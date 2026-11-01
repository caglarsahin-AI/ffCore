"""Named text filters for ingest (19, C6 additive `text_filter`).

A filter runs on the converted text before silver is written, so silver, gold and everything the
model sees are masked; raw stays byte for byte (plan/19 şart 1, K-M3S-0003). Filters are named,
never callables: the document records `<name>@<version>` and a reindex can tell which rule made
its text.

`pii_regex` reuses 08-lite's checksummed recognizers and redacts each finding to its `[CODE]`
label. Person names need NER (08 full) and are not caught: a known limit, written in the runbook.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from ffcore.guardrails.masking import redact_label
from ffcore.guardrails.recognizers.regex import recognize

TextFilterName = Literal["pii_regex"]

# Bump when the categories or recognizers change: the label changes, so does text_hash.
PII_REGEX_VERSION = 1
PII_REGEX_CATEGORIES = ("EMAIL_ADDRESS", "TR_PHONE", "TR_NATIONAL_ID", "TR_IBAN", "CREDIT_CARD")


@dataclass(frozen=True)
class PiiRegexFilter:
    name: str = "pii_regex"
    version: int = PII_REGEX_VERSION

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

    def apply(self, text: str) -> tuple[str, Counter]:
        """(masked text, findings per category). Counts only: no value leaves this function."""
        findings = sorted(recognize(text, PII_REGEX_CATEGORIES), key=lambda f: f.start)
        counts: Counter = Counter()
        parts, at = [], 0
        for f in findings:
            parts.append(text[at : f.start])
            parts.append(redact_label(f.category))
            counts[f.category] += 1
            at = f.end
        parts.append(text[at:])
        return "".join(parts), counts


_FILTERS = {"pii_regex": PiiRegexFilter()}


def resolve(name: str) -> PiiRegexFilter:
    """The filter registered under `name`; an unknown name is an error, never a pass-through."""
    try:
        return _FILTERS[name]
    except KeyError:
        raise ValueError(f"unknown text filter {name!r} (known: {', '.join(_FILTERS)})") from None
