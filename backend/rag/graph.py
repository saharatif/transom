from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .retrieval import build_retriever
from .measurement import compare_measurement_to_sources
import re, logfire

class RAGState(TypedDict):
    question: str
    # What's actually sent to the vector store. rewrite_node updates THIS,
    # never `question` — an earlier version overwrote the user's question
    # on each rewrite loop, so the final answer (and the deterministic
    # measurement comparison) ran against a twice-mutated paraphrase
    # instead of what the user asked (BUGS.md #33).
    retrieval_query: str
    property_id: str
    doc_type: str
    documents: List[dict]
    is_relevant: bool
    answer: str
    citations: List[str]
    iterations: int

def retrieve_node(state):
    retriever = build_retriever(state["property_id"], state["doc_type"])
    query = state.get("retrieval_query") or state["question"]
    docs = retriever.invoke(query)
    return {**state, "documents":
            [{"content": d.page_content, "metadata": d.metadata} for d in docs]}

def grade_node(state):
    # Cheap relevance check before spending a full answer-generation call
    # on documents that may not actually address the question.
    #
    # This grades each excerpt individually (numbered, with its section
    # header) and asks WHICH ones help, rather than a single yes/no over
    # the concatenated blob: the blob version was observed answering a
    # deterministic "NO" even when an excerpt plainly contained the
    # answering clause — apparently anchoring on the first (off-topic)
    # excerpt — which sent good retrievals into pointless rewrite loops
    # and ultimately produced wrong "not covered" answers (BUGS.md #33).
    # Per-excerpt grading forces the model to consider every excerpt and
    # was verified 3/3 consistent in both directions.
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    numbered = "\n\n".join(
        f"Excerpt {i + 1} [{d['metadata'].get('section', 'Unknown Section')}]:\n{d['content']}"
        for i, d in enumerate(state["documents"]))
    g = llm.invoke([
        SystemMessage(content=(
            "For each numbered excerpt below, decide whether it contains "
            "information that helps answer the question (even partially). "
            "Reply with the excerpt numbers that help, comma-separated "
            "(e.g. '1,3'), or the word NONE if none do.")),
        HumanMessage(content=f"Question: {state['question']}\n\n{numbered}")])
    is_relevant = bool(re.search(r"\d", g.content)) and "NONE" not in g.content.upper()
    return {**state, "is_relevant": is_relevant}

def rewrite_node(state):
    # If retrieval missed, rephrase the SEARCH QUERY to better match how
    # the source document is likely worded (e.g. legal/technical phrasing)
    # and try retrieval again. The user's question itself stays intact for
    # grading/answering.
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    r = llm.invoke([SystemMessage(content=(
                        "Rewrite this question as a search query that matches "
                        "formal legal/warranty document wording. Return only "
                        "the rewritten query.")),
                    HumanMessage(content=state.get("retrieval_query") or state["question"])])
    return {**state, "retrieval_query": r.content, "iterations": state["iterations"]+1}

def answer_node(state):
    # Answer is grounded strictly in retrieved sources with citations —
    # for legal/warranty text, an unsupported answer is worse than no
    # answer, so the model is told to say "not covered" instead of guessing.
    # Each chunk is tagged with its real section header (set during
    # ingestion — see ingestion.py's _section_for_chunk) so the model can
    # cite an actual section number instead of inferring/guessing one.
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    txt = "\n\n".join(f"[{d['metadata'].get('section', 'Unknown Section')}]\n{d['content']}"
                      for d in state["documents"])

    # Fix for BUGS.md #20: re-asking the same measurement question could
    # get a different yes/no conclusion each time, even with the same
    # correct source retrieved — the model was doing the "does 1/8 inch
    # exceed 1/32 inch" arithmetic itself, inline with its own judgment
    # call about coverage, and that combined reasoning wasn't stable.
    # compare_measurement_to_sources() does that comparison in code
    # instead, so the LLM is only asked to apply a fixed coverage rule to
    # an already-settled fact rather than also silently doing the math.
    comparison = compare_measurement_to_sources(state["question"], txt)
    if comparison:
        fact_line = (
            f"COMPUTED FACT (pre-calculated, not from the sources — treat as ground truth): "
            f"the measurement in the question is {comparison['measured_inches']:.5f} inches; "
            f"the threshold stated in the sources is {comparison['threshold_inches']:.5f} inches; "
            f"the measurement {'EXCEEDS' if comparison['exceeds_threshold'] else 'DOES NOT EXCEED'} that threshold."
        )
        reasoning_rule = (
            "Reason in two explicit steps: "
            "(1) State the COMPUTED FACT's comparison result — do not recompute or "
            "second-guess the numbers yourself. "
            "(2) Apply this coverage rule: if the measurement EXCEEDS the stated threshold, "
            "that condition fails the performance standard and — per the general repair "
            "obligation for elements that don't meet performance standards during the "
            "warranty period — is a covered defect, UNLESS the sources state an explicit "
            "exclusion for this situation or indicate the warranty period has lapsed. "
            "If the measurement DOES NOT exceed the threshold, it's within tolerance and NOT covered. "
            "State your final Yes/No conclusion clearly, driven by that rule, not by independent judgment."
        )
    else:
        fact_line = ""
        reasoning_rule = ""

    system_content = (
        "Answer using ONLY the sources. Cite the exact section header shown "
        "in brackets before each source (e.g. '§ 7. ...'). Say 'not covered' "
        "if the sources don't address the question."
        + (f" {reasoning_rule}" if reasoning_rule else "")
    )
    user_content = f"Sources:\n{txt}\n\n{fact_line}\n\nQ: {state['question']}"

    r = llm.invoke([
        SystemMessage(content=system_content),
        HumanMessage(content=user_content)])
    cites = re.findall(r'§\s*\d+[^\n.]*|[Ss]ection\s+\d+', r.content)
    return {**state, "answer": r.content, "citations": cites}

def should_rewrite(state):
    # Cap rewrite loops at 2 so a persistently bad match can't loop forever.
    if state["is_relevant"] or state["iterations"] >= 2:
        return "generate_answer"
    return "rewrite"

def build_rag_graph():
    g = StateGraph(RAGState)
    g.add_node("retrieve", retrieve_node)
    g.add_node("grade", grade_node)
    g.add_node("rewrite", rewrite_node)
    g.add_node("generate_answer", answer_node)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", should_rewrite,
                            {"rewrite": "rewrite", "generate_answer": "generate_answer"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate_answer", END)
    return g.compile()

# retrieve -> grade -> (relevant? answer : rewrite -> retrieve, max 2 loops)
# -> answer -> END. The grade/rewrite loop catches wrong retrievals before
# they reach the answer step, which matters for legal text where an
# incorrect answer has real consequences.
rag_agent = build_rag_graph()
