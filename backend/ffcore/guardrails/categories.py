"""Value lists of the guardrail engine: stages, actions and the canonical PII categories.

CONTRACTS C4 freezes STAGES (names and order) and ACTIONS (`action_taken`) when 08 merges.
CATEGORIES is the single canonical list of PII category codes (FOLLOWUP-33, KARARLAR
"08-lite kararları"): English, Presidio-compatible names; the 13a set uses the same codes.
"""

from dataclasses import dataclass

# C4: names and order are frozen; a new stage is additive.
STAGES = (
    "prompt.pre",
    "input.pre",
    "output.pre",
    "output.stream.delta",
    "tool.pre",
    "tool.post",
    "egress",
)
# C4 `action_taken`. A Decision may also be `allow` (nothing found, or monitor mode).
ACTIONS = ("block", "redact", "mask", "tokenize", "warn", "log")
DECISION_ACTIONS = ("allow", *ACTIONS)
TRANSFORMING_ACTIONS = ("redact", "mask", "tokenize")
# Severity of an action when a chain combines rules: the highest wins, earlier rule on a tie.
ACTION_RANK = {"allow": 0, "log": 1, "warn": 2, "redact": 3, "mask": 3, "tokenize": 3, "block": 4}

EVENT_STATUSES = ("passed", "redacted", "failed")
EVENT_SOURCES = ("agent-playground", "chat", "api", "channel")
SEVERITIES = ("low", "medium", "high")
MODES = ("off", "monitor", "enforce")
ON_ERROR = ("block", "allow")
LANGUAGES = ("tr", "en")


@dataclass(frozen=True)
class Category:
    code: str
    label: str
    # On in the built-in default PII policy (brief 08 "Varsayılan açık"), when recognizable.
    default_on: bool
    # A built-in regex recognizer exists in 08-lite. Others need a custom pattern (or 08 full).
    regex: bool


_ROWS = (
    ("TR_NATIONAL_ID", "Turkish national ID (TC)", True, True),
    ("TR_PHONE", "Turkish phone number", True, True),
    ("TR_IBAN", "Turkish IBAN", True, True),
    ("TR_TAX_ID", "Turkish tax number (VKN)", False, False),
    ("TR_PLATE", "Turkish licence plate", False, False),
    ("TR_PASSPORT", "Turkish passport number", False, False),
    ("TR_ADDRESS", "Turkish address", False, False),
    ("PERSON", "Person name", False, False),
    ("ORGANIZATION", "Organization name", False, False),
    ("LOCATION", "Location", False, False),
    ("EMAIL_ADDRESS", "E-mail address", True, True),
    ("CREDIT_CARD", "Card number", True, True),
    ("CVV", "Card security code", True, False),
    ("PIN", "PIN", True, False),
    ("GPS", "GPS coordinates", False, False),
    ("MAC_ADDRESS", "MAC address", False, False),
    ("API_TOKEN", "API token", False, False),
    ("PASSWORD", "Password", False, False),
    ("DATE_OF_BIRTH", "Date of birth", False, False),
)

CATEGORIES: dict[str, Category] = {row[0]: Category(*row) for row in _ROWS}
REGEX_CATEGORIES = tuple(code for code, cat in CATEGORIES.items() if cat.regex)
