"""Unit tests for backend/ingestion/llm_json.py — the shared parser for
JSON embedded in LLM text responses.
"""
import pytest

from backend.ingestion.llm_json import parse_llm_json


def test_plain_json_object():
    assert parse_llm_json('{"sqft": 2201}') == {"sqft": 2201}


def test_markdown_fenced_json():
    raw = '```json\n{"bedrooms": 4, "bathrooms": 3}\n```'
    assert parse_llm_json(raw) == {"bedrooms": 4, "bathrooms": 3}


def test_preamble_and_afterword_text():
    raw = 'Here is the extraction you asked for:\n{"sqft": 1500}\nLet me know!'
    assert parse_llm_json(raw) == {"sqft": 1500}


def test_top_level_array():
    raw = 'Sure: [{"category": "Roof replacement", "priority": 1}]'
    assert parse_llm_json(raw) == [{"category": "Roof replacement", "priority": 1}]


def test_braces_inside_string_values():
    raw = '{"note": "cost is {approx} 8000-10000 USD", "priority": 2}'
    assert parse_llm_json(raw)["priority"] == 2


def test_nested_objects():
    raw = 'prefix {"a": {"b": [1, 2, {"c": 3}]}} suffix'
    assert parse_llm_json(raw) == {"a": {"b": [1, 2, {"c": 3}]}}


def test_escaped_quotes_in_strings():
    raw = '{"label": "the \\"master\\" bedroom"}'
    assert parse_llm_json(raw) == {"label": 'the "master" bedroom'}


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_response_raises(raw):
    with pytest.raises(ValueError, match="empty"):
        parse_llm_json(raw)


def test_no_json_raises_with_snippet():
    with pytest.raises(ValueError, match="No JSON found"):
        parse_llm_json("I could not read the document, sorry.")


def test_unbalanced_json_raises():
    with pytest.raises(ValueError, match="Unbalanced"):
        parse_llm_json('{"sqft": 2201')


def test_malformed_json_raises():
    with pytest.raises(ValueError, match="Malformed"):
        parse_llm_json("{'sqft': 2201}")  # single quotes aren't JSON
