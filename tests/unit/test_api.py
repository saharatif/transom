"""Endpoint wiring tests for backend/main.py via FastAPI's TestClient,
with the LLM/OCR agent functions monkeypatched — verifies the
spool -> agent -> persist flow, upload validation, and error mapping
without any external API calls. This exact wiring (endpoint -> save_*
argument shapes) broke once during refactoring and was only caught live
(BUGS.md #32), so it's pinned here.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.ingestion.preprocess import safe_output_path


@pytest.fixture
def client(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "UPLOADS_DIR", str(tmp_path / "uploads"))
    import os
    os.makedirs(main.UPLOADS_DIR, exist_ok=True)
    return TestClient(main.app, raise_server_exceptions=False)


def _rows(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    conn.close()
    return rows


def _fake_photo_agent(assessment):
    """Mimic the real photo pipeline's side effect: preprocessing writes a
    blurred _safe copy next to the spooled upload, which the endpoint then
    moves into UPLOADS_DIR."""
    def agent(path, pid, doc_id, db):
        with open(safe_output_path(path), "wb") as f:
            f.write(b"fake-blurred-image")
        return assessment
    return agent


def test_photo_ingest_persists_served_image(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "analyze_property_image",
        _fake_photo_agent({"condition_score": 7, "confidence": "high",
                           "visible_issues": ["worn paint"]}))
    res = client.post("/ingest/photo", data={"property_id": 1},
                      files={"file": ("kitchen.jpg", b"fake-image-bytes", "image/jpeg")})
    assert res.status_code == 200
    images = _rows(temp_db, "property_images")
    assert len(images) == 1
    assert images[0]["condition_score"] == 7
    # The response reports which row this upload created — the frontend
    # uses it to scope photo tiles to the current session.
    assert res.json()["image_id"] == images[0]["id"]
    # The stored path must be the kept _safe copy, moved into UPLOADS_DIR
    # (the spooled original is deleted after processing).
    assert images[0]["image_path"].startswith(main.UPLOADS_DIR)
    assert images[0]["image_path"].endswith("_safe.jpg")

    # The property view lists it, and the image endpoint serves the bytes.
    detail = client.get("/property/1").json()
    assert detail["images"] == [{"id": images[0]["id"], "url": f"/images/{images[0]['id']}"}]
    served = client.get(detail["images"][0]["url"])
    assert served.status_code == 200
    assert served.content == b"fake-blurred-image"


def test_missing_image_file_404s_and_is_hidden_from_property_view(client, temp_db):
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO properties (id) VALUES (1)")
    conn.execute("INSERT INTO property_images (property_id, image_path) "
                 "VALUES (1, '/tmp/reaped-temp-file_safe.jpg')")
    conn.commit()
    conn.close()
    assert client.get("/property/1").json()["images"] == []
    assert client.get("/images/1").status_code == 404


def test_blueprint_ingest_persists_fields(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
    res = client.post("/ingest/blueprint", data={"property_id": 1},
                      files={"file": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert res.status_code == 200
    props = _rows(temp_db, "properties")
    assert props[0]["sqft"] == 2201 and props[0]["bedrooms"] == 4


def test_inspection_ingest_persists_form(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "parse_inspection_form",
        lambda path, pid, doc_id, db: {"builder": "Acme", "year_built": 2010})
    res = client.post("/ingest/inspection", data={"property_id": 1},
                      files={"file": ("form.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert res.status_code == 200
    assert _rows(temp_db, "properties")[0]["builder"] == "Acme"
    assert len(_rows(temp_db, "inspection_forms")) == 1


def test_unsupported_extension_rejected_415(client, temp_db):
    res = client.post("/ingest/photo", data={"property_id": 1},
                      files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 415
    assert ".txt" in res.json()["detail"]


def test_inspection_rejects_images(client, temp_db):
    res = client.post("/ingest/inspection", data={"property_id": 1},
                      files={"file": ("scan.jpg", b"fake", "image/jpeg")})
    assert res.status_code == 415


def test_agent_failure_maps_to_502_with_reason(client, temp_db, monkeypatch):
    def boom(path, pid, doc_id, db):
        raise ValueError("No JSON found in LLM response")
    monkeypatch.setattr(main, "analyze_property_image", boom)
    res = client.post("/ingest/photo", data={"property_id": 1},
                      files={"file": ("kitchen.jpg", b"fake", "image/jpeg")})
    assert res.status_code == 502
    assert "No JSON found" in res.json()["detail"]
    # A failed ingestion must not leave partial rows behind.
    assert _rows(temp_db, "property_images") == []


def test_missing_property_404(client, temp_db):
    res = client.get("/property/999")
    assert res.status_code == 404


def test_property_valuation_shows_both_previous_and_improved_estimate(
        client, temp_db, monkeypatch):
    """End-to-end regression for BUGS.md #34: previously properties.
    estimated_value (pre-renovation base value) was the only figure ever
    shown, mislabeled as if it reflected renovations. Blueprint + real
    inspection renovation data should now also produce a genuine
    improved_estimate via the actual ROI math.
    """
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
    monkeypatch.setattr(
        main, "parse_inspection_form",
        lambda path, pid, doc_id, db: {
            "year_built": 2006,
            "renovation_cost_estimate": [
                {"category": "Roof replacement", "priority": 1,
                 "cost": "8000-10000 USD", "roi": "140%"},
            ],
        })
    client.post("/ingest/blueprint", data={"property_id": 1},
               files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")})
    client.post("/ingest/inspection", data={"property_id": 1},
               files={"file": ("form.pdf", b"%PDF-1.4", "application/pdf")})

    valuation = client.get("/property/1").json()["valuation"]
    assert valuation["previous_estimate"] == 316944.0
    # 9000 (midpoint of 8000-10000) * 1.40 = 12,600 uplift
    assert valuation["improved_estimate"] == 329544.0
    assert valuation["improved_estimate"] > valuation["previous_estimate"]
    # The one row is Urgent (priority 1), so its 9000 midpoint is the
    # whole urgent+medium total.
    assert valuation["urgent_medium_total"] == 9000.0
    # net_equity_gain: value uplift (12,600) minus the renovation's own
    # cost (9,000 midpoint) = 3,600 profit.
    assert valuation["profit_estimate"] == 3600.0


# Note: net_equity_gain = total_uplift - total_cost, and every ROI_TABLE
# multiplier is > 1.0 (see test_valuation.py's
# test_all_six_categories_have_multipliers), so total_uplift = cost *
# multiplier is always >= cost for any single mapped category — meaning
# profit_estimate can never actually be negative against the current
# fixed ROI schedule. The frontend's negative/red styling branch is
# still correct defensive design (net_equity_gain's sign isn't
# structurally guaranteed by calculate_renovation_impact's signature,
# only by today's ROI_TABLE contents), just not reachable with real data
# today — so there's no live-data test for it here.


def test_no_profit_estimate_when_no_renovation_data(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201})
    monkeypatch.setattr(
        main, "parse_inspection_form",
        lambda path, pid, doc_id, db: {"year_built": 2006})
    client.post("/ingest/blueprint", data={"property_id": 1},
               files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")})
    client.post("/ingest/inspection", data={"property_id": 1},
               files={"file": ("form.pdf", b"%PDF-1.4", "application/pdf")})

    assert client.get("/property/1").json()["valuation"]["profit_estimate"] is None


def test_property_valuation_null_improved_when_no_renovation_data(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201})
    monkeypatch.setattr(
        main, "parse_inspection_form",
        lambda path, pid, doc_id, db: {"year_built": 2006})
    client.post("/ingest/blueprint", data={"property_id": 1},
               files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")})
    client.post("/ingest/inspection", data={"property_id": 1},
               files={"file": ("form.pdf", b"%PDF-1.4", "application/pdf")})

    valuation = client.get("/property/1").json()["valuation"]
    assert valuation["previous_estimate"] == 316944.0
    assert valuation["improved_estimate"] is None
    assert valuation["urgent_medium_total"] is None


def test_urgent_medium_total_excludes_low_priority_rows(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201})
    monkeypatch.setattr(
        main, "parse_inspection_form",
        lambda path, pid, doc_id, db: {
            "year_built": 2006,
            "renovation_cost_estimate": [
                {"category": "Roof replacement", "priority": 1, "cost": "8000-10000 USD"},
                {"category": "Kitchen remodel", "priority": 2, "cost": "9000-18000 USD"},
                {"category": "Exterior / curb appeal", "priority": 3, "cost": "3000-7000 USD"},
            ],
        })
    client.post("/ingest/blueprint", data={"property_id": 1},
               files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")})
    client.post("/ingest/inspection", data={"property_id": 1},
               files={"file": ("form.pdf", b"%PDF-1.4", "application/pdf")})

    valuation = client.get("/property/1").json()["valuation"]
    # midpoints: 9000 (urgent) + 13500 (moderate) = 22500; the priority-3
    # (low) row's 5000 midpoint must NOT be included.
    assert valuation["urgent_medium_total"] == 22500.0


def test_blank_chat_message_422(client, temp_db):
    res = client.post("/chat", data={"property_id": 1, "message": "   "})
    assert res.status_code == 422


def test_reset_clears_ingested_data_but_keeps_contractors(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "process_blueprint",
        lambda path, pid, doc_id, db: {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
    client.post("/ingest/blueprint", data={"property_id": 1},
                files={"file": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert len(_rows(temp_db, "properties")) == 1

    res = client.post("/reset")
    assert res.status_code == 200
    assert res.json()["deleted"]["properties"] == 1

    assert _rows(temp_db, "properties") == []
    assert _rows(temp_db, "inspection_forms") == []
    assert _rows(temp_db, "property_images") == []
    # Seeded reference data must survive a reset.
    assert len(_rows(temp_db, "renovation_companies")) == 5
    assert client.get("/property/1").status_code == 404
