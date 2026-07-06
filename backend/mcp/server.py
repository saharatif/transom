from mcp.server.fastmcp import FastMCP
from ..valuation.calculator import (calculate_base_value,
                                     calculate_renovation_impact, ROI_TABLE)
from ..rag.graph import rag_agent
from ..db.queries import (get_property, get_maintenance_needs,
                          get_contractors_by_category, fetch_local_ppsf)
import logfire

mcp = FastMCP("property-intelligence")

# Each tool maps to exactly the "right tool per input" routing from
# Module 1 §3: SQL for structured data, deterministic code for formulas,
# RAG only for the one open-ended (warranty) source.

@mcp.tool()
@logfire.instrument()
def get_property_summary(property_id: str) -> dict:
    """Return the full structured summary for a property."""
    return get_property(property_id)

@mcp.tool()
@logfire.instrument()
def get_maintenance(property_id: str, priority: str = None) -> dict:
    """Get maintenance needs, optionally filtered by priority."""
    return get_maintenance_needs(property_id, priority)

@mcp.tool()
@logfire.instrument()
def estimate_property_value(sqft: int, year_built: int, zip_code: str) -> dict:
    """Calculate base value using the Texas valuation formula (Section 1)."""
    ppsf = fetch_local_ppsf(zip_code)
    base = calculate_base_value(sqft, year_built, ppsf)
    return {"base_value": base, "price_per_sqft": ppsf}

@mcp.tool()
@logfire.instrument()
def calculate_renovation_roi(property_id: str, renovations: list,
                             zip_code: str) -> dict:
    """Calculate renovation value uplift capped at neighborhood ceiling."""
    prop = get_property(property_id)
    if prop is None:
        return {"error": f"Property {property_id} not found"}
    if not prop.get("sqft") or not prop.get("year_built"):
        return {"error": f"Property {property_id} is missing sqft/year_built — "
                         "ingest a blueprint and inspection form first"}
    ppsf = fetch_local_ppsf(zip_code)
    base = calculate_base_value(prop["sqft"], prop["year_built"], ppsf)
    return calculate_renovation_impact(base, renovations, ppsf, prop["sqft"])

@mcp.tool()
@logfire.instrument()
def get_contractors(category: str) -> dict:
    """Get recommended contractors for a renovation category."""
    return get_contractors_by_category(category)

@mcp.tool()
@logfire.instrument()
def get_warranty_coverage(property_id: str, question: str) -> dict:
    """Search the warranty document (RAG) for coverage on an issue."""
    result = rag_agent.invoke({
        "question": question, "retrieval_query": "",
        "property_id": property_id, "doc_type": "warranty", "documents": [],
        "is_relevant": False, "answer": "", "citations": [], "iterations": 0})
    return {"answer": result["answer"], "citations": result["citations"]}

if __name__ == "__main__":
    mcp.run()
