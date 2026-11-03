"""08-tam-1a r1 MAJOR-4: the credential-word patterns (`_SHORT_TOKEN`, 106, and the older
`_ASSIGNMENT`) split whitespace between two `\\s*` around an optional group, so a credential word
followed by many spaces backtracked quadratically (token + 20,000 spaces: 43 s). The linear form
`(?:\\s*(?:[:=]|is))?\\s*` matches the same spans (checked on 3,000 random samples)."""

import random
import re
import subprocess
import sys

import pytest

from ffcore.guardrails import rules

# The patterns as they were (fb7130d), kept here only to prove the new ones match the same.
OLD_SHORT = re.compile(
    r"(?i)\b(?P<word>" + rules._CREDENTIAL_WORD + r")\b[\"']?\s*(?:[:=]|\bis\b)?\s*[\"']?"
    r"(?:(?:bearer|basic)\s+)?"
    r"(?P<value>[A-Za-z0-9_\-+/=]{13,23})(?![A-Za-z0-9_\-+/=])"
)
OLD_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passwd|pwd|şifre(?:m|si|niz)?|parola(?:m|sı)?)\b\s*(?:[:=]|is)?\s*"
    r"(?P<value>[^\s,;]{6,})"
)


def _finishes_within(seconds, text_expr):
    """`find_secrets` on the text in a child process, killed after `seconds`: `re` holds the GIL,
    so a thread with a timeout could not stop a backtracking match."""
    code = f"from ffcore.guardrails import rules; rules.find_secrets({text_expr})"
    try:
        subprocess.run([sys.executable, "-c", code], check=True, timeout=seconds)
    except subprocess.TimeoutExpired:
        return False
    return True


@pytest.mark.parametrize("word", ["token", "password", "API_KEY", "secret", "şifre"])
def test_08t_m4_many_spaces_after_a_credential_word_is_linear(word):
    # 200,000 spaces; the quadratic form needed 43 s for 20,000. Process start is in the budget.
    assert _finishes_within(10, f"{word!r} + ' ' * 200_000 + '!'"), word


def test_08t_m4_repeated_words_under_the_text_limit_is_linear():
    # 180,000 characters (MAX_TEXT_CHARS 200,000); the quadratic form needed 58.8 s.
    assert _finishes_within(10, "('token' + ' ' * 3000 + 'x ') * 60")


def _sample(rng):
    words = ["token", "Token:", "API_KEY", "password", "pwd", "secret", "bearer", "şifre"]
    seps = ["", " ", "   ", ":", " : ", "=", " = ", " is ", "is", "\t", ' "', "'", ": Bearer "]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-+/="
    value = "".join(rng.choice(alphabet) for _ in range(rng.randint(4, 30)))
    return (
        "x "
        + rng.choice(words)
        + rng.choice(seps)
        + rng.choice(seps)
        + value
        + rng.choice(["", " end", ",", ")", "\n"])
    )


def _spans(pattern, text):
    return [(m.span("value")) for m in pattern.finditer(text)]


def test_08t_m4_linear_patterns_match_the_same_spans():
    rng = random.Random(4)
    for _ in range(3000):
        text = _sample(rng)
        assert _spans(rules._SHORT_TOKEN, text) == _spans(OLD_SHORT, text), text
        assert _spans(rules._ASSIGNMENT, text) == _spans(OLD_ASSIGNMENT, text), text
