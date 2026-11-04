"""Named text filters for ingest (19, C6 additive `text_filter`).

A filter runs on the converted text before silver is written, so silver, gold and everything the
model sees are masked; raw stays byte for byte (plan/19 şart 1, K-M3S-0003). Filters are named,
never callables: the document records `<name>@<version>` and a reindex can tell which rule made
its text.

`pii_regex` reuses 08-lite's checksummed recognizers and redacts each finding to its `[CODE]`
label; person names are not caught by it. `pii_ner` (08 tam 1b) adds person names from the NER
model, asked over HTTP (`POST /api/v1/internal/guardrails/ner`: ingest runs in the worker or the
ingest-raw CLI, never in the API process that holds the model); a regex finding always wins
over an overlapping name. NER unreachable fails the text, it is never written unmasked.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from ffcore.guardrails.masking import redact_label
from ffcore.guardrails.recognizers.regex import recognize

TextFilterName = Literal["pii_regex", "pii_ner"]

# Bump when the categories or recognizers change: the label changes, so does text_hash.
PII_REGEX_VERSION = 1
PII_REGEX_CATEGORIES = ("EMAIL_ADDRESS", "TR_PHONE", "TR_NATIONAL_ID", "TR_IBAN", "CREDIT_CARD")
PII_NER_VERSION = 1
PII_NER_CATEGORIES = ("PERSON",)


def _redact(text: str, findings) -> tuple[str, Counter]:
    counts: Counter = Counter()
    parts, at = [], 0
    for f in sorted(findings, key=lambda f: f.start):
        parts.append(text[at : f.start])
        parts.append(redact_label(f.category))
        counts[f.category] += 1
        at = f.end
    parts.append(text[at:])
    return "".join(parts), counts


def ner_client():
    """The workers' NER: the API process holds the model (08 tam 1b S2)."""
    from ffcore.core.config import get_settings
    from ffcore.guardrails.recognizers.ner import HttpNer

    return HttpNer(get_settings())


@dataclass(frozen=True)
class PiiRegexFilter:
    name: str = "pii_regex"
    version: int = PII_REGEX_VERSION

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

    def apply(self, text: str) -> tuple[str, Counter]:
        """(masked text, findings per category). Counts only: no value leaves this function."""
        return _redact(text, recognize(text, PII_REGEX_CATEGORIES))

    async def mask(self, text: str) -> tuple[str, Counter]:
        return self.apply(text)


@dataclass(frozen=True)
class PiiNerFilter:
    name: str = "pii_ner"
    version: int = PII_NER_VERSION

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

    async def mask(self, text: str) -> tuple[str, Counter]:
        """`pii_regex` plus person names; a name overlapping a regex finding is dropped."""
        base = recognize(text, PII_REGEX_CATEGORIES)
        names = await ner_client().find(text, PII_NER_CATEGORIES) if text.strip() else []
        kept = [n for n in names if not any(n.overlaps(b) for b in base)]
        return _redact(text, [*base, *kept])


TextFilter = PiiRegexFilter | PiiNerFilter
_FILTERS = {"pii_regex": PiiRegexFilter(), "pii_ner": PiiNerFilter()}

# Metadata keys that are identifiers or bookkeeping, not text a person wrote: left as given.
UNMASKED_KEYS = frozenset({"source", "source_item_id", "text_filter"})


async def mask_metadata(f: TextFilter, metadata: dict) -> tuple[dict, Counter]:
    """Every string value (and string in a list) of a C6 metadata mapping through the filter,
    except UNMASKED_KEYS (r1 MAJOR-2: titles, breadcrumbs and links carry e-mail addresses too)."""
    counts: Counter = Counter()

    async def one(value):
        if isinstance(value, str):
            masked, found = await f.mask(value)
            counts.update(found)
            return masked
        if isinstance(value, list):
            return [await one(v) for v in value]
        return value

    return {k: (v if k in UNMASKED_KEYS else await one(v)) for k, v in metadata.items()}, counts


def resolve(name: str) -> TextFilter:
    """The filter registered under `name`; an unknown name is an error, never a pass-through."""
    try:
        return _FILTERS[name]
    except KeyError:
        raise ValueError(f"unknown text filter {name!r} (known: {', '.join(_FILTERS)})") from None
