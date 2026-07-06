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


@pytest.fixture
def client(temp_db):
    return TestClient(main.app, raise_server_exceptions=False)


def _rows(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    conn.close()
    return rows


def test_photo_ingest_persists_safe_image_path(client, temp_db, monkeypatch):
    monkeypatch.setattr(
        main, "analyze_property_image",
        lambda path, pid, doc_id, db: {"condition_score": 7, "confidence": "high",
                                       "visible_issues": ["worn paint"]})
    res = client.post("/ingest/photo", data={"property_id": 1},
                      files={"file": ("kitchen.jpg", b"fake-image-bytes", "image/jpeg")})
    assert res.status_code == 200
    images = _rows(temp_db, "property_images")
    assert len(images) == 1
    assert images[0]["condition_score"] == 7
    # The stored path must be the kept _safe sibling, not the deleted
    # spooled original.
    assert images[0]["image_path"].endswith("_safe.jpg")


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
