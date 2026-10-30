"""Seed for the plan/18 scenario stack (K-SEN-0023 A; 13b takes it over).

Only the product's public API (/api/v1) and its documented CLI (`python -m ffcore.cli`), so the
seed exercises the same paths an operator would. Idempotent: a 409 means "already there" and the
resource is looked up by key; anything else that is not a success stops the seed with its body.

Run in the tools container of the scenario stack, from the repository root:
    python -m tests.e2e.scenarios.seed
Environment (never written to a file): E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD (the superadmin the
seed creates with `create-superadmin --password-stdin`), E2E_PASSWORD (every seeded member).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[3]
SAMPLES = REPO / "data" / "samples"
BACKEND = REPO / "backend"
BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://backend:8000")
API = "/api/v1"
INDEX_TIMEOUT_S = float(os.environ.get("E2E_INDEX_TIMEOUT_S", "900"))
INDEX_TERMINAL = {"indexed", "skipped", "failed", "timeout"}

# fake-llm answers by upstream model id (backend/tests/fakes/fake_openai.py)
PROVIDER_KEY = "fake-llm"
FAKE_LLM_BASE = "http://fake-llm:9999/v1"
MODELS = {
    "chat-default": "ok-model",
    "chat-fail": "fail-model",
    "chat-slow": "slow-model",
    # tool-* mode: calls the first tool once, then answers (fix/fake-llm-tool-mode, K-SEN-0025)
    "chat-tools": "tool-default",
}
TICKET_REPLY = {"tool_key": "ticket-desk", "actions": ["send_reply"]}
# Scenario-only agents: (template, model, changes to its definition).
E2E_AGENTS = {
    "e2e-yavas": ("sozlesme-asistani", "chat-slow", {"knowledge": []}),  # F12 resume
    "e2e-hatali": ("sozlesme-asistani", "chat-fail", {"knowledge": []}),  # F12 model down
    "e2e-sql": ("veri-soru-cevap", "chat-tools", {}),  # F3: one approved run_sql call
    "e2e-bilet": (  # F2: send_reply waits for an analyst's approval
        "sozlesme-asistani",
        "chat-tools",
        {
            "knowledge": [],
            "tools": [TICKET_REPLY],
            "approval": {"actions": ["ticket-desk.send_reply"], "assign_to": "analyst"},
        },
    ),
}
TARGET = "hastane-a"


class SeedError(RuntimeError):
    pass


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SeedError(f"{name} is not set (tests/e2e/scenarios/README.md)")
    return value


def load(rel: str):
    return json.loads((SAMPLES / rel).read_text(encoding="utf-8"))


def cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ffcore.cli", *args],
        cwd=BACKEND,
        input=stdin,
        capture_output=True,
        text=True,
    )


class LoginRefused(SeedError):
    """POST /auth/login answered with an error; `code` is the API's error code."""

    def __init__(self, email: str, status: int, code: str):
        super().__init__(f"login {email}: {status} {code}")
        self.status, self.code = status, code


class Client:
    """Signed-in API client; the Secure session cookie is sent by hand over plain HTTP."""

    def __init__(self, email: str, password: str):
        self.http = httpx.Client(base_url=BACKEND_URL + API, timeout=60)
        r = self.http.post("/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            try:
                code = r.json()["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = "unreadable_error_body"
            raise LoginRefused(email, r.status_code, code)
        self.http.headers["cookie"] = f"ffcore_session={r.cookies['ffcore_session']}"


    def call(self, method: str, path: str, ok=(200, 201, 202, 204), **kw) -> httpx.Response:
        r = self.http.request(method, path, **kw)
        if r.status_code not in ok:
            raise SeedError(f"{method} {path}: {r.status_code} {r.text[:300]}")
        return r

    def create(self, path: str, body: dict, lookup) -> dict:
        """POST, or on 409 the existing resource found by `lookup()`."""
        r = self.call("POST", path, ok=(200, 201, 409), json=body)
        if r.status_code == 409:
            found = lookup()
            if found is None:
                raise SeedError(f"POST {path}: 409 but not found by key: {r.text[:200]}")
            return found
        return r.json()

    def find(self, path: str, key: str, field: str = "key", items: str = "data") -> dict | None:
        rows = self.call("GET", path).json()[items]
        return next((row for row in rows if row[field] == key), None)


def ensure_superadmin(email: str, password: str, *, login=Client, run=cli):
    """The signed-in superadmin. Signs in first; only 401 `invalid_credentials` (no such user)
    creates it with `create-superadmin`. Any other refusal, and any CLI failure (an existing
    user with another password included), stops the seed: no text matching (review r1)."""
    try:
        return login(email, password)
    except LoginRefused as exc:
        if (exc.status, exc.code) != (401, "invalid_credentials"):
            raise
    done = run(
        "create-superadmin",
        "--email",
        email,
        "--full-name",
        "E2E Admin",
        "--password-stdin",
        stdin=password + "\n",
    )
    if done.returncode != 0:
        raise SeedError(f"create-superadmin: {done.stderr.strip() or done.stdout.strip()}")
    return login(email, password)


def seed_projects(admin: Client, projects: dict) -> dict[str, str]:
    ids = {}
    for project in projects["projects"]:
        body = {"key": project["key"], "name": project["name"]}
        ids[project["key"]] = admin.create(
            "/projects", body, lambda k=project["key"]: admin.find("/projects", k)
        )["id"]
    return ids


def seed_members(admin: Client, projects: dict, ids: dict[str, str], password: str) -> None:
    for project in projects["projects"]:
        for member in project["members"]:
            email = member["email"]
            user = admin.create(
                "/users",
                {"email": email, "full_name": member.get("full_name", email), "password": password},
                lambda e=email: admin.find("/users", e, field="email"),
            )
            admin.call(
                "POST",
                f"/projects/{ids[project['key']]}/members",
                ok=(201, 409),
                json={"user_id": user["id"], "role": member["role"], "access": member["access"]},
            )


def seed_models(admin: Client, ids: dict[str, str]) -> None:
    provider = admin.create(
        "/providers",
        {
            "key": PROVIDER_KEY,
            "label": "Fake LLM (test stack)",
            "driver": "openai_compatible",
            "domains": ["model"],
            "config": {"base_url": FAKE_LLM_BASE, "api_key": "dummy-not-secret-e2e"},
            "project_ids": list(ids.values()),
        },
        lambda: admin.find("/providers", PROVIDER_KEY),
    )
    admin.call(
        "PUT", f"/providers/{provider['id']}/projects", json={"project_ids": list(ids.values())}
    )
    for pid in ids.values():
        for key, upstream in MODELS.items():
            admin.call(
                "POST",
                f"/projects/{pid}/models",
                ok=(201, 409),
                json={
                    "key": key,
                    "display_name": key,
                    "provider_id": provider["id"],
                    "category": "llm",
                    "model_id": upstream,
                    "upstream_api": "chat",  # chosen explicitly, never detected
                    # agents with tools need a tool-calling model; fake-llm accepts tools on all
                    "capabilities": {"tool_calls": True},
                    "request_policy": {"extra_body": {"reasoning_effort": "none"}},
                },
            )


def wait_indexed(admin: Client, base: str, doc_ids: list[str]) -> None:
    deadline = time.monotonic() + INDEX_TIMEOUT_S
    pending = set(doc_ids)
    while pending:
        for doc_id in sorted(pending):
            doc = admin.call("GET", f"{base}/documents/{doc_id}").json()
            if doc["status"] in INDEX_TERMINAL:
                if doc["status"] != "indexed":
                    raise SeedError(f"{doc['filename']}: {doc['status']} {doc.get('error')}")
                pending.discard(doc_id)
        if pending and time.monotonic() > deadline:
            raise SeedError(f"documents not indexed after {INDEX_TIMEOUT_S} s: {sorted(pending)}")
        if pending:
            time.sleep(3)


def _readback():
    """13a's stdlib reader (DOCX, PDF text layer), loaded by path: it is a test helper."""
    import importlib.util

    path = SAMPLES / "scripts" / "tests" / "readback.py"
    spec = importlib.util.spec_from_file_location("readback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upload_form(path: Path) -> tuple[str, bytes]:
    """(name, bytes) to upload. The test stack has no Docling weights (model_missing), so DOCX
    goes in as its text (<stem>.txt, 13a readback; K-SEN-0028 A). The text-layer PDFs index
    without weights (seen on the stack), so they go in as they are. The Docling path is 04a's
    own `models` test; these scenarios test retrieval and the runtime."""
    if path.suffix == ".docx":
        return f"{path.stem}.txt", _readback().text_of(path).encode("utf-8")
    return path.name, path.read_bytes()


def seed_kb(admin: Client, pid: str, key: str, files: list[tuple[Path, list[str]]]) -> str:
    """KB `key` with `files` [(path, acl_roles)]; [] = open to every member (13a words.py)."""
    base = f"/projects/{pid}/knowledge-bases"
    kb = admin.create(base, {"key": key, "name": key}, lambda: admin.find(base, key))
    doc_ids = []
    for path, roles in files:
        data = {"acl_open": "true"} if not roles else {"acl_roles": roles}
        r = admin.call(
            "POST", f"{base}/{kb['id']}/documents", files={"files": upload_form(path)}, data=data
        )
        doc_ids += [row["document"]["id"] for row in r.json()["data"]]
    wait_indexed(admin, f"{base}/{kb['id']}", doc_ids)
    return kb["id"]


def seed_knowledge(admin: Client, projects: dict, ids: dict[str, str]) -> None:
    """Each project's KBs from projects.json (contracts with their manifest ACL, other sources
    open), then the scenario KBs of the target project: `zehirli` (F11), `surumler` (F13)."""
    acl = {c["file_name"]: c["acl_roles"] for c in load("contracts/manifest.json")}
    for project in projects["projects"]:
        for kb in project["knowledge_bases"]:
            folder = SAMPLES / kb["source"]
            files = sorted(p for p in folder.iterdir() if p.suffix in (".pdf", ".docx", ".txt"))
            seed_kb(
                admin, ids[project["key"]], kb["key"], [(f, acl.get(f.name, [])) for f in files]
            )
    poison = sorted((SAMPLES / "poison" / "docs").glob("*.txt"))
    seed_kb(admin, ids[TARGET], "zehirli", [(p, []) for p in poison])
    versions = []
    for v in load("versions/expected.json"):
        versions += [(SAMPLES / v["v1_file"], []), (SAMPLES / v["v2_file"], [])]
    seed_kb(admin, ids[TARGET], "surumler", versions)


def seed_tools(admin: Client, pid: str) -> None:
    base = f"/projects/{pid}/tools"
    tools = {
        "mcp-sql": ("http://mcp-sql:8000/mcp", {"type": "forward_user"}),
        "ticket-desk": ("http://ticket-desk:8000/mcp", {"type": "none"}),
    }
    for key, (url, auth) in tools.items():
        body = {"key": key, "name": key, "kind": "mcp", "endpoint_url": url, "auth": auth}
        tool = admin.create(base, body, lambda k=key: admin.find(base, k))
        tool = admin.call("POST", f"{base}/{tool['id']}/discover").json()
        if tool["status"] != "discovered":
            raise SeedError(f"discover {key}: {tool['status']} {tool.get('last_error_code')}")
        for action in tool["actions"]:
            # writes keep their approval; reads are opened without one (F2: send_reply waits)
            reads = action["name"] in ("get_schema", "list_tickets", "get_ticket")
            admin.call(
                "PATCH",
                f"{base}/{tool['id']}/actions/{action['name']}",
                json={"enabled": True, "needs_approval": not reads},
            )
    for args in (
        ("seed-sql-demo", "--path", "../data/samples/schema"),
        (
            "seed-sql-context",
            "--project",
            TARGET,
            "--tool",
            "mcp-sql",
            "--path",
            "../data/samples/schema",
        ),
    ):
        done = cli(*args)
        if done.returncode != 0:
            raise SeedError(f"{args[0]}: {done.stderr.strip() or done.stdout.strip()}")


def _publish(
    admin: Client, pid: str, key: str, name: str, description: str, definition: dict
) -> None:
    base = f"/projects/{pid}/agents"
    agent = admin.create(
        base,
        {"key": key, "name": name, "description": description, "model": definition["model"]},
        lambda: admin.find(base, key, items="items"),
    )
    if agent["status"] == "published":
        return  # idempotent: an existing published agent is kept as it is
    version = agent["latest_version"]
    admin.call("PUT", f"{base}/{agent['id']}/versions/{version}", json={"definition": definition})
    admin.call("POST", f"{base}/{agent['id']}/publish", json={"version": version})


def seed_agents(admin: Client, projects: dict, ids: dict[str, str]) -> None:
    """Every template in the target project; in the other projects the agents projects.json
    names, pointed at that project's own KB. Plus the scenario-only E2E_AGENTS."""
    templates = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in (SAMPLES / "agents").glob("*.json")
    }
    for key, t in sorted(templates.items()):
        _publish(admin, ids[TARGET], key, t["name"], t["description"], t["definition"])
    for project in projects["projects"]:
        if project["key"] == TARGET:
            continue
        own_kb = project["knowledge_bases"][0]["key"]
        for key in project["agents"]:
            t = templates[key]
            knowledge = [{**k, "kb_key": own_kb} for k in t["definition"]["knowledge"]]
            definition = {**t["definition"], "knowledge": knowledge}
            _publish(admin, ids[project["key"]], key, t["name"], t["description"], definition)
    for key, (template, model, changes) in E2E_AGENTS.items():
        definition = {**templates[template]["definition"], "model": model, **changes}
        _publish(admin, ids[TARGET], key, key, "plan/18 scenario (test stack only)", definition)


def seed_guardrails(admin: Client, ids: dict[str, str]) -> None:
    """The target project's `default` policy: the built-in rules in enforce mode, so PII leaves
    tokenized (F4). The built-in policy is monitor (08-lite): it records the tokenization but
    sends the text as it is (K-SEN-0029: becomes enforce, fix/08-default-egress-enforce); the
    other project keeps it, and test_18_f4_1c shows the leak until that fix.
    The secrets rule only logs here: its entropy check flags document file names
    (`SZL-2025-003_temizlik-hizmet.txt` → API_TOKEN) and would block every KB run in enforce
    (finding T-18-0038). A same-key row overrides the built-in policy."""
    base = f"/projects/{ids[TARGET]}/guardrail-policies"
    current = admin.find(base, "default")
    if current is None:
        raise SeedError(f"{base}: no default policy")
    if not current["builtin"]:
        return  # idempotent: the seeded row is kept as it is
    rules = [{**r, "action": "log"} if r["type"] == "secrets" else r for r in current["rules"]]
    body = {
        "key": "default",
        "name": "Default (enforce, plan/18 F4)",
        "mode": "enforce",
        "rules": rules,
        **{k: current[k] for k in ("short_circuit", "on_error", "block_message")},
    }
    admin.call("POST", base, json=body)


def seed_prompts() -> None:
    done = cli("seed-prompts", "--path", "prompts")
    if done.returncode != 0:
        raise SeedError(f"seed-prompts: {done.stderr.strip() or done.stdout.strip()}")


def main() -> int:
    email, admin_password = env("E2E_ADMIN_EMAIL"), env("E2E_ADMIN_PASSWORD")
    password = env("E2E_PASSWORD")
    projects = load("projects/projects.json")
    admin = ensure_superadmin(email, admin_password)
    seed_prompts()
    ids = seed_projects(admin, projects)
    seed_members(admin, projects, ids, password)
    me = admin.call("GET", "/auth/me").json()["user"]["id"]
    for pid in ids.values():  # a superadmin must be a member to run agents (run_needs_membership)
        admin.call(
            "POST", f"/projects/{pid}/members", ok=(201, 409), json={"user_id": me, "role": "admin"}
        )
    seed_models(admin, ids)
    seed_guardrails(admin, ids)
    seed_knowledge(admin, projects, ids)
    seed_tools(admin, ids[TARGET])
    seed_agents(admin, projects, ids)
    print(f"seeded: projects {sorted(ids)}, models {sorted(MODELS)}, agents in {TARGET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SeedError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
