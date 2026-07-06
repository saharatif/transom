"""Unit tests for backend/redaction/pii.py. The round-trip tests with two
distinct people are the regression test for BUGS.md #28 — the old
anonymizer-based replacement collapsed all matches of one entity type
into a single (last-generated) token, so de-tokenization restored the
wrong person's name.

These load Presidio + the spaCy model, so this file is the slow part of
the suite (~10s import).
"""
import pytest

from backend.redaction.pii import de_tokenize, redact_and_tokenize


@pytest.fixture
def doc(temp_db):
    return "test-doc-1", temp_db


def test_round_trip_single_person(doc):
    doc_id, db = doc
    text = "The inspection was performed by John Smith on site."
    redacted = redact_and_tokenize(text, doc_id, db)
    assert "John Smith" not in redacted
    assert "[PERSON_" in redacted
    assert de_tokenize(redacted, doc_id, db) == text


def test_two_people_get_distinct_tokens_and_restore_correctly(doc):
    # BUGS.md #28 regression: both names must come back as themselves,
    # not both as the second name.
    doc_id, db = doc
    text = "Inspector John Smith met the owner, Mary Johnson, at the property."
    redacted = redact_and_tokenize(text, doc_id, db)
    assert "John Smith" not in redacted
    assert "Mary Johnson" not in redacted
    person_tokens = [t for t in redacted.split() if t.startswith("[PERSON_")]
    assert len(set(person_tokens)) == len(person_tokens)  # all unique
    assert de_tokenize(redacted, doc_id, db) == text


def test_email_and_phone_redacted(doc):
    doc_id, db = doc
    text = "Contact Jane Doe at jane.doe@example.com or 214-306-7611."
    redacted = redact_and_tokenize(text, doc_id, db)
    assert "jane.doe@example.com" not in redacted
    assert "214-306-7611" not in redacted
    assert de_tokenize(redacted, doc_id, db) == text


def test_currency_range_not_treated_as_phone_number(doc):
    # BUGS.md #13/#26: digit-hyphen-digit cost ranges with an adjacent
    # currency marker must survive redaction untouched.
    doc_id, db = doc
    text = "Est. cost: 8000-10000 USD for the roof, 4000-9000 dollars for flooring."
    redacted = redact_and_tokenize(text, doc_id, db)
    assert "8000-10000 USD" in redacted
    assert "4000-9000 dollars" in redacted


def test_no_pii_text_unchanged(doc):
    doc_id, db = doc
    text = "The drywall crack measures 1/8 inch across the hallway ceiling."
    assert redact_and_tokenize(text, doc_id, db) == text
