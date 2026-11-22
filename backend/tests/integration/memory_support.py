"""14 test support: a NER that knows the 13a set's invented names, the memory port and the
extraction job's ports without HTTP, and the settings memory needs.

The in-process TestClient cannot be called again from inside a request (an InlineQueue attempt
runs inside the run request), so `DirectMemory` calls the internal route handlers of
api/memories.py as coroutines with their own session: the same code the worker reaches over
HTTP, without the transport (HttpMemory has its own unit test).
"""

import ast
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from ffcore.api import memories as api
from ffcore.core import db
from ffcore.core.auth import SERVICE_ACTOR
from ffcore.guardrails.findings import Finding
from ffcore.memory.recall import MemoryConflict, Recall
from ffcore.runtime.state import ModelTurn

REPO = Path(__file__).resolve().parents[3]
MEMORY_SET = REPO / "data" / "samples" / "memory" / "memory-40.jsonl"
NAMES_SOURCE = REPO / "data" / "samples" / "scripts" / "gen" / "pii.py"
NER = {"ner_model": "acme/turkish-ner", "ner_revision": "0123456789abcdef"}


def _names(variable: str) -> list[str]:
    """The invented name lists of the 13a generator (DECISION-24), read without importing it."""
    tree = ast.parse(NAMES_SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == variable:
            return list(ast.literal_eval(node.value))
    raise LookupError(variable)


FIRST_NAMES = _names("FIRST_NAMES")
LAST_NAMES = _names("LAST_NAMES")


def memory_set() -> list[dict]:
    return [json.loads(line) for line in MEMORY_SET.read_text(encoding="utf-8").splitlines()]


class SetNer:
    """PERSON for every invented surname of the set (the person names 13a puts in turns)."""

    model, revision = NER["ner_model"], NER["ner_revision"]

    def __init__(self) -> None:
        self.calls = 0

    async def find(self, text, categories):
        self.calls += 1
        lowered = text.lower()
        found = []
        for name in LAST_NAMES:
            start = lowered.find(name.lower())
            if start != -1:
                end = start + len(name)
                found.append(Finding("PERSON", start, end, 0.97, "ner", text[start:end]))
        return found


def enable(pg, project_id, *, agent_id=None, enabled=True, kinds=None, max_items=200, top_k=5):
    pg.execute(
        "INSERT INTO memory_settings (id, project_id, agent_id, enabled, allowed_kinds,"
        " max_items_per_user, recall_top_k, extraction_model, updated_by)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, 'memory-extract', 'test')",
        (
            uuid.uuid4(),
            project_id,
            agent_id,
            enabled,
            kinds or ["profile", "preference", "fact", "decision"],
            max_items,
            top_k,
        ),
    )


class DirectMemory:
    """The worker's memory port (HttpMemory's interface) over the internal route handlers."""

    def __init__(self, settings, *, run_id, project_id, user_id) -> None:
        self.settings = settings
        self.ids = {"run_id": run_id, "project_id": project_id, "user_id": user_id}
        self.recalls: list[str] = []

    @classmethod
    def factory(cls, settings, holder: list | None = None):
        def make(_settings=None, **ids):
            port = cls(settings, **ids)
            if holder is not None:
                holder.append(port)
            return port

        return make

    @classmethod
    def for_run(cls, settings, holder: list | None = None):
        """Ports.memory: the port of the run being attempted (its user, as the worker does)."""

        def make(run):
            if run.user_id is None:
                return None
            port = cls(settings, run_id=run.id, project_id=run.project_id, user_id=run.user_id)
            if holder is not None:
                holder.append(port)
            return port

        return make

    async def _call(self, handler, model, **body):
        async with db.session_scope() as session:
            try:
                return await handler(
                    model(**self.ids, **body), SERVICE_ACTOR, session, self.settings
                )
            except Exception as exc:
                if getattr(exc, "status_code", None) == 409:
                    raise MemoryConflict(exc.code) from exc
                raise

    async def recall(self, question, share):
        self.recalls.append(question)
        out = await self._call(
            api.internal_recall, api.RecallRequest, question=question, share=share
        )
        return Recall(
            out.off_reason,
            [i.model_dump(mode="json") for i in out.items],
            dropped=[str(i) for i in out.dropped],
        )

    async def related(self, text):
        out = await self._call(api.internal_related, api.RelatedRequest, text=text)
        return Recall(
            out.off_reason, [i.model_dump(mode="json") for i in out.items], out.extraction_model
        )

    async def write(self, items):
        out = await self._call(
            api.internal_candidates,
            api.CandidatesRequest,
            items=[api.CandidateIn(**i) for i in items],
        )
        return json.loads(out.model_dump_json())


def insert_item(
    pg, settings, project_id, user_id, text, *, kind="preference", use_count=0, agent_id=None
):
    """An item put straight into the table (no write rule), with the fake embedding."""
    import asyncio

    from ffcore.knowledge.embed import embed

    vector = asyncio.run(embed(settings, [text])).dense[0]
    item_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO memories (id, project_id, user_id, agent_id, kind, text, embedding,"
        " confidence, use_count) VALUES (%s, %s, %s, %s, %s, %s, %s::vector, 1, %s)",
        (item_id, project_id, user_id, agent_id, kind, text, str(list(vector)), use_count),
    )
    return item_id


def catalog_model(pg, project_id, key="memory-extract"):
    """An active chat model of the project's catalog (the extraction model a setting names)."""
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted, supports_test,"
        " is_active, created_by) VALUES (%s, %s, 'P', 'openai_compatible', ARRAY['model'],"
        " '\\x00', true, true, 'test')",
        (provider, f"prov-{provider.hex[:8]}"),
    )
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, is_active,"
        " created_by) VALUES (%s, %s, %s, 'm', %s, 'llm', 'x', '{}', ARRAY['text'], '{}', '{}',"
        " 'chat', '{}', true, 'test')",
        (uuid.uuid4(), project_id, key, provider),
    )


def turn_of(content: str) -> ModelTurn:
    return ModelTurn(
        content=content,
        tool_calls=[],
        finish_reason="stop",
        usage={"prompt_tokens": 5, "completion_tokens": 5},
        fallback=None,
        model="p.memory-extract",
        ms=10,
    )


class Extractor:
    """The extraction model's port: a function of the prompt's turn text gives the JSON answer."""

    def __init__(self, answer) -> None:
        self.answer = answer
        self.seen: list[dict] = []

    def factory(self):
        def make(settings, session, slots, **kwargs):
            self.seen.append(kwargs)
            outer = self

            class Caller:
                async def call(self, messages, *, tools, max_tokens, on_token):
                    outer.seen[-1]["messages"] = messages
                    return turn_of(outer.answer(messages[0]["content"]))

            return Caller()

        return make


class FakePrompt:
    def __init__(self, text: str) -> None:
        self.text = text

    def compile(self, **values):
        out = self.text
        for key, value in values.items():
            out = out.replace("{{" + key + "}}", value)
        return out


class FakePrompts:
    def __init__(self) -> None:
        seed = REPO / "backend" / "prompts" / "memory_extract.md"
        self.prompt = FakePrompt(seed.read_text(encoding="utf-8"))

    def get(self, name, label="production"):
        assert name == "memory_extract"
        return self.prompt


def job_ctx(redis, settings, extractor: Extractor, holder=None) -> dict:
    return {
        "redis": redis,
        "slots": SimpleNamespace(),
        "prompts": FakePrompts(),
        "settings": settings,
        "memory_client_factory": DirectMemory.factory(settings, holder),
        "memory_model_factory": extractor.factory(),
    }


def answer_json(*items) -> str:
    return json.dumps({"items": list(items)}, ensure_ascii=False)


def turn_user_text(prompt: str) -> str:
    """The user's line of the turn inside the extraction prompt."""
    body = prompt.split("<<<TURN", 1)[1].split("TURN>>>", 1)[0]
    for line in body.splitlines():
        if line.startswith("USER: "):
            return line[len("USER: ") :]
    raise AssertionError("no user line in the turn")
