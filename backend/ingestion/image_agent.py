import base64, json
from openai import OpenAI
from .preprocess import blur_faces_and_plates
from ..redaction.pii import redact_and_tokenize
import logfire

client = OpenAI()

@logfire.instrument()
def analyze_property_image(image_path: str, property_id: str, doc_id: str, db_path: str):
    """Run a property photo through the full ingestion chain:
    blur faces/plates -> GPT-4o Vision analysis -> redact any PII in the
    text output -> return structured JSON. This is the only path an image
    is allowed to reach an external LLM through.
    """
    # 1. Preprocess: blur faces / license plates BEFORE Vision.
    # Presidio (used in step 3) only works on text, so images must be
    # sanitized here, before they're sent to an external API.
    safe_image_path = blur_faces_and_plates(image_path)

    with open(safe_image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    # 2. Vision analysis — ask GPT-4o for a fixed set of known fields
    # (condition, materials, issues) rather than open-ended description,
    # since these map directly to the structured SQLite schema.
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": """
Analyze this property image. Return ONLY JSON:
{
  "floor_type": "hardwood/tile/vinyl/carpet/laminate/unknown",
  "floor_condition": "excellent/good/fair/worn/poor",
  "wood_species": "oak/pine/walnut/unknown/na",
  "paint_condition": "fresh/good/fair/poor",
  "condition_score": 0-10,
  "visible_issues": ["..."],
  "estimated_age_years": number,
  "confidence": "high/medium/low"
}
"""}
            ]
        }]
    )
    # Vision sometimes wraps JSON in a markdown code fence; strip it before parsing.
    raw = resp.choices[0].message.content.replace("```json", "").replace("```", "")

    # 3. Redact any PII the model may have echoed into its text output
    # (e.g. a visible name/address in the photo) before it's stored.
    clean = redact_and_tokenize(raw, doc_id, db_path)
    return json.loads(clean)
