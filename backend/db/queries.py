import json
import os
import sqlite3
from contextlib import contextmanager

from ..valuation.calculator import calculate_base_value


@contextmanager
def _db():
    """Connection scope using DATABASE_PATH from the environment, same
    convention as setup_db.py — callers (MCP tools) don't pass a db_path
    explicitly. Commits on success; always closes, so an exception mid-
    query can't leak the handle or hold a write lock open.
    """
    db_path = os.environ.get("DATABASE_PATH", "./property_intel.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_property_exists(property_id: int):
    """INSERT OR IGNORE a bare properties row so ingestion pipelines have
    something to attach child rows (property_images, material_assessment,
    etc.) to via FOREIGN KEY, even before /ingest/blueprint has populated
    the property's core fields. properties.id is INTEGER PRIMARY KEY, so
    property_id must be a real integer, not an arbitrary string.
    """
    with _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO properties (id) VALUES (?)", (property_id,))


def save_photo_assessment(property_id: int, image_path: str, assessment: dict):
    """Persist one image_agent result: raw assessment + condition/issues
    into property_images, and the material-relevant fields into
    material_assessment (source='ai_photo') so they're queryable alongside
    blueprint/inspection-sourced assessments of the same property.
    """
    ensure_property_exists(property_id)
    with _db() as conn:
        cursor = conn.execute(
            "INSERT INTO property_images (property_id, image_path, ai_assessment, "
            "condition_score, issues_detected, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            (property_id, image_path, json.dumps(assessment),
             assessment.get("condition_score"),
             json.dumps(assessment.get("visible_issues", [])),
             assessment.get("confidence")))
        image_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO material_assessment (property_id, floor_type, floor_condition, "
            "wood_species, paint_condition, source, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (property_id, assessment.get("floor_type"), assessment.get("floor_condition"),
             assessment.get("wood_species"), assessment.get("paint_condition"),
             "ai_photo", assessment.get("confidence")))
    # Returned so the API response can tell the frontend which
    # property_images row this upload created (used to scope the
    # dashboard's photo tiles to the current session).
    return image_id


def _maybe_update_estimated_value(property_id: int):
    """Compute and persist properties.estimated_value once sqft and
    year_built are both known, using the same deterministic formula as
    the valuation module (Module 3 §9 / backend/valuation/calculator.py).
    Called after any save_* that might have just completed the pair
    (blueprint usually sets sqft, inspection usually sets year_built —
    whichever one lands second is what actually triggers a real value).
    Without this, estimated_value/price_per_sqft stay null forever and
    the frontend shows "Value pending" even after enough data exists to
    compute a real number.
    """
    with _db() as conn:
        row = conn.execute(
            "SELECT sqft, year_built FROM properties WHERE id = ?", (property_id,)).fetchone()
        if row and row["sqft"] and row["year_built"]:
            # fetch_local_ppsf is a stub (see its docstring) — this is an
            # illustrative estimate, not an appraisal, same caveat as the
            # valuation module itself.
            ppsf = fetch_local_ppsf(None)
            estimated_value = calculate_base_value(row["sqft"], row["year_built"], ppsf)
            conn.execute(
                "UPDATE properties SET price_per_sqft = ?, estimated_value = ? WHERE id = ?",
                (ppsf, estimated_value, property_id))


def save_blueprint_fields(property_id: int, fields: dict):
    """Persist blueprint_agent results into properties' core fields.
    Only overwrites a column if the blueprint actually returned a value
    for it (COALESCE keeps the existing value otherwise) — a given
    blueprint sheet (e.g. Ground Floor) may not contain every field (e.g.
    bedroom count lives on the Upper Floor sheet instead).

    NULLIF(?, 0) treats an extracted 0 the same as a missing value for
    sqft/bedrooms/bathrooms — a sheet that doesn't mention bedrooms at
    all is "unknown," not "a home with zero bedrooms." This is
    defense-in-depth alongside the extraction prompt's own null-vs-zero
    instruction (see blueprint_agent.py): that prompt has already been
    caught giving inconsistent answers on this exact field once before
    (BUGS.md #21), so the persistence layer doesn't rely on the prompt
    alone to avoid a real room count getting clobbered by a false zero.
    """
    ensure_property_exists(property_id)
    with _db() as conn:
        conn.execute(
            "UPDATE properties SET "
            "sqft = COALESCE(NULLIF(?, 0), sqft), "
            "bedrooms = COALESCE(NULLIF(?, 0), bedrooms), "
            "bathrooms = COALESCE(NULLIF(?, 0), bathrooms) "
            "WHERE id = ?",
            (fields.get("sqft"), fields.get("bedrooms"), fields.get("bathrooms"),
             property_id))
    _maybe_update_estimated_value(property_id)


def save_inspection_form(property_id: int, fields: dict):
    """Persist inspection_parser results into inspection_forms, plus feed
    the PROPERTY DETAILS header fields (builder/year_built/address) back
    into properties — the inspection form is often the only ingestion
    source that captures those, since blueprints only give sqft/beds/baths
    and photos don't have them at all. inspector_name_token/inspection_date
    are still left null: the extraction prompt doesn't pull inspector
    identity fields (out of scope — that data would need its own
    redaction handling before being tokenized into this column).
    """
    ensure_property_exists(property_id)
    with _db() as conn:
        conn.execute(
            "INSERT INTO inspection_forms (property_id, parsed_fields) VALUES (?, ?)",
            (property_id, json.dumps(fields)))
        conn.execute(
            "INSERT INTO material_assessment (property_id, floor_type, floor_condition, "
            "wood_grade, paint_condition, source) VALUES (?, ?, ?, ?, ?, ?)",
            (property_id, fields.get("floor_type"), fields.get("floor_condition"),
             fields.get("wood_grade"), fields.get("paint_condition"), "inspection"))
        conn.execute(
            "UPDATE properties SET "
            "builder = COALESCE(?, builder), "
            "year_built = COALESCE(?, year_built), "
            "address = COALESCE(?, address), "
            "city_state_zip = COALESCE(?, city_state_zip) "
            "WHERE id = ?",
            (fields.get("builder"), fields.get("year_built"), fields.get("address"),
             fields.get("city_state_zip"), property_id))
    _maybe_update_estimated_value(property_id)


def get_property(property_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    return dict(row) if row else None


def get_maintenance_needs(property_id, priority=None):
    with _db() as conn:
        if priority:
            rows = conn.execute(
                "SELECT * FROM maintenance_needs WHERE property_id = ? AND priority = ?",
                (property_id, priority)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM maintenance_needs WHERE property_id = ?",
                (property_id,)).fetchall()
    return [dict(r) for r in rows]


def get_contractors_by_category(category):
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM renovation_companies WHERE category = ?",
            (category,)).fetchall()
    return [dict(r) for r in rows]


def get_latest_inspection(property_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT parsed_fields FROM inspection_forms WHERE property_id = ? "
            "ORDER BY id DESC LIMIT 1", (property_id,)).fetchone()
    return json.loads(row["parsed_fields"]) if row else None


def get_renovation_breakdown(property_id):
    """Normalize the renovation_cost_estimate field from the latest
    inspection form into a consistent list of
    {category, priority, cost, roi} for the frontend's RenovationTable.

    The extraction prompt (inspection_parser.py) now specifies one fixed
    JSON schema (list of {category, priority, cost, roi} objects), which
    the first branch below handles directly. The other branches are
    fallbacks for the freeform shapes GPT-4o was observed returning
    before that schema was locked down — a dict keyed by category, and a
    list of single-key {category_name: cost_string} dicts (see
    tests/test_log.txt Tests 10, 17, 22) — kept so older already-ingested
    rows in the DB still render instead of going blank.
    """
    inspection = get_latest_inspection(property_id)
    if not inspection:
        return []
    raw = inspection.get("renovation_cost_estimate")
    if not raw:
        return []
    items = []
    if isinstance(raw, list):
        for r in raw:
            if not isinstance(r, dict):
                continue
            if "category" in r or "item" in r:
                # Current fixed schema, or the older item/est_cost shape.
                items.append({
                    "category": r.get("category") or r.get("item"),
                    "priority": r.get("priority"),
                    "cost": r.get("cost") or r.get("est_cost"),
                    "roi": r.get("roi"),
                })
            else:
                # Fallback: single-key {category_name: cost_string} dict.
                for category, cost in r.items():
                    items.append({
                        "category": category,
                        "priority": None,
                        "cost": cost if isinstance(cost, str) else None,
                        "roi": None,
                    })
    elif isinstance(raw, dict):
        for category, r in raw.items():
            if not isinstance(r, dict):
                continue
            items.append({
                "category": category,
                "priority": r.get("Priority"),
                "cost": r.get("Est. cost ($)"),
                "roi": r.get("ROI (%)"),
            })
    return items


def get_property_images(property_id):
    """All uploaded-photo records for a property, oldest first — the
    frontend's PropertyCard uses the first as its hero image and the
    rest as thumbnails.
    """
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, image_path FROM property_images WHERE property_id = ? "
            "ORDER BY id", (property_id,)).fetchall()
    return [dict(r) for r in rows]


def get_image_record(image_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT id, image_path FROM property_images WHERE id = ?",
            (image_id,)).fetchone()
    return dict(row) if row else None


def reset_property_data():
    """Delete every ingested/derived row so uploads can start fresh:
    properties and all their child tables, plus the PII token map (its
    doc_ids reference documents that no longer exist after a reset).
    renovation_companies is intentionally kept — it's seeded reference
    data (schema.sql), not ingested content. Pinecone namespaces are also
    left alone: the warranty document is ingested separately from the
    upload flow, and wiping it would silently break /chat.
    """
    tables = ["property_images", "material_assessment", "maintenance_needs",
              "inspection_forms", "documents", "pii_token_map", "properties"]
    deleted = {}
    with _db() as conn:
        for table in tables:
            deleted[table] = conn.execute(f"DELETE FROM {table}").rowcount
    return deleted


def fetch_local_ppsf(zip_code):
    """Look up local price-per-sqft for a ZIP code.

    STUB: no live MLS/county-appraisal/market-data API is integrated yet.
    Returns the $180/sqft statewide illustrative midpoint from
    texas_property_valuation_formulas.pdf's worked examples. The source
    doc explicitly warns against this for real calculations ("Do not use
    a statewide average for a real calculation — Texas price-per-sqft
    varies roughly 2-3x between metro submarkets") — this exists so the
    valuation tools are callable end-to-end before that integration
    exists, not as a production-accurate lookup.
    """
    return 180.0
