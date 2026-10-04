"""Tests for the shared LLM JSON parser (app.agents.base.parse_json_response)."""

import pytest

from app.agents.base import parse_json_response


def test_plain_json():
    assert parse_json_response('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_code_fenced_json():
    raw = 'Here you go:\n```json\n{"content": "hi"}\n```\nDone.'
    assert parse_json_response(raw) == {"content": "hi"}


def test_bare_fence_without_lang():
    raw = "```\n{\"k\": 2}\n```"
    assert parse_json_response(raw) == {"k": 2}


def test_extracts_outermost_braces_from_prose():
    raw = 'The result is {"score": 90} overall.'
    assert parse_json_response(raw) == {"score": 90}


def test_fullwidth_punctuation_is_normalized():
    # fullwidth comma and fullwidth quotes
    raw = '{\u201ca\u201d: 1\uff0c \u201cb\u201d: 2}'
    assert parse_json_response(raw) == {"a": 1, "b": 2}


def test_trailing_comma_is_tolerated():
    assert parse_json_response('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_fallback_none_raises():
    with pytest.raises(ValueError):
        parse_json_response("not json at all", fallback=None)


def test_dict_fallback_is_deepcopied():
    default = {"issues": [], "nested": {"x": 1}}
    result = parse_json_response("garbage", fallback=default)
    assert result == default
    # mutating the result must not affect the original default
    result["issues"].append("mutated")
    result["nested"]["x"] = 999
    assert default == {"issues": [], "nested": {"x": 1}}


def test_callable_fallback_receives_raw():
    raw = "plain novel text"
    result = parse_json_response(raw, fallback=lambda r: {"content": r.strip()})
    assert result == {"content": "plain novel text"}


def test_repair_truncated_closes_brackets():
    # Truncated mid-array; repair should drop the incomplete tail and close.
    raw = '{"branches": [{"title": "A"}, {"title": "B"'
    result = parse_json_response(raw, repair_truncated=True, fallback={"branches": []})
    assert "branches" in result
    assert isinstance(result["branches"], list)
    assert result["branches"][0] == {"title": "A"}


def test_repair_disabled_uses_fallback():
    raw = '{"branches": [{"title": "A"}, {"title": "B"'
    result = parse_json_response(raw, repair_truncated=False, fallback={"branches": []})
    assert result == {"branches": []}
