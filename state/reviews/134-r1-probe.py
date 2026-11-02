"""Reviewer probe for fix/06a-egress-all-messages r1: the REAL guardrail engine (built-in default
policy, in-memory token store) behind graph._egress_messages. No stack needed.
Run in the tools container with the PR worktree mounted at /new."""
import asyncio
import sys
from types import SimpleNamespace

from ffcore.guardrails import engine
from ffcore.guardrails.builtin import BUILTIN_DEFAULT
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.runtime.graph import _egress_messages
from ffcore.runtime.state import GuardResult, StopRun

FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


class RealGuard:
    """The same call EngineGuard.check makes, minus DB/Redis event recording."""

    def __init__(self, policy, store, run_id="run-A"):
        self.policy, self.store, self.run_id, self.calls = policy, store, run_id, 0

    async def check(self, stage, text, *, tool=None):
        self.calls += 1
        ctx = engine.EvalContext(run_id=self.run_id, project_id="p", source="chat", tool=tool,
                                 token_store=self.store, egress_enabled=True)
        d = await engine.evaluate(text, stage, self.policy, ctx=ctx)
        return GuardResult(d.action, d.text_out, d.message, d.reference_id, len(d.events))


def ctxof(guard):
    return SimpleNamespace(guard=guard, egress_cache={})


EMAIL, PHONE = "ali.veli@example.com", "+905321234567"
MSGS = [
    {"role": "system", "content": f"Support contact: {EMAIL}. Be brief."},
    {"role": "user", "content": f"earlier: my phone is {PHONE}"},
    {"role": "assistant", "content": f"noted {PHONE}", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "run_sql", "arguments": f'{{"q": "{EMAIL}"}}'}}]},
    {"role": "tool", "tool_call_id": "c1", "content": f'<tool_result name="run_sql">\nrow: {EMAIL}\n</tool_result>'},
    {"role": "user", "content": "plain question without identifiers"},
]


async def main():
    store = MemoryTokenStore()
    guard = RealGuard(BUILTIN_DEFAULT, store)
    out = await _egress_messages(ctxof(guard), MSGS)
    flat = "\n".join(m.get("content") or "" for m in out)
    check(EMAIL not in flat and PHONE not in flat, "real engine: system/history/assistant/tool text carries no raw e-mail/phone")
    check("<<PII_" in flat, "placeholders present")
    # idempotent on a fresh cache (resume): masked in -> masked out, same tokens
    again = await _egress_messages(ctxof(RealGuard(BUILTIN_DEFAULT, store)), out)
    check(again == out, "idempotent with a fresh cache and the same token store")
    # same value, same token across messages
    check(out[0]["content"].count("<<PII_") == 1 and out[3]["content"].split("row: ")[1].startswith(out[0]["content"].split(": ")[1].split(".")[0][:0] or "<<PII_"), "tool/system share a token for the same e-mail")
    tok_sys = out[0]["content"].split("contact: ")[1].split(".")[0]
    check(tok_sys in out[3]["content"], f"same e-mail -> same token in system and tool ({tok_sys})")
    # tool_calls arguments are NOT touched by egress (the PR relies on tool_guard)
    args = out[2]["tool_calls"][0]["function"]["arguments"]
    print("INFO tool_calls arguments after egress:", args)
    check(EMAIL in args, "NOTE tool_calls.arguments keep the raw value under the default policy (not covered by egress)")
    # input is not mutated
    check(MSGS[0]["content"].startswith("Support contact: ali"), "input list not mutated")
    # cache is per ctx
    c1, c2 = ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore(), "run-B")), ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore(), "run-C"))
    await _egress_messages(c1, [{"role": "user", "content": f"x {EMAIL}"}])
    check(c2.egress_cache == {} and len(c1.egress_cache) == 1, "egress_cache belongs to one context only")
    # placeholder lookalike injected by a tool result is left alone and cannot resolve across runs
    fake = [{"role": "tool", "tool_call_id": "c", "content": "<<PII_1>> from document"}]
    outfake = await _egress_messages(ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore(), "run-D")), fake)
    check(outfake == fake, "lookalike placeholder text unchanged")
    check(await MemoryTokenStore().lookup("run-D", "<<PII_1>>") is None, "lookalike resolves to nothing in a fresh scope")

    # non-str content is skipped silently
    listy = [{"role": "user", "content": [{"type": "text", "text": f"mail {EMAIL}"}]}]
    outl = await _egress_messages(ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore())), listy)
    check(outl == listy, "FINDING-CANDIDATE: list-typed content passes through unchecked (no raise)")

    # oversize text
    big = [{"role": "tool", "tool_call_id": "c", "content": "a" * 200_001}]
    try:
        await _egress_messages(ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore())), big)
        check(False, "oversize message was accepted")
    except StopRun as e:
        check(True, f"oversize -> StopRun {e.code}")
    except Exception as e:  # noqa: BLE001
        print("INFO oversize raised", type(e).__name__, "(not StopRun; runner maps unknown errors to code 'run_error')")
        check(isinstance(e, engine.TextTooLong), "oversize raises TextTooLong (generic run_error at the runner)")

    # enforce policy + secret in a tool result -> block fails the run
    enforce = BUILTIN_DEFAULT.__class__(key="e", spec=BUILTIN_DEFAULT.spec.model_copy(update={"mode": "enforce"}),
                                        pii_policies=BUILTIN_DEFAULT.pii_policies, builtin=False)
    secret = "AKIAIOSFODNN7EXAMPLE"
    try:
        await _egress_messages(ctxof(RealGuard(enforce, MemoryTokenStore())),
                               [{"role": "tool", "tool_call_id": "c", "content": f"key={secret} secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}])
        check(False, "enforce: secret in tool result was not blocked")
    except StopRun as e:
        check(e.code == "guardrail_block", f"enforce: secret in tool result -> StopRun {e.code}")
    # default (monitor) policy: the same secret is only logged, not blocked
    try:
        o = await _egress_messages(ctxof(RealGuard(BUILTIN_DEFAULT, MemoryTokenStore())),
                                   [{"role": "tool", "tool_call_id": "c", "content": f"key={secret}"}])
        print("INFO default (monitor) policy: secret passes unblocked ->", o[0]["content"][:40])
    except StopRun as e:
        print("INFO default policy blocks secrets at egress ->", e.code)

    # user message already egress-checked in guard_in is evaluated AGAIN at the model node
    g = RealGuard(BUILTIN_DEFAULT, MemoryTokenStore())
    first = await g.check("egress", f"hello {EMAIL}")
    n0 = g.calls
    await _egress_messages(ctxof(g), [{"role": "user", "content": first.text}])
    check(g.calls == n0 + 1, "INFO: guard_in's already-masked user message is checked a second time (cache not seeded)")

    print("FAILS:", FAILS)
    return 1 if FAILS else 0


sys.exit(asyncio.run(main()))
