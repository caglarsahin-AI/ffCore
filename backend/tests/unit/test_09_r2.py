"""09-1 r2 review (state/reviews/09-1-r2.md, KARARLAR "09-1 r2 kararları"): unit tests.

MAJOR-r2-1 a rejected run_sql makes the item not_run; MAJOR-r2-2 a tick has a time budget and
does not judge while the background window is closed, and a tick that saved progress resets the
failure count; MAJOR-r2-3 an mcp-sql refusal or database error is a tool error and only a
successful call is read again; MINOR-r2-1..7.
"""

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import anyio
import pytest

from ffcore.evaluation import worker_tick
from ffcore.evaluation.engine import (
    ItemFacts,
    deterministic_scores,
    executed_sql,
    item_result,
    summarize,
)
from ffcore.evaluation.runner import Budget, combine
from ffcore.evaluation.scorers import Score
from tests.unit.test_09_engine import _call, _ev, _facts, _item

BACKEND = Path(__file__).resolve().parents[2]
SQL_CFG = {"sql_result": {"name": "sql_result"}, "contains": {"name": "contains"}}


def _sql_item(i="q01"):
    return _item(i, must_contain=["3"], sql_result=[["3"]])


def _summary(results):
    return summarize(results, pass_threshold=0.5, warmup_ms=None, latencies_ms=[])


# --- MAJOR-r2-1: a person's rejection is an item not_run -----------------------------------------


def test_09_r2_major1_rejected_sql_item_is_not_run_and_exam_incomplete():
    facts = _facts(answer="no rows", sql=[], sql_rejected=True)
    scores = deterministic_scores(_sql_item(), facts, SQL_CFG, None, "approval_rejected")
    rejected = item_result(_sql_item(), facts, scores, "")
    assert (rejected.passed, rejected.note) == (None, "approval_rejected")
    ok = item_result(_item("q02"), _facts(), [Score("contains", 1.0, True)], "")
    s = _summary([rejected, ok])
    assert s["not_run"] == {"approval_rejected": 1} and s["complete"] is False
    assert s["scored"] == 1 and s["passed_items"] == 1


def test_09_r2_major1_rejected_call_after_an_executed_one_is_scored():
    facts = _facts(answer="3", sql=[("sql", "SELECT 3")], sql_rejected=True)
    scores = deterministic_scores(_sql_item(), facts, SQL_CFG, [["3"]], None)
    r = item_result(_sql_item(), facts, scores, "")
    assert r.passed is True and r.note == ""


# --- MAJOR-r2-2: tick time budget, closed window, progress resets the count ---------------------


def _window_settings(open_now: bool):
    zone = ZoneInfo("Europe/Istanbul")
    now = datetime.now(zone)
    if open_now:
        start, end = now - timedelta(hours=1), now + timedelta(hours=1)
    else:
        start, end = now + timedelta(hours=2), now + timedelta(hours=3)
    return SimpleNamespace(
        eval_judge_calls_per_tick=20,
        llm_call_timeout_s=60,
        eval_judge_call_s=60,
        background_window=f"{start:%H:%M}-{end:%H:%M}",
        background_window_weekends=False,
        background_window_tz="Europe/Istanbul",
    )


def test_09_r2_major2_tick_budget_knows_the_background_window():
    closed = worker_tick.tick_budget(_window_settings(open_now=False))
    opened = worker_tick.tick_budget(_window_settings(open_now=True))
    assert closed.judge_open() is False and opened.judge_open() is True
    assert closed.judge_calls == 20
    # The tick ends before the cron job's timeout cancels it.
    assert opened.deadline is not None
    assert opened.deadline - time.monotonic() < worker_tick.TICK_TIMEOUT_S


def test_09_r2_major2_budget_refuses_a_judge_call_past_the_deadline():
    b = Budget(5, deadline=time.monotonic() + 1.0, call_s=0.4)
    # r4 MAJOR-r4-1: the first item too needs its planned time (9 x 0.4 s does not fit).
    assert b.may_judge(9) is False and b.may_judge(2) is True
    b.started = 1
    assert b.may_judge(2) is True
    assert b.may_judge(3) is False  # 3 x 0.4 s does not fit in the second left
    assert Budget(1).may_judge(3) is True  # a repeat above the per-tick limit still progresses
    later = Budget(2)
    later.started = 1
    # r3 MINOR-r3-1: after the first item the limit is strict.
    assert later.may_judge(2) is True and later.may_judge(3) is False
    later.judge_calls = 0
    assert later.may_judge(1) is False and later.may_judge(0) is True
    assert Budget(5, is_open=lambda: False).may_judge(1) is False
    assert Budget(5, is_open=lambda: False).may_judge(0) is True  # no judge: no window


class _CountRedis:
    def __init__(self):
        self.incr_calls, self.deleted = 0, []

    async def incr(self, key):
        self.incr_calls += 1
        return self.incr_calls

    async def expire(self, *a):
        pass

    async def delete(self, key):
        self.deleted.append(key)


def _advance_one_with(monkeypatch, fake_advance):
    @asynccontextmanager
    async def scope():
        class _S:
            async def get(self, *_):
                return SimpleNamespace(status="running", cancel_requested_at=None)

            async def rollback(self):
                pass

        yield _S()

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    monkeypatch.setattr(worker_tick, "advance_eval", fake_advance)
    for name in ("_judge", "_sql", "_embed", "_closer"):
        monkeypatch.setattr(worker_tick, name, lambda *a: None)
    redis = _CountRedis()
    settings = _window_settings(open_now=True)
    return redis, lambda: anyio.run(
        worker_tick._advance_one, settings, redis, None, None, None, "ev", None
    )


def test_09_r2_major2_failing_tick_that_saved_progress_resets_the_count(monkeypatch):
    async def progressed_then_failed(*a, budget, **kw):
        budget.committed += 1
        raise RuntimeError("later item failed")

    redis, run = _advance_one_with(monkeypatch, progressed_then_failed)
    run()
    assert redis.incr_calls == 0 and redis.deleted == [worker_tick.failures_key("ev")]


def test_09_r2_major2_failing_tick_without_progress_counts(monkeypatch):
    async def failed(*a, budget, **kw):
        raise RuntimeError("down")

    redis, run = _advance_one_with(monkeypatch, failed)
    run()
    assert redis.incr_calls == 1 and redis.deleted == []


def test_09_r2_minor5_cancelled_tick_without_progress_counts_and_reraises(monkeypatch):
    async def cancelled(*a, budget, **kw):
        raise asyncio.CancelledError

    redis, run = _advance_one_with(monkeypatch, cancelled)
    with pytest.raises(asyncio.CancelledError):
        run()
    assert redis.incr_calls == 1


# --- MAJOR-r2-3: an mcp-sql refusal or database error is a tool error -------------------------


def test_09_r2_major3_mcp_sql_refusal_and_db_error_are_tool_errors():
    from mcp.types import CallToolResult

    from ffcore.services import mcp_sql_server

    rows = "n\n3\nrows: 1"
    assert mcp_sql_server.checked(rows) == rows
    for text in ("sql_rejected: sql_not_select (UPDATE)", "sql_error: 42703 (no column nope)"):
        out = mcp_sql_server.checked(text)
        assert isinstance(out, CallToolResult) and out.is_error
        # The exact text, no SDK prefix: the model reads the code and corrects the query.
        assert [c.text for c in out.content] == [text]


def test_09_r2_major3_tool_outcome_carries_the_sql_code(monkeypatch):
    from ffcore.runtime import adapters
    from ffcore.runtime.definition import parse_definition
    from ffcore.services import mcp_client
    from tests.unit.test_06a_definition import MINIMAL

    texts = iter(
        [
            ("sql_error: sql_timeout (exceeded 20 s)", True),
            ("sql_rejected: sql_unknown_table (patients)", True),
            ("upstream says no", True),
            ("n\n3\nrows: 1", False),
        ]
    )

    async def call(*a, **kw):
        text, is_error = next(texts)
        return mcp_client.CallResult(text, False, len(text), is_error, 3)

    monkeypatch.setattr(mcp_client, "call", call)
    binding = adapters.McpBinding(target=None, action="run_sql", needs_approval=False,
                                  max_calls=None, timeout_s=None)  # fmt: skip
    tools = adapters.AgentTools(parse_definition(MINIMAL), {"sql__run_sql": binding}, [])
    codes = [anyio.run(tools.call, "sql__run_sql", {}) for _ in range(4)]
    assert [(o.is_error, o.error_code) for o in codes] == [
        (True, "sql_error"),
        (True, "sql_rejected"),
        (True, None),
        (False, None),
    ]


def test_09_r2_major3_failed_sql_is_not_read_and_the_last_good_one_is():
    bad = [
        _call("c1", "SELECT nope", needs_approval=False),
        _ev("tool_result", tool_call_id="c1", is_error=True, error_code="sql_error"),
    ]
    assert executed_sql(bad) == ([], False)
    good_then_bad = [
        _call("c0", "SELECT good", needs_approval=False),
        _ev("tool_result", tool_call_id="c0", is_error=False, error_code=None),
        *bad,
    ]
    assert executed_sql(good_then_bad)[0][-1] == ("sql", "SELECT good")


def _reread(monkeypatch, *, result=None, raises=None, given=True, bound=True):
    from ffcore.services import mcp_client, mcp_tools

    audits = []

    @asynccontextmanager
    async def scope():
        class _S:
            async def commit(self):
                pass

        yield _S()

    async def is_given(session, run, key):
        return given

    async def bound_action(session, run, key):
        return (SimpleNamespace(), SimpleNamespace(name="run_sql", timeout_s=5)) if bound else None

    async def call(*a, **kw):
        if raises is not None:
            raise raises
        return result

    async def record(session, entry):
        audits.append(entry)

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    monkeypatch.setattr(worker_tick, "sql_tool_given", is_given)
    monkeypatch.setattr(worker_tick, "bound_sql_action", bound_action)
    monkeypatch.setattr(worker_tick, "write_event", record)
    monkeypatch.setattr(mcp_client, "call", call)
    monkeypatch.setattr(mcp_tools, "target_of", lambda tool, settings: "t")
    run = SimpleNamespace(id="r", user_id="u", project_id="p", agent_version_id="v")
    out = anyio.run(worker_tick._sql(None, None), run, "sql", "SELECT 1")
    return out, audits


def test_09_r2_major3_reread_refusal_flagged_as_error_keeps_its_code(monkeypatch):
    refused = SimpleNamespace(is_error=True, text="sql_rejected: sql_not_select (UPDATE)")
    (rows, code), audits = _reread(monkeypatch, result=refused)
    assert (rows, code) == (None, "no_sql_result:sql_rejected")
    assert [a.outcome for a in audits] == ["failure"]


# --- MINOR-r2-1: a thrown ToolCallError on the re-read ------------------------------------------


def test_09_r2_minor1_reread_tool_call_error_is_audited_and_not_run(monkeypatch):
    from ffcore.services.mcp_client import ToolCallError

    (rows, code), audits = _reread(monkeypatch, raises=ToolCallError("tool_timeout"))
    assert (rows, code) == (None, "sql_reread_failed")
    (entry,) = audits
    assert entry.outcome == "failure" and entry.after["error_code"] == "tool_timeout"
    facts = _facts(answer="3", sql=[("sql", "SELECT 3")])
    scores = deterministic_scores(_sql_item(), facts, SQL_CFG, None, "sql_reread_failed")
    r = item_result(_sql_item(), facts, scores, "")
    assert (r.passed, r.note) == (None, "sql_reread_failed")


# --- MINOR-r2-7: the tool of an executed call was removed since ---------------------------------


def test_09_r2_minor7_removed_tool_is_not_run_not_the_agents_failure(monkeypatch):
    (rows, code), audits = _reread(monkeypatch, bound=False)
    assert (rows, code, audits) == (None, "tool_removed", [])
    (rows, code), _ = _reread(monkeypatch, given=False)
    assert code == "no_executed_sql"
    facts = _facts(answer="3", sql=[("sql", "SELECT 3")])
    scores = deterministic_scores(_sql_item(), facts, SQL_CFG, None, "tool_removed")
    r = item_result(_sql_item(), facts, scores, "")
    assert (r.passed, r.note) == (None, "tool_removed")


# --- MINOR-r2-2: lock renewal and release are owner-checked; a lost lock stops the tick ---------


class _EvalRedis:
    """SET NX / GET / EVAL (the two owner-checked scripts) over a dict."""

    def __init__(self, fail_renew=False):
        self.kv, self.fail_renew, self.evals = {}, fail_renew, []

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def eval(self, script, numkeys, key, token, *args):
        self.evals.append("del" if "del" in script else "expire")
        if "expire" in script and self.fail_renew:
            raise ConnectionError("redis blinked")
        if self.kv.get(key) != token:
            return 0
        if "del" in script:
            self.kv.pop(key)
        return 1


def test_09_r2_minor2_lost_lock_stops_the_holder_and_is_released():
    redis = _EvalRedis(fail_renew=True)

    async def go():
        async with worker_tick.exam_lock(redis, "ev", ttl_s=0.06) as held:
            assert held
            await asyncio.sleep(1.0)  # a long judge call

    started = time.monotonic()
    with pytest.raises(worker_tick.LockLost):
        anyio.run(go)
    assert time.monotonic() - started < 0.9  # stopped, not left to run without the lock
    assert redis.evals[-1] == "del" and redis.kv == {}


def test_09_r2_minor2_release_never_deletes_another_holders_lock():
    redis = _EvalRedis()

    async def go():
        async with worker_tick.exam_lock(redis, "ev") as held:
            assert held
            redis.kv[worker_tick.lock_key("ev")] = "someone-else"

    anyio.run(go)
    assert redis.kv == {worker_tick.lock_key("ev"): "someone-else"}


# --- MINOR-r2-3: cancel_waiting locks the approval before the run (as approvals.decide) ---------


def test_09_r2_minor3_cancel_waiting_locks_approval_before_run():
    from ffcore.evaluation import runner

    seen = []

    class _S:
        async def execute(self, stmt):
            seen.append(stmt)
            return SimpleNamespace(all=lambda: [])

        async def scalar(self, stmt):
            seen.append(stmt)
            return None  # the run moved on: nothing else happens

    run = SimpleNamespace(id="r", status="waiting_approval", project_id="p")
    assert (
        anyio.run(lambda: runner.cancel_waiting(_S(), run, "eval_approval_required", close=None))
        is False
    )
    first = seen[0]
    assert first.is_select and first._for_update_arg is not None
    assert first.get_final_froms()[0].name == "approvals"


# --- MINOR-r2-4: some repeats not run → counted apart, exam incomplete ---------------------------


def test_09_r2_minor4_partly_not_run_repeats_mark_the_exam_incomplete():
    from ffcore.evaluation.runner import _dump

    item = _item()
    ran = item_result(item, _facts(), [Score("contains", 1.0, True)], "")
    waited = item_result(
        item, _facts(status="cancelled", error_code="eval_waiting_user", outcome_label=None), [], ""
    )
    combined = combine(item, [{"run_id": f"r{i}", **_dump(r)} for i, r in
                              enumerate([ran, waited, waited])])  # fmt: skip
    assert combined.passed is True
    s = _summary([combined])
    assert s["not_run"] == {"partial:waiting_user": 1} and s["complete"] is False
    assert s["scored"] == 1


# --- MINOR-r2-5: fixes that had no test -----------------------------------------------------------


def test_09_r2_minor5_background_worker_starts_the_listener(monkeypatch):
    from ffcore.guardrails import settings as guard_settings
    from ffcore.runtime import worker
    from ffcore.runtime.contracts import JobClass

    started = []

    async def listen(settings, redis):
        started.append(redis)

    s = SimpleNamespace(database_url=SimpleNamespace(get_secret_value=lambda: "x"),
                        background_window="", background_window_weekends=False,
                        background_window_tz="Europe/Istanbul", llm_slots=1)  # fmt: skip
    monkeypatch.setattr(worker, "get_settings", lambda: s)
    monkeypatch.setattr(worker, "configure_logging", lambda settings: None)
    monkeypatch.setattr(worker.db, "configure", lambda url: None)
    monkeypatch.setattr(guard_settings, "check_egress_ner", lambda *a: None)
    monkeypatch.setattr(worker.tracing, "init_tracing", lambda settings: None)
    monkeypatch.setattr(worker.tracing, "get_client", lambda: None)
    monkeypatch.setattr(worker, "LlmSlots", lambda *a: "slots")
    monkeypatch.setattr(worker, "PromptStore", lambda client: "prompts")
    monkeypatch.setattr(worker.adapters, "context_factory", lambda *a, **kw: None)
    monkeypatch.setattr(worker, "Attempt", lambda *a: None)
    monkeypatch.setattr(worker_tick, "listen_loop", listen)

    async def go(job_class):
        ctx = {"redis": "r"}
        await worker._startup_for(job_class)(ctx)
        task = ctx.get("eval_listener")
        if task is not None:
            await task
        return task is not None

    assert anyio.run(go, JobClass.background) is True and started == ["r"]
    assert anyio.run(go, JobClass.interactive) is False


def test_09_r2_minor5_suite_update_refuses_null_except_agent_id():
    from pydantic import ValidationError

    from ffcore.api.eval_schemas import SuiteUpdate

    assert SuiteUpdate(agent_id=None).agent_id is None
    for field in ("name", "scorers", "pass_threshold", "repeat", "approve_tools"):
        with pytest.raises(ValidationError):
            SuiteUpdate(**{field: None})


def test_09_r2_minor5_dataset_name_must_be_the_projects():
    from ffcore.api.eval import dataset_name_ok

    assert dataset_name_ok("hastane-a.exam-1", "hastane-a")
    for bad in ("hastane-b.exam", "hastane-a.", "hastane-a..x", "hastane-a.Exam",
                "hastane-a./x", "hastane-a.x/../y", "hastane-ax"):  # fmt: skip
        assert not dataset_name_ok(bad, "hastane-a"), bad


# --- MINOR-r2-6: a rubric change is a new Langfuse prompt ----------------------------------------

# The rubric's text by prompt name. Seeding never overwrites an existing prompt (Langfuse owns it
# after the first install), so changing the text needs a new name; this pin makes that visible.
RUBRIC_SHA256 = {
    "eval_judge_rubric_v2": "ac08ab45aa934380f809ed1011bf27686fd9b005c3d1450878ada9d29b464ae3",
}


def test_09_r2_minor6_rubric_change_needs_a_new_prompt_name():
    from ffcore.evaluation import judge

    path = BACKEND / "prompts" / f"{judge.RUBRIC_PROMPT}.md"
    assert path.exists(), judge.RUBRIC_PROMPT
    text = path.read_text(encoding="utf-8")
    assert "<<<QUESTION" in text  # r1 MINOR-1 delimiters are in the seeded text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert RUBRIC_SHA256.get(judge.RUBRIC_PROMPT) == digest, (
        "rubric text changed: give it a new prompt name (and a line here)",
        digest,
    )


def test_09_r2_facts_default_has_no_rejection():
    assert ItemFacts("r", "completed", None, None, "", None, None, None).sql_rejected is False
