from presidio_analyzer import AnalyzerEngine
import re, sqlite3, uuid
import logfire

# Presidio's analyzer is loaded once at import time (model load is
# expensive) and reused across every call. The replacement step is done
# manually below rather than with presidio_anonymizer: its OperatorConfig
# is keyed per entity TYPE, not per match, so two different PERSON matches
# in one document would both get the last-generated token — collapsing two
# distinct people into one and making de_tokenize() restore the wrong name
# (BUGS.md #28). Splicing tokens into the exact spans the analyzer already
# reported keeps one unique token per match.
analyzer = AnalyzerEngine()

# Entity types we scan for in any text pulled from OCR/Vision before it's
# allowed to touch a downstream LLM, chunker, or embedder.
PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                "US_SSN", "CREDIT_CARD", "US_BANK_NUMBER", "LOCATION"]

# Presidio's phone-number recognizer can misfire on digit-hyphen-digit
# cost ranges (e.g. "4000-9000") when no phone-like context words are
# nearby — it scores these identically to a real, contextless phone
# number (see BUGS.md #13), so a confidence threshold can't tell them
# apart. A currency marker immediately adjacent IS a reliable signal
# though: a real phone number is never directly followed by "USD"/"$"/
# "dollars". This filter only excludes PHONE_NUMBER matches with that
# specific adjacent context — it doesn't touch confidence scoring, so it
# can't suppress real phone number redaction elsewhere.
_CURRENCY_CONTEXT = re.compile(r"^\s*(USD|usd|\$|dollars?)\b")


def _looks_like_currency(text: str, start: int, end: int) -> bool:
    return bool(_CURRENCY_CONTEXT.match(text[end:end + 12]))


def _drop_overlaps(results):
    """Presidio can report overlapping spans for the same stretch of text
    (e.g. a name matched both as PERSON and inside a LOCATION). Splicing
    two tokens into overlapping spans would garble the text, so keep only
    the highest-scoring (ties: longest) match for any overlapping region.
    """
    kept = []
    for r in sorted(results, key=lambda r: (-r.score, -(r.end - r.start))):
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start)


@logfire.instrument()
def redact_and_tokenize(text: str, doc_id: str, db_path: str) -> str:
    """Replace each detected PII span with a unique placeholder token
    (e.g. [PERSON_A1B2C3]) and persist the token -> original value mapping
    so it can be reversed later via de_tokenize(). The LLM/vector store
    only ever sees the tokenized text, never the raw PII.
    """
    results = analyzer.analyze(text=text, entities=PII_ENTITIES, language="en")
    results = [r for r in results
               if not (r.entity_type == "PHONE_NUMBER" and _looks_like_currency(text, r.start, r.end))]
    results = _drop_overlaps(results)

    # Splice tokens in from the end of the text backwards so earlier
    # spans' offsets stay valid as replacements change the string length.
    token_map = {}
    redacted = text
    for r in sorted(results, key=lambda r: r.start, reverse=True):
        # Unique token per match (not just per entity type) so repeated
        # names/emails/etc. in the same doc don't collide.
        token = f"[{r.entity_type}_{uuid.uuid4().hex[:6].upper()}]"
        token_map[token] = (text[r.start:r.end], r.entity_type)
        redacted = redacted[:r.start] + token + redacted[r.end:]

    # Trace how much PII was found, without logging the PII itself.
    logfire.info("pii_detected", count=len(results),
                 types=[r.entity_type for r in results])

    _store_token_map(doc_id, token_map, db_path)
    return redacted


def _store_token_map(doc_id, token_map, db_path):
    """Persist token -> (original value, entity type) pairs for one document
    so de_tokenize() can later restore the original text for that doc_id.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO pii_token_map (doc_id, token, original_value, entity_type) "
            "VALUES (?, ?, ?, ?)",
            [(doc_id, token, original, etype)
             for token, (original, etype) in token_map.items()])
        conn.commit()
    finally:
        conn.close()


@logfire.instrument()
def de_tokenize(text: str, doc_id: str, db_path: str) -> str:
    """Reverse redact_and_tokenize(): swap every placeholder token back to
    its original value using the mapping stored for this doc_id. Used when
    displaying results to an authorized user, not before any LLM call.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT token, original_value FROM pii_token_map WHERE doc_id = ?",
            (doc_id,)).fetchall()
    finally:
        conn.close()
    for token, original in rows:
        text = text.replace(token, original)
    return text
