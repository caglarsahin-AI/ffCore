"""05b S1 (KARARLAR "05b plan kararları"): a published server's guardrail_mode may make its
policy stricter, never looser. Effective mode of each rule = max(server mode, rule mode) with
off < monitor < enforce; the policy itself is never weakened."""

import pytest

from ffcore.guardrails.engine import rule_mode
from ffcore.guardrails.schemas import PolicySpec, ResolvedPolicy, Rule
from ffcore.services.mcp_publish import effective_policy

ARGS = {"tools": ["*"], "patterns": ["DROP"]}


def _policy(mode: str, rule_modes: list[str | None]) -> ResolvedPolicy:
    rules = [
        Rule(type="tool_args", action="block", stages=["tool.pre"], params=ARGS, mode=m)
        for m in rule_modes
    ]
    return ResolvedPolicy(key="p", spec=PolicySpec(mode=mode, rules=rules))


def _modes(policy: ResolvedPolicy) -> tuple[str, list[str]]:
    spec = policy.spec
    return spec.mode, [rule_mode(spec, r) for r in spec.rules]


@pytest.mark.parametrize(
    "server, policy_mode, rules, expected",
    [
        # off adds nothing: the policy runs as it is (a server cannot switch a policy off).
        ("off", "enforce", [None], ("enforce", ["enforce"])),
        ("off", "monitor", [None, "enforce"], ("monitor", ["monitor", "enforce"])),
        ("off", "off", [None], ("off", ["off"])),
        # monitor: an off policy still logs; enforce stays enforce.
        ("monitor", "off", [None], ("monitor", ["monitor"])),
        ("monitor", "enforce", [None, "monitor"], ("enforce", ["enforce", "monitor"])),
        # enforce: every rule enforces.
        ("enforce", "monitor", [None, "monitor"], ("enforce", ["enforce", "enforce"])),
        ("enforce", "off", [None], ("enforce", ["enforce"])),
    ],
)
def test_05b_server_mode_only_tightens(server, policy_mode, rules, expected):
    policy = _policy(policy_mode, rules)
    assert _modes(effective_policy(policy, server)) == expected
    # The stored policy object is not changed.
    assert policy.spec.mode == policy_mode


def test_05b_unknown_server_mode_fails_loud():
    with pytest.raises(ValueError):
        effective_policy(_policy("monitor", [None]), "auto")
