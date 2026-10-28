"""A recognizer hit. Maps one to one onto Presidio's RecognizerResult (entity_type, start, end,
score) plus the mandatory evidence text, so 08 full can add Presidio/NER without a rename."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    category: str
    start: int
    end: int
    score: float
    # Why it matched, for audits: "checksum valid · context word 'kimlik'". Never the value.
    evidence: str
    value: str

    def overlaps(self, other: "Finding") -> bool:
        return self.start < other.end and other.start < self.end
