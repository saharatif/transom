from mistralai import Mistral
from openai import OpenAI
from .llm_json import parse_llm_json
from ..redaction.pii import redact_and_tokenize
import base64, mimetypes, os, logfire

# Both clients read their API key from the environment at construction
# time, which happens at import time (module-level). Whatever imports this
# module must load .env first — see backend/main.py's import ordering.
mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
openai_client = OpenAI()

@logfire.instrument()
def process_blueprint(pdf_path: str, property_id: str, doc_id: str, db_path: str):
    """Extract structured fields from a blueprint PDF: OCR the raw text
    (unavoidable external API exposure), redact any PII immediately, then
    ask GPT-4o for the known, fixed set of fields (sqft, rooms, layout).
    This is structured extraction, not RAG — the questions we'll ask
    about a blueprint are known in advance.
    """
    # 1. OCR (unavoidable — external API sees raw). The OCR endpoint only
    # accepts a document_url (a hosted URL or a base64 data URI), not raw
    # file bytes, so the local file is base64-encoded and wrapped as one.
    # The mime type should match the actual file (image/png, image/jpeg,
    # application/pdf, ...) rather than always assuming PDF — this was
    # previously hardcoded to application/pdf even for image uploads.
    # (Investigated as the cause of a bedroom/bathroom count discrepancy;
    # turned out OCR text was identical either way for that file — see
    # BUGS.md #21 for the actual cause — but this was still a real
    # correctness bug worth fixing on its own.)
    mime_type, _ = mimetypes.guess_type(pdf_path)
    mime_type = mime_type or "application/pdf"
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()
    ocr_resp = mistral.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:{mime_type};base64,{pdf_b64}",
        })
    # OCRResponse has no single .text field — text comes back per-page as
    # markdown, so join all pages into one string for downstream extraction.
    raw_text = "\n\n".join(page.markdown for page in ocr_resp.pages)

    # 2. Redact IMMEDIATELY after OCR — no storage/logging of raw_text
    # before this point.
    clean_text = redact_and_tokenize(raw_text, doc_id, db_path)

    # 3. Extract the known, fixed set of fields from the clean text. A
    # blueprint's questions (sqft, room count, layout) are known in
    # advance, so this is structured extraction rather than open-ended RAG.
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"""
Extract from this blueprint text. Return ONLY JSON:
{{"sqft": number, "bedrooms": number, "bathrooms": number,
  "rooms": ["..."], "layout_type": "..."}}

A multi-story home's blueprint set usually splits rooms across sheets
(e.g. a "Ground Floor" sheet and an "Upper Floor" sheet), each covering
only some of the home's total rooms. When a sheet's title block labels
rooms with ordinal numbers, like "BEDROOMS 3 & 4 + BATH 3", those are
room numbers in the whole home's numbering sequence, not a count of how
many rooms appear on this one sheet — "BEDROOMS 3 & 4" means this sheet
depicts bedroom #3 and bedroom #4 (out of a larger total, at least 4),
not "there are 2 bedrooms here". In that case, set "bedrooms" and
"bathrooms" to the HIGHEST room number mentioned (e.g. 4 bedrooms, 3
bathrooms for "BEDROOMS 3 & 4 + BATH 3"), not a literal count of the
listed items. If the text has no such ordinal-numbered labels, count
rooms normally from what's listed.

IMPORTANT: if this sheet doesn't mention bedrooms or bathrooms at ALL
(e.g. a Ground Floor sheet showing only living areas, garage, kitchen),
set "bedrooms"/"bathrooms" to null — do NOT set them to 0. This is a
partial sheet, not a home with zero bedrooms; null means "not on this
sheet" so a caller merging data from multiple sheets doesn't overwrite
a real count from another sheet with a false zero. Same for "sqft": use
null, not 0, if this sheet doesn't state a square footage figure.

TEXT: {clean_text}
"""}]
    )
    return parse_llm_json(resp.choices[0].message.content)
