from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .retrieval import build_retriever
import re, logfire

class RAGState(TypedDict):
    question: str
    property_id: str
    doc_type: str
    documents: List[dict]
    is_relevant: bool
    answer: str
    citations: List[str]
    iterations: int

def retrieve_node(state):
    retriever = build_retriever(state["property_id"], state["doc_type"])
    docs = retriever.invoke(state["question"])
    return {**state, "documents":
            [{"content": d.page_content, "metadata": d.metadata} for d in docs]}

def grade_node(state):
    # Cheap relevance check before spending a full answer-generation call
    # on documents that may not actually address the question.
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    txt = "\n\n".join(d["content"] for d in state["documents"])
    g = llm.invoke([SystemMessage(content="Are these docs relevant? YES or NO only."),
                    HumanMessage(content=f"Q: {state['question']}\n\n{txt}")])
    return {**state, "is_relevant": "YES" in g.content.upper()}

def rewrite_node(state):
    # If retrieval missed, rephrase the question to better match how the
    # source document is likely worded (e.g. legal/technical phrasing)
    # and try retrieval again.
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    r = llm.invoke([SystemMessage(content="Rewrite to improve retrieval."),
                    HumanMessage(content=state["question"])])
    return {**state, "question": r.content, "iterations": state["iterations"]+1}

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
    r = llm.invoke([
        SystemMessage(content="Answer using ONLY the sources. Cite the exact "
                              "section header shown in brackets before each "
                              "source (e.g. '§ 7. ...'). Say 'not covered' "
                              "if the sources don't address the question."),
        HumanMessage(content=f"Sources:\n{txt}\n\nQ: {state['question']}")])
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
