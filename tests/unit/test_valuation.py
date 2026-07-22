"""Unit tests for backend/valuation/calculator.py.

The formulas come from docs/pdfs/texas_property_valuation_formulas.pdf;
the worked-example numbers ($288,000 base value for a 2,000 sqft home
aged 20 years at $180/sqft) were previously verified manually (see
tests/test_log.txt, Tests 11-12) — these tests pin them permanently.
"""
import pytest

from backend.valuation.calculator import (
    ROI_TABLE, calculate_base_value, calculate_renovation_impact,
    estimate_renovation_uplift, parse_cost_estimate, sum_costs_by_priority)


class TestBaseValue:
    def test_worked_example_from_pdf(self):
        # 2,000 sqft x $180 x age factor 0.80 (20 yrs x 1%/yr) = $288,000
        assert calculate_base_value(2000, 2006, 180.0, current_year=2026) == 288000.0

    def test_age_factor_floors_at_060(self):
        # 100-year-old home: 1 - 0.01*100 = 0, but the floor is 0.60.
        assert calculate_base_value(1000, 1926, 100.0, current_year=2026) == 60000.0

    def test_new_build_has_no_depreciation(self):
        assert calculate_base_value(1500, 2026, 200.0, current_year=2026) == 300000.0

    @pytest.mark.parametrize("sqft", [0, -100, None])
    def test_rejects_bad_sqft(self, sqft):
        with pytest.raises(ValueError):
            calculate_base_value(sqft, 2000, 180.0)

    def test_rejects_future_year_built(self):
        with pytest.raises(ValueError):
            calculate_base_value(2000, 2050, 180.0, current_year=2026)


class TestRenovationImpact:
    def test_uplift_and_net_equity(self):
        result = calculate_renovation_impact(
            base_value=288000.0,
            renovations=[{"category": "kitchen_remodel", "cost": 10000}],
            local_median_ppsf=180.0, sqft=2000)
        assert result["total_value_uplift"] == 15000.0  # 10,000 x 1.50
        assert result["updated_value"] == 303000.0
        assert result["net_equity_gain"] == 5000.0
        assert result["ceiling_applied"] is False
        assert result["breakdown"][0]["roi_percent"] == 150.0

    def test_neighborhood_ceiling_caps_updated_value(self):
        # Ceiling = 180 x 1000 x 1.20 = 216,000; raw would be 300,000.
        result = calculate_renovation_impact(
            base_value=280000.0,
            renovations=[{"category": "roof_replacement", "cost": 14285.71}],
            local_median_ppsf=180.0, sqft=1000)
        assert result["ceiling_applied"] is True
        assert result["updated_value"] == 216000.0

    def test_all_six_categories_have_multipliers(self):
        assert set(ROI_TABLE) == {
            "roof_replacement", "hvac_replacement", "kitchen_remodel",
            "bathroom_updates", "flooring_refinish", "curb_appeal_exterior"}
        for entry in ROI_TABLE.values():
            assert entry["multiplier"] > 1.0
            assert entry["priority"] in {"urgent", "moderate", "low"}

    def test_unknown_category_raises_with_valid_options(self):
        with pytest.raises(ValueError, match="Unknown renovation category"):
            calculate_renovation_impact(
                288000.0, [{"category": "swimming_pool", "cost": 50000}],
                180.0, 2000)

    @pytest.mark.parametrize("cost", [None, "10000", -5])
    def test_non_numeric_or_negative_cost_raises(self, cost):
        with pytest.raises(ValueError, match="cost"):
            calculate_renovation_impact(
                288000.0, [{"category": "kitchen_remodel", "cost": cost}],
                180.0, 2000)


class TestParseCostEstimate:
    def test_range_returns_midpoint(self):
        assert parse_cost_estimate("8000-10000 USD") == 9000.0

    def test_single_figure(self):
        assert parse_cost_estimate("$9,500") == 9500.0

    def test_no_number_returns_none(self):
        assert parse_cost_estimate("TBD") is None

    @pytest.mark.parametrize("value", [None, "", 9000])
    def test_non_string_or_empty_returns_none(self, value):
        assert parse_cost_estimate(value) is None


class TestEstimateRenovationUplift:
    """Covers the real dashboard scenario (previously a gap — see
    BUGS.md #34): turning the inspection form's free-text
    renovation_cost_estimate rows into a genuine renovation-adjusted
    valuation via calculate_renovation_impact, rather than only ever
    showing the pre-renovation base value.
    """

    def test_maps_real_inspection_form_categories_and_cost_ranges(self):
        base_value = 316944.0  # property #1's real base value
        breakdown = [
            {"category": "Roof replacement", "priority": 1, "cost": "8000-10000 USD", "roi": "140%"},
            {"category": "HVAC system", "priority": 1, "cost": "5000-10000 USD", "roi": "120%"},
        ]
        result = estimate_renovation_uplift(base_value, 2201, 180.0, breakdown)
        assert result is not None
        # midpoints: 9000 * 1.40 + 7500 * 1.20 = 12600 + 9000 = 21600
        assert result["total_value_uplift"] == 21600.0
        assert result["updated_value"] > base_value

    def test_unmapped_category_is_skipped_not_guessed(self):
        # "Paint (interior)" has no PDF-defined ROI multiplier.
        breakdown = [{"category": "Paint (interior)", "cost": "1000-3000 USD"}]
        assert estimate_renovation_uplift(288000.0, 2000, 180.0, breakdown) is None

    def test_unparseable_cost_is_skipped(self):
        breakdown = [{"category": "Roof replacement", "cost": None}]
        assert estimate_renovation_uplift(288000.0, 2000, 180.0, breakdown) is None

    def test_empty_breakdown_returns_none(self):
        assert estimate_renovation_uplift(288000.0, 2000, 180.0, []) is None

    def test_mixed_known_and_unknown_categories_uses_only_known(self):
        breakdown = [
            {"category": "Kitchen remodel", "cost": "9000-18000 USD"},
            {"category": "Paint (interior)", "cost": "1000-3000 USD"},
        ]
        result = estimate_renovation_uplift(288000.0, 2000, 180.0, breakdown)
        assert result is not None
        assert result["total_renovation_cost"] == 13500.0  # only the kitchen midpoint


class TestSumCostsByPriority:
    """The urgent-medium repair total shown under the two value figures
    on PropertyCard — sums the (averaged) cost of every Urgent (1) +
    Moderate (2) priority renovation row, matching RenovationTable's own
    priority labels."""

    def test_sums_only_urgent_and_moderate(self):
        breakdown = [
            {"category": "Roof replacement", "priority": 1, "cost": "8000-10000 USD"},
            {"category": "HVAC system", "priority": 1, "cost": "5000-10000 USD"},
            {"category": "Kitchen remodel", "priority": 2, "cost": "9000-18000 USD"},
            {"category": "Curb appeal", "priority": 3, "cost": "3000-7000 USD"},
        ]
        # midpoints: 9000 + 7500 + 13500 = 30000 (priority-3 row excluded)
        assert sum_costs_by_priority(breakdown, {1, 2}) == 30000.0

    def test_rows_with_unparseable_cost_are_skipped_not_zero(self):
        breakdown = [
            {"category": "Roof replacement", "priority": 1, "cost": "8000-10000 USD"},
            {"category": "HVAC system", "priority": 1, "cost": None},
        ]
        assert sum_costs_by_priority(breakdown, {1, 2}) == 9000.0

    def test_no_matching_priority_returns_none(self):
        breakdown = [{"category": "Curb appeal", "priority": 3, "cost": "3000-7000 USD"}]
        assert sum_costs_by_priority(breakdown, {1, 2}) is None

    def test_empty_breakdown_returns_none(self):
        assert sum_costs_by_priority([], {1, 2}) is None

    def test_missing_priority_key_is_not_matched(self):
        breakdown = [{"category": "Roof replacement", "cost": "8000-10000 USD"}]
        assert sum_costs_by_priority(breakdown, {1, 2}) is None
