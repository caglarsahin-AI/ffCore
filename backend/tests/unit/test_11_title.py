"""11-1: a conversation's title is the first 60 characters of its first message (brief 11,
PayCore D6): derived, never asked of a model."""

from ffcore.services.runs_start import TITLE_CHARS, conversation_title


def test_11_title_is_first_60_characters():
    assert TITLE_CHARS == 60
    text = "Hizmet sözleşmesinde fesih bildirim süresi kaç gündür ve hangi şartlarla uygulanır?"
    assert conversation_title(text) == text[:60]
    assert len(conversation_title("x" * 500)) == 60


def test_11_title_short_message_is_kept_whole():
    assert conversation_title("Fesih süresi?") == "Fesih süresi?"


def test_11_title_trims_surrounding_whitespace_and_newlines():
    assert conversation_title("  Fesih\nsüresi?  ") == "Fesih süresi?"
    assert conversation_title(("a" * 59) + " b") == "a" * 59
