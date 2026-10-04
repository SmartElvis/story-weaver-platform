"""Tests for the jieba token-cleaning helpers in vector_store.

These guard against the "no operand in tsquery" Postgres error that occurred
when punctuation/whitespace tokens from jieba were passed to to_tsquery.
"""

from app.services.text_utils import build_tsquery, tokenize


def test_tokenize_drops_punctuation_and_whitespace():
    tokens = tokenize("畢文中是個很有性格的人，三十多了……\n")
    assert "，" not in tokens
    assert "……" not in tokens
    assert "\n" not in tokens
    assert " " not in tokens
    # Real words survive.
    assert "畢文中" in tokens or "文中" in tokens


def test_tokenize_keeps_alphanumeric():
    tokens = tokenize("Python 3.11 版本")
    assert "Python" in tokens
    assert "3.11" in tokens


def test_tokenize_empty_for_pure_punctuation():
    assert tokenize("，。！？……\n") == []


def test_build_tsquery_joins_with_or():
    q = build_tsquery("圍城 沈洛珊")
    assert " | " in q
    # No punctuation operands present.
    assert "，" not in q
    assert "\n" not in q


def test_build_tsquery_empty_when_no_word_tokens():
    assert build_tsquery("，。！？……") == ""
