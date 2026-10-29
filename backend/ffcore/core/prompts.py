"""Prompts from Langfuse prompt management (package 02, brief madde 5).

A prompt is fetched by name and label (`production`) and cached for 60 s. If Langfuse cannot
be reached, the last good copy is served and `prompt_cache_stale` is logged; with no copy at all
the call fails (`prompt_unavailable`), never a silent local fallback (C13). The SDK's own cache
is switched off so that serving a stale copy is always said: it refreshes in the background and
returns stale copies without telling.

backend/prompts/*.md are only the first-install seed (`make seed-prompts`).
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ffcore.core.errors import ApiError

log = logging.getLogger("ffcore.prompts")

DEFAULT_LABEL = "production"
TTL_S = 60


class PromptUnavailable(ApiError):
    def __init__(self, name: str, reason: str) -> None:
        super().__init__(503, "api_error", "prompt_unavailable", f"Prompt {name} is not available.")
        self.reason = reason


@dataclass
class PromptStore:
    client: Any
    ttl_s: float = TTL_S
    clock: Callable[[], float] = time.monotonic
    _cache: dict[tuple[str, str], tuple[Any, float]] = field(default_factory=dict)

    def get(self, name: str, label: str = DEFAULT_LABEL) -> Any:
        if self.client is None:
            raise PromptUnavailable(name, "tracing_off")
        key = (name, label)
        cached = self._cache.get(key)
        if cached is not None and self.clock() - cached[1] < self.ttl_s:
            return cached[0]
        try:
            prompt = self.client.get_prompt(name, label=label, cache_ttl_seconds=0)
        except Exception as exc:  # noqa: BLE001 - every failure is either stale or loud
            if cached is not None:
                log.warning(
                    "prompt_cache_stale name=%s label=%s error=%s",
                    name,
                    label,
                    type(exc).__name__,
                )
                return cached[0]
            log.error(
                "prompt_unavailable name=%s label=%s error=%s", name, label, type(exc).__name__
            )
            raise PromptUnavailable(name, type(exc).__name__) from None
        self._cache[key] = (prompt, self.clock())
        return prompt


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)


def seed_prompts(client: Any, directory: Path) -> SeedReport:
    """Each <name>.md becomes prompt <name> with label production, unless it already exists:
    after the first install Langfuse owns the prompts."""
    if client is None:
        raise PromptUnavailable("*", "tracing_off")
    report = SeedReport()
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        name = path.stem
        try:
            client.get_prompt(name, label=DEFAULT_LABEL, cache_ttl_seconds=0)
            report.existing.append(name)
            continue
        except Exception:  # noqa: BLE001 - not found (or unreachable: create fails loud)
            pass
        client.create_prompt(
            name=name, prompt=path.read_text(encoding="utf-8"), labels=[DEFAULT_LABEL]
        )
        report.created.append(name)
    return report
