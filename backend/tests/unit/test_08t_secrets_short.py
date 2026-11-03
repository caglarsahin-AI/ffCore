"""08-tam-1a, FOLLOWUP-106: tokens of 13-23 characters are under the entropy rule's length floor
(ENTROPY_MIN_CHARS = 24; random upper-case 2x6 and 3x6 were caught 0 % in the 08 r3
measurement, state/reviews/08-entropy-probe-short.py). They are caught when a credential word
names them (`API_KEY=`, `Authorization: Bearer`, `token:`, `secret`); without such a word they
stay as before, so names, codes and words are not taken for keys."""

import random
import string

import pytest

from ffcore.guardrails.rules import ENTROPY_MIN_CHARS, find_secrets

U, L, D = string.ascii_uppercase, string.ascii_lowercase, string.digits
N = 2000


def _rnd(rng, alphabet, n):
    return "".join(rng.choice(alphabet) for _ in range(n))


SHAPES = {
    "upper 2x6": lambda r: "_".join(_rnd(r, U, 6) for _ in range(2)),
    "upper 3x6": lambda r: "-".join(_rnd(r, U, 6) for _ in range(3)),
    "upper 16": lambda r: _rnd(r, U, 16),
    "mixed 14": lambda r: _rnd(r, U + L + D, 14),
    "upper+digits 20": lambda r: _rnd(r, U + D, 20),
}

CONTEXTS = (
    "API_KEY={}",
    "api-key: {}",
    "Authorization: Bearer {}",
    "authorization: {}",
    "token: {}",
    'access_key = "{}"',
    "client_secret={}",
    "the secret is {}",
    "erişim anahtarı: {}",
)
# Measured floor per shape (seed 106, N=2000). Upper 2x6 stays near 95 %: about one random
# 6-letter pair in twenty reads as two words (>= 30 % vowels, no 3 consonants) and keeps the
# plain-identifier exemption, which names and codes need; docs/guardrail.md has the table.
FLOOR = {"upper 2x6": 0.94}


def _caught(text):
    return any(f.category == "API_TOKEN" for f in find_secrets(text))


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_08t_11_short_token_with_credential_word_caught(shape):
    rng = random.Random(106)
    caught = 0
    for i in range(N):
        value = SHAPES[shape](rng)
        assert 13 <= len(value) < ENTROPY_MIN_CHARS
        caught += _caught(CONTEXTS[i % len(CONTEXTS)].format(value))
    assert caught / N >= FLOOR.get(shape, 0.99), (shape, caught / N)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_08t_11_short_token_without_context_unchanged(shape):
    # No credential word: the same values are not findings (the rule is bound to its context).
    rng = random.Random(107)
    texts = [f"Kayıt {SHAPES[shape](rng)} olarak işlendi." for _ in range(200)]
    assert sum(_caught(t) for t in texts) == 0


@pytest.mark.parametrize(
    "text",
    [
        "token: PRSIM-1234",
        "API key: SZL-2025-003_temizlik",
        "Authorization: required for this endpoint",
        "token: authentication",
        "secret: KONFIDENSIYEL",
        "erişim anahtarı: KULLANICI-ADI",
        "the token expired yesterday",
        "API_KEY=ankara-istanbul",
        "token: 1234567890123",
    ],
)
def test_08t_11_credential_word_with_plain_value_not_caught(text):
    assert not _caught(text), text


def test_08t_11_finding_covers_the_value_only():
    text = "Authorization: Bearer QWERTYUIOPASDF"
    (finding,) = [f for f in find_secrets(text) if f.category == "API_TOKEN"]
    assert text[finding.start : finding.end] == "QWERTYUIOPASDF"
    assert "credential word" in finding.evidence
    assert "QWERTYUIOPASDF" not in finding.evidence
