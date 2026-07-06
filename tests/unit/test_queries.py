"""Unit tests for backend/db/queries.py against a fresh schema.sql DB
(see conftest.temp_db). Covers the persistence safeguards that have had
real regressions before: the NULLIF zero-clobber guard (BUGS.md #27),
the estimated-value trigger (BUGS.md #23), and the renovation-breakdown
shape normalizer (BUGS.md #22).
"""
import json
import sqlite3

from backend.db import queries


def _get_property(db_path, pid=1):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


class TestBlueprintPersistence:
    def test_saves_fields(self, temp_db):
        queries.save_blueprint_fields(1, {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
        prop = _get_property(temp_db)
        assert (prop["sqft"], prop["bedrooms"], prop["bathrooms"]) == (2201, 4, 3)

    def test_zero_does_not_clobber_existing_value(self, temp_db):
        # BUGS.md #27: a partial sheet returning 0 must not overwrite a
        # real count extracted from another sheet.
        queries.save_blueprint_fields(1, {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
        queries.save_blueprint_fields(1, {"sqft": 0, "bedrooms": 0, "bathrooms": 0})
        prop = _get_property(temp_db)
        assert (prop["sqft"], prop["bedrooms"], prop["bathrooms"]) == (2201, 4, 3)

    def test_null_does_not_clobber_existing_value(self, temp_db):
        queries.save_blueprint_fields(1, {"sqft": 2201, "bedrooms": 4, "bathrooms": 3})
        queries.save_blueprint_fields(1, {"sqft": None, "bedrooms": None, "bathrooms": None})
        prop = _get_property(temp_db)
        assert (prop["sqft"], prop["bedrooms"], prop["bathrooms"]) == (2201, 4, 3)


class TestEstimatedValueTrigger:
    def test_no_value_until_both_fields_exist(self, temp_db):
        queries.save_blueprint_fields(1, {"sqft": 2201})
        assert _get_property(temp_db)["estimated_value"] is None

    def test_value_computed_once_sqft_and_year_known(self, temp_db):
        # BUGS.md #23: blueprint gives sqft, inspection gives year_built —
        # whichever lands second must trigger the valuation.
        queries.save_blueprint_fields(1, {"sqft": 2000})
        queries.save_inspection_form(1, {"builder": "Acme Homes", "year_built": 2006})
        prop = _get_property(temp_db)
        # 2000 sqft x $180 x 0.80 age factor (20 yrs at 1%/yr, from the
        # stubbed statewide ppsf) = $288,000.
        assert prop["estimated_value"] == 288000.0
        assert prop["price_per_sqft"] == 180.0


class TestInspectionPersistence:
    def test_header_fields_feed_properties(self, temp_db):
        queries.save_inspection_form(1, {
            "builder": "Acme Homes", "year_built": 2010,
            "address": "12 Oak St", "city_state_zip": "Dallas, TX 75001"})
        prop = _get_property(temp_db)
        assert prop["builder"] == "Acme Homes"
        assert prop["year_built"] == 2010
        assert prop["address"] == "12 Oak St"

    def test_null_header_fields_do_not_clobber(self, temp_db):
        queries.save_inspection_form(1, {"builder": "Acme Homes", "year_built": 2010})
        queries.save_inspection_form(1, {"builder": None, "year_built": None})
        prop = _get_property(temp_db)
        assert prop["builder"] == "Acme Homes"
        assert prop["year_built"] == 2010


class TestRenovationBreakdownNormalizer:
    def _insert_inspection(self, db_path, estimate):
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT OR IGNORE INTO properties (id) VALUES (1)")
        conn.execute(
            "INSERT INTO inspection_forms (property_id, parsed_fields) VALUES (1, ?)",
            (json.dumps({"renovation_cost_estimate": estimate}),))
        conn.commit()
        conn.close()

    def test_current_fixed_schema(self, temp_db):
        self._insert_inspection(temp_db, [
            {"category": "Roof replacement", "priority": 1,
             "cost": "8000-10000 USD", "roi": "140%"}])
        rows = queries.get_renovation_breakdown(1)
        assert rows == [{"category": "Roof replacement", "priority": 1,
                         "cost": "8000-10000 USD", "roi": "140%"}]

    def test_legacy_dict_keyed_by_category(self, temp_db):
        self._insert_inspection(temp_db, {
            "HVAC system": {"Priority": 1, "Est. cost ($)": "5000", "ROI (%)": "120%"}})
        rows = queries.get_renovation_breakdown(1)
        assert rows == [{"category": "HVAC system", "priority": 1,
                         "cost": "5000", "roi": "120%"}]

    def test_legacy_single_key_dict_list(self, temp_db):
        self._insert_inspection(temp_db, [{"Kitchen remodel": "9000-12000"}])
        rows = queries.get_renovation_breakdown(1)
        assert rows == [{"category": "Kitchen remodel", "priority": None,
                         "cost": "9000-12000", "roi": None}]

    def test_no_inspection_returns_empty(self, temp_db):
        assert queries.get_renovation_breakdown(1) == []
