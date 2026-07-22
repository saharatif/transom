import re

# Deterministic valuation formulas, parsed once from
# docs/pdfs/texas_property_valuation_formulas.pdf — never RAG'd, since
# these are fixed formulas/lookups, not open-ended text to retrieve from.
# Multipliers and cost ranges below are transcribed directly from that
# reference doc's Section 2.1 table.

# Maps the inspection form's free-text renovation categories (as they
# appear in renovation_cost_estimate — see inspection_parser.py) to the
# fixed ROI_TABLE keys above. "Paint (interior)" and any other category
# printed on the form with no matching PDF-defined ROI multiplier is
# intentionally left unmapped rather than guessed.
RENOVATION_CATEGORY_ALIASES = {
    "roof replacement": "roof_replacement",
    "hvac system": "hvac_replacement",
    "kitchen remodel": "kitchen_remodel",
    "bathroom updates": "bathroom_updates",
    "flooring refinish": "flooring_refinish",
    "exterior / curb appeal": "curb_appeal_exterior",
}

_COST_NUMBER = re.compile(r"[\d,]+(?:\.\d+)?")


def parse_cost_estimate(cost_str):
    """Parse a handwritten cost field like "8000-10000 USD" or "$9,500"
    into a single representative number (the midpoint of a range, or the
    lone figure) for feeding into calculate_renovation_impact. Returns
    None if the field is empty or has no parseable number — callers skip
    those rows rather than guessing a cost.
    """
    if not cost_str or not isinstance(cost_str, str):
        return None
    numbers = [float(m.replace(",", "")) for m in _COST_NUMBER.findall(cost_str)]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def sum_costs_by_priority(renovation_breakdown, priorities):
    """Sum parse_cost_estimate() over every row in a property's
    renovation_cost_estimate breakdown whose priority is in `priorities`
    (e.g. {1, 2} for Urgent + Moderate — see RenovationTable.vue's
    PRIORITY_LABELS). Rows with an unparseable/missing cost are skipped
    rather than treated as zero. Returns None if no matching row had a
    parseable cost, so the caller can hide the figure instead of
    displaying a misleading $0.
    """
    total = 0.0
    matched = False
    for row in renovation_breakdown or []:
        if row.get("priority") not in priorities:
            continue
        cost = parse_cost_estimate(row.get("cost"))
        if cost is not None:
            total += cost
            matched = True
    return round(total, 2) if matched else None


def estimate_renovation_uplift(base_value, sqft, price_per_sqft, renovation_breakdown):
    """Apply calculate_renovation_impact to a property's actual parsed
    renovation_cost_estimate rows (RenovationTable's data source), mapping
    each row's free-text category/cost to the PDF's fixed ROI schedule.
    Rows with an unrecognized category or an unparseable cost are skipped
    (e.g. "Paint (interior)" has no PDF-defined multiplier). Returns None
    if nothing in the breakdown was usable, so the caller can fall back
    to showing only the pre-renovation base value.
    """
    renovations = []
    for row in renovation_breakdown or []:
        key = RENOVATION_CATEGORY_ALIASES.get((row.get("category") or "").strip().lower())
        cost = parse_cost_estimate(row.get("cost"))
        if key and cost is not None:
            renovations.append({"category": key, "cost": cost})
    if not renovations:
        return None
    return calculate_renovation_impact(base_value, renovations, price_per_sqft, sqft)


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
    if sqft is None or sqft <= 0:
        raise ValueError(f"sqft must be a positive number, got {sqft!r}")
    if year_built is None or year_built > current_year:
        raise ValueError(f"year_built must be <= {current_year}, got {year_built!r}")
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
        cat = r.get("category")
        if cat not in ROI_TABLE:
            # Callers (notably the MCP calculate_renovation_roi tool) pass
            # freeform renovation lists — name the valid categories instead
            # of surfacing a bare KeyError.
            raise ValueError(
                f"Unknown renovation category {cat!r}. "
                f"Valid categories: {', '.join(sorted(ROI_TABLE))}")
        cost = r.get("cost")
        if not isinstance(cost, (int, float)) or cost < 0:
            raise ValueError(
                f"Renovation {cat!r} needs a non-negative numeric 'cost', got {cost!r}")
        mult = ROI_TABLE[cat]["multiplier"]
        uplift = cost * mult
        total_uplift += uplift
        total_cost += cost
        breakdown.append({
            "category": cat,
            "cost": cost,
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
