"""LiteLLM client: every model call of the backend goes through here (brief 01 madde 2, A4).

The backend calls the LiteLLM proxy with one internal key; project and user travel in `user` and
`metadata`. Fallback is explicit (K-01-0004 karar A): the request carries
`fallbacks=["<project>.chat-fallback"]` only when the project has an active `chat-fallback`
model; LiteLLM's global router settings are never written (`/config/update` stores the master key
in plain text). Which deployment answered is read from `x-litellm-model-id`, which the reconciler
sets to our `models.id`; a different id than the requested model's is a `FallbackObserved`.
"""

from dataclasses import dataclass

from ffcore.core.config import Settings


class LiteLLMNotConfigured(RuntimeError):
    """LITELLM_URL or one of its keys is not set; model calls are impossible, not skipped."""


@dataclass(frozen=True)
class LiteLLMSettings:
    url: str
    master_key: str
    internal_key: str

    def __repr__(self) -> str:
        return f"LiteLLMSettings(url={self.url!r}, master_key='***', internal_key='***')"


def litellm_settings(settings: Settings) -> LiteLLMSettings:
    missing = [
        name
        for name, value in (
            ("LITELLM_URL", settings.litellm_url),
            ("LITELLM_MASTER_KEY", settings.litellm_master_key),
            ("LITELLM_INTERNAL_KEY", settings.litellm_internal_key),
        )
        if not value
    ]
    if missing:
        raise LiteLLMNotConfigured(f"not set: {', '.join(missing)}")
    assert settings.litellm_url and settings.litellm_master_key and settings.litellm_internal_key
    return LiteLLMSettings(
        url=settings.litellm_url.rstrip("/"),
        master_key=settings.litellm_master_key.get_secret_value(),
        internal_key=settings.litellm_internal_key.get_secret_value(),
    )
