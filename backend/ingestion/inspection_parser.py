import base64, json, os
import fitz  # PyMuPDF
from openai import OpenAI
from ..redaction.pii import redact_and_tokenize
import logfire

# Reads OPENAI_API_KEY from the environment at construction time, which
# happens at import time — whatever imports this module must load .env
# first (see backend/main.py's import ordering).
openai_client = OpenAI()

# The inspection form has fixed, known checkbox fields — this is a parser,
# not RAG. Unlike blueprint_agent.py, this uses GPT-4o Vision directly on
# rendered page images rather than Mistral OCR text: OCR's text/markdown
# conversion drops which checkbox is marked (it just lists all the option
# labels as plain text, checked or not), so a text-only pipeline can't tell
# what was actually selected. A vision model can see the checkmarks.

def _pdf_pages_to_base64_images(pdf_path: str, zoom: float = 2.0) -> list[str]:
    """Render each page of a PDF to a PNG and return as base64 strings.
    zoom=2.0 roughly doubles the default ~72 DPI render, which makes small
    handwritten checkmarks legible to the vision model.
    """
    doc = fitz.open(pdf_path)
    images = []
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    doc.close()
    return images


@logfire.instrument()
def parse_inspection_form(pdf_path: str, property_id: str, doc_id: str, db_path: str):
    """Render the filled inspection form to page images, send all pages to
    GPT-4o Vision in one call to read the checked boxes and handwritten
    values, then redact any PII (inspector name, license no.) in the JSON
    output before it's stored.
    """
    # 1. Render pages as images. Like image_agent.py, the raw form
    # unavoidably reaches Vision as-is — Presidio only redacts text, and
    # there's no OCR text step here to redact before the API call.
    page_images = _pdf_pages_to_base64_images(pdf_path)

    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
        for img in page_images
    ]
    content.append({"type": "text", "text": """
This is a scanned property inspection form with handwritten checkmarks and
notes across multiple pages. Read the checked boxes and handwritten values.
Return ONLY JSON with keys: floor_type, floor_condition, wood_grade,
paint_condition, roof_condition, hvac_age_years, kitchen_condition,
bathroom_condition, renovation_cost_estimate, overall_condition_score.
Use the label text of each checked box as the field value (e.g.
"Engineered hardwood" for floor_type). If a field wasn't checked or is
illegible, use null.
"""})

    # 2. Vision analysis — single call across all pages so the model has
    # full form context (e.g. renovation cost table spans the last page).
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.choices[0].message.content.replace("```json", "").replace("```", "")

    # 3. Redact any PII in the text output (inspector name, license number)
    # before it's stored.
    clean = redact_and_tokenize(raw, doc_id, db_path)
    return json.loads(clean)
