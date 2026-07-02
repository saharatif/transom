from mistralai import Mistral
from openai import OpenAI
from ..redaction.pii import redact_and_tokenize
import base64, os, json, logfire

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
    # file bytes, so the local PDF is base64-encoded and wrapped as one.
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()
    ocr_resp = mistral.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{pdf_b64}",
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

TEXT: {clean_text}
"""}]
    )
    raw = resp.choices[0].message.content.replace("```json","").replace("```","")
    return json.loads(raw)
