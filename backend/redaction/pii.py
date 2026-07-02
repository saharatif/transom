from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import sqlite3, uuid
import logfire

# Presidio engines are loaded once at import time (model load is expensive)
# and reused across every call.
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Entity types we scan for in any text pulled from OCR/Vision before it's
# allowed to touch a downstream LLM, chunker, or embedder.
PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                "US_SSN", "CREDIT_CARD", "US_BANK_NUMBER", "LOCATION"]


@logfire.instrument()
def redact_and_tokenize(text: str, doc_id: str, db_path: str) -> str:
    """Replace each detected PII span with a unique placeholder token
    (e.g. [PERSON_A1B2C3]) and persist the token -> original value mapping
    so it can be reversed later via de_tokenize(). The LLM/vector store
    only ever sees the tokenized text, never the raw PII.
    """
    results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")

    token_map = {}
    operators = {}
    for r in results:
        # Unique token per match (not just per entity type) so repeated
        # names/emails/etc. in the same doc don't collide.
        token = f"[{r.entity_type}_{uuid.uuid4().hex[:6].upper()}]"
        original = text[r.start:r.end]
        token_map[token] = (original, r.entity_type)
        operators[r.entity_type] = OperatorConfig("replace", {"new_value": token})

    # Trace how much PII was found, without logging the PII itself.
    logfire.info("pii_detected", count=len(results),
                 types=[r.entity_type for r in results])

    anonymized = anonymizer.anonymize(
        text=text, analyzer_results=results, operators=operators)

    _store_token_map(doc_id, token_map, db_path)
    return anonymized.text


def _store_token_map(doc_id, token_map, db_path):
    """Persist token -> (original value, entity type) pairs for one document
    so de_tokenize() can later restore the original text for that doc_id.
    """
    conn = sqlite3.connect(db_path)
    for token, (original, etype) in token_map.items():
        conn.execute(
            "INSERT INTO pii_token_map (doc_id, token, original_value, entity_type) "
            "VALUES (?, ?, ?, ?)", (doc_id, token, original, etype))
    conn.commit()
    conn.close()


@logfire.instrument()
def de_tokenize(text: str, doc_id: str, db_path: str) -> str:
    """Reverse redact_and_tokenize(): swap every placeholder token back to
    its original value using the mapping stored for this doc_id. Used when
    displaying results to an authorized user, not before any LLM call.
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT token, original_value FROM pii_token_map WHERE doc_id = ?",
        (doc_id,)).fetchall()
    conn.close()
    for token, original in rows:
        text = text.replace(token, original)
    return text
