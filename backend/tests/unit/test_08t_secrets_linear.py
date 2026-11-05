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


# FOLLOWUP-168 NOTE-5 (KARARLAR "Birim testinde mutlak süre sınırı yok"): linearity is proven by
# the CPU-time ratio of two input sizes, 4x apart (a quadratic pattern gives about 16); the child
# process limit is only a wide guard against hanging (the 2 s wall-clock bound failed under load).
RATIO_LIMIT = 8.0
HANG_GUARD_S = 120
CALLS = 5  # per measurement, so the small input is well above the timer's resolution


def _cpu_seconds(text_expr):
    """Best of three CPU times of `find_secrets` on the text, measured in a child process (process
    start and imports stay out of it; `re` holds the GIL, so only a process can be killed if the
    pattern backtracks)."""
    code = (
        "import time; from ffcore.guardrails import rules; "
        f"t = {text_expr}; best = None\n"
        "for _ in range(3):\n"
        "    s = time.process_time()\n"
        f"    for _ in range({CALLS}): rules.find_secrets(t)\n"
        "    d = time.process_time() - s; best = d if best is None else min(best, d)\n"
        "print(best)"
    )
    try:
        done = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            timeout=HANG_GUARD_S,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"find_secrets did not finish within {HANG_GUARD_S} s: {text_expr}")
    return float(done.stdout.strip())


def _ratio(small_expr, large_expr):
    return _cpu_seconds(large_expr) / max(_cpu_seconds(small_expr), 1e-3)


@pytest.mark.parametrize("word", ["token", "password", "API_KEY", "secret", "şifre"])
def test_08t_m4_many_spaces_after_a_credential_word_is_linear(word):
    # 50,000 vs 200,000 spaces; the quadratic form needed 43 s for 20,000.
    ratio = _ratio(f"{word!r} + ' ' * 50_000 + '!'", f"{word!r} + ' ' * 200_000 + '!'")
    assert ratio < RATIO_LIMIT, (word, ratio)


def test_08t_m4_repeated_words_under_the_text_limit_is_linear():
    # 45,000 vs 180,000 characters (MAX_TEXT_CHARS 200,000); the quadratic form needed 58.8 s.
    ratio = _ratio("('token' + ' ' * 3000 + 'x ') * 15", "('token' + ' ' * 3000 + 'x ') * 60")
    assert ratio < RATIO_LIMIT, ratio


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
