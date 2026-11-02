"""13b `make eval`: run an exam set through the 06a run API and write a Markdown report.

PoC only (K-13b-0006 S2): the set is read from its JSON file (default
data/samples/eval/sozlesme-33.json; on the PayCore server the S1 set by path, never copied
here), and the report goes to eval/results/ (git-ignored). Package 09 moves exams to Langfuse
datasets after the PoC; this script is not a second exam system, only the M3 summary.

Scorers, per item (data/samples/eval/suite.json):
  contains      every `must_contain` text is in the answer (case-insensitive)
  cites_source  every expected document is among the run's `sources` (matched by file stem:
                the scenario seed uploads DOCX as <stem>.txt)
  sql_result    every expected value appears in a run_sql `tool_result`, not only in the text
  holds         an unanswerable item: no answer (`outcome_label` other than `answered`)
  llm_judge     NOT_RUN: no judge model in the PoC (DECISION-2, decided at M3)
A failed run fails every scorer. SQL items wait for an approval; the runner approves them only
with `--approve-sql` (an explicit choice, recorded in the report), otherwise they are NOT_RUN.
A run on fake-llm proves the pipeline only; the report says so and is never a measurement.
"""

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SET = REPO / "data" / "samples" / "eval" / "sozlesme-33.json"
API = "/api/v1"
TERMINAL = {"completed", "failed", "cancelled", "abandoned"}
WAITING = {"waiting_approval", "waiting_user"}


@dataclass
class ItemResult:
    id: str
    style: str
    answerable: bool
    sql: bool
    outcome_label: str | None
    status: str
    scores: dict = field(default_factory=dict)  # scorer -> True | False | None (NOT_RUN)
    seconds: float | None = None
    llm_calls: int = 0
    note: str = ""


def _is_sql(item: dict) -> bool:
    return "sql" in item["metadata"].get("tags", [])


def _stems(names) -> set[str]:
    return {Path(str(n)).stem.casefold() for n in names}


def score(item: dict, run: dict, events: list[dict]) -> dict:
    expected = item["expected_output"]
    meta = item["metadata"]
    ok = run.get("status") == "completed"
    answer = (run.get("output") or "").casefold()
    scores: dict = {}
    if meta["answerable"]:
        scores["contains"] = ok and all(t.casefold() in answer for t in expected["must_contain"])
        if _is_sql(item):
            results = " ".join(
                json.dumps(e["payload"], ensure_ascii=False)
                for e in events
                if e["type"] == "tool_result" and "run_sql" in str(e["payload"].get("name", ""))
            )
            values = [str(v) for row in expected.get("sql_result", []) for v in row]
            scores["sql_result"] = ok and bool(values) and all(v in results for v in values)
        else:
            cited = _stems(
                s.get("document_name", "")
                for e in events
                if e["type"] == "sources"
                for s in (e["payload"].get("selected") or e["payload"].get("sources") or [])
            )
            wanted = expected.get("must_cite") or meta.get("expected_docs") or []
            scores["cites_source"] = ok and bool(wanted) and _stems(wanted) <= cited
    else:
        scores["holds"] = ok and run.get("outcome_label") != "answered"
    scores["llm_judge"] = None
    return scores


def _excluded_by(item: dict, exclude: list[str]) -> str | None:
    """The first excluded source the item depends on (`metadata.sources`, `<kind>:<space>`)."""
    for source in item["metadata"].get("sources") or []:
        segments = [s.casefold() for s in str(source).split(":")]
        for name in exclude:
            if name.casefold() in segments:
                return name
    return None


def select_items(items: list[dict], exclude: list[str]) -> tuple[list[dict], dict[str, int]]:
    """19: questions that depend on an excluded source (S1's PRSIM questions) are left out of the
    run and counted; the report says n/N, the threshold is computed on n (KARARLAR "M3 korpus
    kapsamı"). Not a NOT_RUN: the item is outside the measured corpus on both sides."""
    kept, excluded = [], {}
    for item in items:
        name = _excluded_by(item, exclude) if exclude else None
        if name is None:
            kept.append(item)
        else:
            excluded[name] = excluded.get(name, 0) + 1
    return kept, excluded


def passed(scores: dict) -> bool:
    return all(v for v in scores.values() if v is not None)


def _count(results, predicate) -> tuple[int, int]:
    chosen = [r for r in results if predicate(r) and r.status != "not_run"]
    return sum(passed(r.scores) for r in chosen), len(chosen)


def markdown(meta: dict, results: list[ItemResult]) -> str:
    lines = [
        f"# Exam report: {meta['dataset']}",
        "",
        f"- Agent: `{meta['agent']}`; SQL agent: `{meta.get('sql_agent', '-')}`",
        f"- Model: {meta['model']}; profile: {meta.get('profile', '-')}; "
        f"run at {meta.get('at', '-')} UTC",
    ]
    if "fake" in meta["model"]:
        lines.append(
            "- **fake model: this run proves the pipeline only, it is not a measurement.**"
        )
    if "total" in meta:
        excluded = meta.get("excluded") or {}
        shown = ", ".join(f"{k} {v}" for k, v in sorted(excluded.items())) or "none"
        lines.append(
            f"- Scored items: {len(results)}/{meta['total']} (excluded by source: {shown})"
        )
    if meta.get("warmup"):
        lines.append(
            f"- Warmup runs (not scored, not in times): {len(meta['warmup'])}, "
            + ", ".join(f"{s:.1f} s" for s in meta["warmup"])
        )
    lines += ["", "## Outcome labels", "", "| outcome_label | n |", "|---|---|"]
    labels: dict[str, int] = {}
    for r in results:
        labels[r.outcome_label or r.status] = labels.get(r.outcome_label or r.status, 0) + 1
    lines += [f"| {k} | {v} |" for k, v in sorted(labels.items())]
    doc = _count(results, lambda r: r.answerable and not r.sql)
    held = _count(results, lambda r: not r.answerable)
    sql = _count(results, lambda r: r.sql)
    sql_skipped = sum(1 for r in results if r.sql and r.status == "not_run")
    times = sorted(r.seconds for r in results if r.seconds is not None)
    p95 = times[max(0, round(0.95 * len(times)) - 1)] if times else None
    calls = [r.llm_calls for r in results if r.status != "not_run"]
    lines += [
        "",
        "## Summary",
        "",
        f"- Document questions with the right source: {doc[0]}/{doc[1]}",
        f"- Source accuracy: {doc[0]}/{doc[1]} ({100 * doc[0] / doc[1]:.1f}%)"
        if doc[1]
        else "- Source accuracy: no document question",
        f"- Unanswerable questions held: {held[0]}/{held[1]}",
        f"- SQL questions: {sql[0]}/{sql[1]}"
        + (f" ({sql_skipped} NOT_RUN: --approve-sql not given)" if sql_skipped else ""),
        "- llm_judge: NOT_RUN (no judge model in the PoC; DECISION-2, M3)",
        f"- Answer time: median {statistics.median(times):.1f} s, P95 {p95:.1f} s"
        if times
        else "- Answer time: no completed run",
        f"- LLM calls per question: {statistics.mean(calls):.2f}" if calls else "",
        "",
        "## Items",
        "",
        "| id | style | status | outcome_label | passed | scores | s | note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        shown = ", ".join(
            f"{k}={'NOT_RUN' if v is None else ('ok' if v else 'fail')}"
            for k, v in r.scores.items()
        )
        verdict = "-" if r.status == "not_run" else ("yes" if passed(r.scores) else "no")
        secs = "-" if r.seconds is None else f"{r.seconds:.1f}"
        lines.append(
            f"| {r.id} | {r.style} | {r.status} | {r.outcome_label or '-'} | {verdict} | "
            f"{shown} | {secs} | {r.note} |"
        )
    return "\n".join(line for line in lines if line is not None) + "\n"


class Runner:
    """A signed-in console user running agents over the public API (the scenario stack's way)."""

    def __init__(self, base_url: str, email: str, password: str, timeout_s: float):
        import httpx

        self.http = httpx.Client(base_url=base_url, timeout=httpx.Timeout(60, read=None))
        r = self.http.post(f"{API}/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise SystemExit(f"eval: login {email}: {r.status_code} {r.text[:200]}")
        self.http.headers["cookie"] = f"ffcore_session={r.cookies['ffcore_session']}"
        self.me = r.json()
        self.timeout_s = timeout_s

    def project_id(self, key: str) -> str:
        for m in self.me.get("memberships", []):
            if m.get("project_key") == key:
                return m["project_id"]
        raise SystemExit(f"eval: {key}: the user is not a member")

    def run(self, pid: str, agent: str, item: dict, approve: bool) -> tuple[dict, list, float]:
        started = time.monotonic()
        body = {"input": item["input"]["message"], "variables": item["input"].get("variables", {})}
        url = f"{API}/projects/{pid}/agents/{agent}/runs"
        run_id = None
        with self.http.stream("POST", url, json=body) as r:
            if r.status_code != 200:
                raise SystemExit(f"eval: {item['id']}: {r.status_code} {r.read()[:200]!r}")
            for line in r.iter_lines():
                if line.startswith("data:") and run_id is None:
                    data = json.loads(line[5:].strip() or "{}")
                    run_id = data.get("run_id")
        if run_id is None:
            raise SystemExit(f"eval: {item['id']}: no run_id in the stream")
        detail = self._settle(pid, run_id)
        while detail["status"] == "waiting_approval" and approve:
            self.http.post(
                f"{API}/projects/{pid}/runs/{run_id}/resume",
                json={"decision": "approved", "comment": "make eval --approve-sql"},
            ).read()
            detail = self._settle(pid, run_id)
        events = self.http.get(f"{API}/projects/{pid}/runs/{run_id}/events").json()["items"]
        return detail, events, time.monotonic() - started

    def _settle(self, pid: str, run_id: str) -> dict:
        deadline = time.monotonic() + self.timeout_s
        while True:
            detail = self.http.get(f"{API}/projects/{pid}/runs/{run_id}").json()
            if detail["status"] in TERMINAL | WAITING:
                return detail
            if time.monotonic() > deadline:
                raise SystemExit(f"eval: run {run_id} still {detail['status']} (timeout)")
            time.sleep(2)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_out(dataset: Path, *, out: str | None, out_dir: str | None, now: datetime) -> Path:
    """Where the report goes (19 şart 5). A set from outside the repository (S1 on the server)
    needs an explicit place outside it: no default that could drop the report into a checkout
    or into a container layer that disappears. Inside the repository only `eval/results/`."""
    name = f"eval-{now:%Y%m%d-%H%M}.md"
    target = Path(out) if out else Path(out_dir) / name if out_dir else None
    if target is None:
        if not _inside(dataset, REPO):
            raise SystemExit(
                "eval: eval_out_required: the dataset is outside the repository; "
                "set EVAL_OUT to a directory outside it (e.g. /var/lib/ffcore/eval)"
            )
        return REPO / "eval" / "results" / name
    if _inside(target, REPO) and not _inside(target, REPO / "eval" / "results"):
        raise SystemExit(f"eval: eval_out_inside_repo: {target} (only eval/results/ is allowed)")
    return target


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dataset", default=str(DEFAULT_SET))
    p.add_argument("--project", default="hastane-a")
    p.add_argument("--agent", default="sozlesme-asistani")
    p.add_argument("--sql-agent", default="veri-soru-cevap")
    p.add_argument("--approve-sql", action="store_true", help="approve each run_sql call")
    p.add_argument("--model", required=True, help="what answered, e.g. fake-llm, qwen3.5:35b cpu")
    p.add_argument("--user", default=None, help="default: <project>-analyst-edit@example.test")
    p.add_argument("--out", default=None, help="report file")
    p.add_argument("--out-dir", default=None, help="report directory (make eval EVAL_OUT=...)")
    p.add_argument(
        "--exclude-sources",
        nargs="*",
        default=[],
        help="leave out questions that depend on these sources (19: S1 without PRSIM)",
    )
    p.add_argument(
        "--warmup",
        type=int,
        default=0,
        help="run the first N questions this many times first; reported apart, not scored",
    )
    a = p.parse_args(argv)
    password = os.environ.get("E2E_PASSWORD")
    if not password:
        raise SystemExit("eval: E2E_PASSWORD is not set (the seeded members' password)")
    out = resolve_out(Path(a.dataset), out=a.out, out_dir=a.out_dir, now=datetime.now(UTC))
    every = json.loads(Path(a.dataset).read_text(encoding="utf-8"))
    items, excluded = select_items(every, a.exclude_sources)
    runner = Runner(
        os.environ.get("E2E_BACKEND_URL", "http://backend:8000"),
        a.user or f"{a.project}-analyst-edit@example.test",
        password,
        float(os.environ.get("E2E_RUN_TIMEOUT_S", "900")),
    )
    pid = runner.project_id(a.project)
    warmup = []
    for item in [i for i in items if not _is_sql(i)][: a.warmup]:
        _, _, secs = runner.run(pid, a.agent, item, False)
        warmup.append(secs)
        print(f"warmup {item['id']}: {secs:.1f} s", flush=True)
    results = []
    for item in items:
        meta = item["metadata"]
        sql = _is_sql(item)
        if sql and not a.approve_sql:
            results.append(
                ItemResult(
                    item["id"],
                    meta["style"],
                    meta["answerable"],
                    sql,
                    None,
                    "not_run",
                    {},
                    None,
                    0,
                    "NOT_RUN: --approve-sql not given",
                )
            )
            continue
        detail, events, secs = runner.run(pid, a.sql_agent if sql else a.agent, item, a.approve_sql)
        scores = score(item, detail, events)
        llm = sum(1 for e in events if e["type"] == "llm_call")
        results.append(
            ItemResult(
                item["id"],
                meta["style"],
                meta["answerable"],
                sql,
                detail.get("outcome_label"),
                detail["status"],
                scores,
                secs,
                llm,
                detail.get("error_code") or "",
            )
        )
        print(
            f"{item['id']}: {detail['status']} {'pass' if passed(scores) else 'fail'}", flush=True
        )
    now = datetime.now(UTC)
    meta = {
        "dataset": Path(a.dataset).stem,
        "agent": a.agent,
        "sql_agent": a.sql_agent,
        "model": a.model,
        "profile": os.environ.get("DEPLOY_PROFILE", "-"),
        "at": now.strftime("%Y-%m-%d %H:%M"),
        "total": len(every),
        "excluded": excluded,
        "warmup": warmup,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(meta, results), encoding="utf-8")
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
