"""Exam advancer tick lengths (09-1 r2 MAJOR-r2-2, r5 MAJOR-r5-1). No imports: config uses it.

- TICK_TIMEOUT_S: the arq cron timeout of one tick.
- TICK_MARGIN_S: the tick's own deadline ends this much earlier, so it stops on time instead of
  being cancelled (TICK_BUDGET_S = the deadline after the tick started).
- TICK_OVERHEAD_S: what a tick may spend before its first item (lock, listen, load).
- TICK_PLAN_S: the usable window. A plan up to it can start in a tick; a longer one ends coded
  (`planned_exceeds_tick_budget`, start 422 `eval_plan_exceeds_tick`). EVAL_JUDGE_CALL_S is at
  most this, and a cut counts only after min(LLM_CALL_TIMEOUT_S x calls, TICK_PLAN_S).
"""

TICK_TIMEOUT_S = 600
TICK_MARGIN_S = 30
TICK_OVERHEAD_S = 30
TICK_BUDGET_S = TICK_TIMEOUT_S - TICK_MARGIN_S
TICK_PLAN_S = TICK_BUDGET_S - TICK_OVERHEAD_S
