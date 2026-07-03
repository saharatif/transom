# Deterministic valuation formulas, parsed once from
# docs/pdfs/texas_property_valuation_formulas.pdf — never RAG'd, since
# these are fixed formulas/lookups, not open-ended text to retrieve from.
# Multipliers and cost ranges below are transcribed directly from that
# reference doc's Section 2.1 table.

ROI_TABLE = {
    "roof_replacement":     {"multiplier": 1.40, "priority": "urgent",
                             "cost_range": (8000, 14000)},
    "hvac_replacement":     {"multiplier": 1.20, "priority": "urgent",
                             "cost_range": (5500, 10000)},
    "kitchen_remodel":      {"multiplier": 1.50, "priority": "moderate",
                             "cost_range": (9000, 18000)},
    "bathroom_updates":     {"multiplier": 1.25, "priority": "moderate",
                             "cost_range": (5000, 12000)},
    "flooring_refinish":    {"multiplier": 1.42, "priority": "moderate",
                             "cost_range": (4000, 9000)},
    "curb_appeal_exterior": {"multiplier": 1.50, "priority": "low",
                             "cost_range": (3000, 7000)},
}


def calculate_base_value(sqft, year_built, price_per_sqft,
                         depreciation_rate=0.010, current_year=2026):
    """Section 1 — Base Value = Price/SqFt x SqFt x Age Factor.
    Age Factor = 1 - (Depreciation Rate x Effective Age), floored at 0.60.
    Effective Age defaults to Actual Age (current_year - year_built) since
    no renovation-adjusted effective age is tracked here.
    """
    age = current_year - year_built
    age_factor = max(1 - (depreciation_rate * age), 0.60)
    return round(price_per_sqft * sqft * age_factor, 2)


def calculate_renovation_impact(base_value, renovations, local_median_ppsf,
                                 sqft, ceiling_multiplier=1.20):
    """Section 2 — Value Uplift = Renovation Cost x ROI Multiplier;
    Updated Value = Base Value + sum(Value Uplift). Capped by a
    neighborhood ceiling (Section 2, "diminishing at the margin"): Updated
    Value should not exceed roughly 1.15-1.25x local median price/sqft x
    sqft, so ceiling_multiplier defaults to the middle of that range.
    """
    breakdown = []
    total_uplift = 0
    total_cost = 0
    for r in renovations:
        cat = r["category"]
        mult = ROI_TABLE[cat]["multiplier"]
        uplift = r["cost"] * mult
        total_uplift += uplift
        total_cost += r["cost"]
        breakdown.append({
            "category": cat,
            "cost": r["cost"],
            "value_uplift": round(uplift, 2),
            "roi_percent": round(mult * 100, 1),
            "priority": ROI_TABLE[cat]["priority"]
        })

    raw_updated = base_value + total_uplift
    ceiling = local_median_ppsf * sqft * ceiling_multiplier
    updated_value = min(raw_updated, ceiling)

    return {
        "base_value": base_value,
        "total_renovation_cost": total_cost,
        "total_value_uplift": round(total_uplift, 2),
        "updated_value": round(updated_value, 2),
        "net_equity_gain": round(total_uplift - total_cost, 2),
        "ceiling_applied": raw_updated > ceiling,
        "breakdown": breakdown
    }
