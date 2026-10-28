"""CONTRACTS C1: "<project_key>.<model_key>" and "agent:<project_key>/<agent_key>" split one way."""

import re

import pytest
from pydantic import TypeAdapter, ValidationError

from ffcore.api.schemas import MODEL_KEY_PATTERN, PROJECT_KEY_PATTERN, ModelKey, ProjectKey
from ffcore.models.catalog import MODEL_KEY_REGEX, litellm_name
from ffcore.models.identity import PROJECT_KEY_REGEX

project_key = TypeAdapter(ProjectKey)
model_key = TypeAdapter(ModelKey)


def test_c1_api_and_database_patterns_agree():
    assert PROJECT_KEY_PATTERN == PROJECT_KEY_REGEX
    assert MODEL_KEY_PATTERN == MODEL_KEY_REGEX


@pytest.mark.parametrize("bad", ["", "a", "Hastane", "has.tane", "has/tane", "has:tane", "1abc"])
def test_c1_project_key_rejects_separators_and_bad_forms(bad):
    with pytest.raises(ValidationError):
        project_key.validate_python(bad)


@pytest.mark.parametrize("bad", ["", "chat.default", "chat/default", "chat:default", "Chat"])
def test_c1_model_key_rejects_separators(bad):
    with pytest.raises(ValidationError):
        model_key.validate_python(bad)


def test_c1_litellm_name_splits_back():
    name = litellm_name(project_key.validate_python("hastane"), model_key.validate_python("chat"))
    assert name == "hastane.chat"
    assert name.split(".") == ["hastane", "chat"]


def test_c1_agent_name_splits_back():
    agent = f"agent:{project_key.validate_python('hastane')}/doc-assistant"
    assert re.fullmatch(r"agent:([^/:.]+)/(.+)", agent).groups() == ("hastane", "doc-assistant")
