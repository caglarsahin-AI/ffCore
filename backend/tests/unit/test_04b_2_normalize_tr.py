"""04b-2 slice 3, D3 (K-04B-0002 S3 A, K1): TEXT_NORMALIZE_TR is off by default. On, it adds
PayCore's deterministic layer A on top of format cleanup: circumflexes are folded (kâr → kar,
hâlâ → hala, Â → A, Î → İ), in silver and in every query alike. Code (fenced and inline) and URLs
are content in their exact form and stay. The configuration id says which form a text is in."""

import pytest

from ffcore.core.config import Settings
from ffcore.knowledge.normalize import clean_markdown, normalize_query, normalizer_config_id
from tests.dummy import SETTINGS_03A

TEXT = (
    "Şirketin kâr payı hâlâ ödenmedi; Âdem Îzmir'de. Kod: `kâr()` ve https://x.tr/kâr"
    "\n\n```\nhâlâ = 1\n```"
)


def _settings(**extra) -> Settings:
    return Settings(deploy_profile="airgap", offline=True, **SETTINGS_03A, **extra)


def test_04b_2_d3_default_is_off_and_format_only():
    settings = _settings()
    assert settings.text_normalize_tr is False
    assert normalizer_config_id(settings) == "format-v1"
    assert "kâr payı hâlâ" in clean_markdown(TEXT)


def test_04b_2_d3_on_folds_circumflex_outside_code_and_urls():
    settings = _settings(text_normalize_tr=True)
    assert normalizer_config_id(settings) == "format-v1+tr-a1"
    out = clean_markdown(TEXT, turkish=True)
    assert "kar payı hala ödenmedi; Adem İzmir'de." in out
    assert "`kâr()`" in out and "https://x.tr/kâr" in out
    assert "```\nhâlâ = 1\n```" in out


@pytest.mark.parametrize(("query", "folded"), [("kâr payı", "kar payı"), ("HÂLÂ", "HALA")])
def test_04b_2_d3_query_meets_silver_in_one_form(query, folded):
    assert normalize_query(query, turkish=True) == folded
    assert normalize_query(query) == query
