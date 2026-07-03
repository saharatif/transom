from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from ..redaction.pii import redact_and_tokenize
import re, logfire

# RAG is only for long, open-ended documents (warranty, legal contracts,
# historical inspection reports) where the questions people will ask
# aren't known in advance — everything else in this system is structured
# extraction or deterministic code. See Module 1 §3.

# Matches section headers like "§ 7. Performance Standards for Drywall".
_SECTION_HEADER = re.compile(r"§\s*\d+\.[^\n]*")


def _section_map(text):
    """Return [(char_offset, header_text), ...] for every section header
    found in the document, in order. Used to tag each chunk with the
    section it actually falls under, since a chunk_size of 800 chars can
    span past a section's own header (e.g. sub-points (b)/(c)/(d) landing
    in a chunk that doesn't repeat the "§ 7. ..." header itself).
    """
    return [(m.start(), m.group().strip()) for m in _SECTION_HEADER.finditer(text)]


def _section_for_chunk(chunk_text, full_text, section_map, search_from=0):
    """Find where chunk_text sits in full_text and return the nearest
    preceding section header, so citations can be grounded in real
    section numbers instead of the LLM guessing from surrounding prose.
    """
    idx = full_text.find(chunk_text, search_from)
    if idx == -1:
        idx = full_text.find(chunk_text)
    section = "Unknown Section"
    for start, header in section_map:
        if start <= idx:
            section = header
        else:
            break
    return section, idx


@logfire.instrument()
def ingest_document(pdf_path, property_id, doc_id, db_path, doc_type="warranty"):
    """Load a long-form PDF, redact PII, chunk it along document structure,
    tag each chunk with its real section header, and store the embedded
    chunks in Pinecone under a property+doc_type namespace so retrieval
    can be scoped per property later.
    """
    loader = PyMuPDFLoader(pdf_path)
    raw_text = "\n\n".join(d.page_content for d in loader.load())

    # Redact PII (builder name/phone/email/address in headers) before this
    # text is chunked, embedded, or sent to any external API.
    clean_text = redact_and_tokenize(raw_text, doc_id, db_path)

    # Structural chunking — split on section markers first, falling back
    # to paragraph/line/word boundaries, so a chunk doesn't cut a legal
    # clause in half mid-section.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=100,
        separators=["\n§ ", "\n(a)", "\n(b)", "\n\n", "\n", " "])
    chunks = splitter.create_documents(
        [clean_text],
        metadatas=[{"doc_id": doc_id, "doc_type": doc_type,
                    "property_id": property_id, "source": pdf_path}])

    # Tag each chunk with its real section header (e.g. "§ 7. Performance
    # Standards for Drywall") so answer_node can cite an actual section
    # number instead of inferring one from prose. search_from tracks
    # position to keep repeated/similar chunk text resolving in document
    # order rather than always matching the first occurrence.
    section_map = _section_map(clean_text)
    search_from = 0
    for chunk in chunks:
        section, idx = _section_for_chunk(chunk.page_content, clean_text, section_map, search_from)
        chunk.metadata["section"] = section
        if idx != -1:
            search_from = idx

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    # One namespace per property+doc_type keeps retrieval scoped to the
    # right property and document type at query time.
    namespace = f"property_{property_id}_{doc_type}"
    PineconeVectorStore.from_documents(
        documents=chunks, embedding=embeddings,
        index_name="property-intelligence", namespace=namespace)

    logfire.info("document_ingested", chunks=len(chunks), namespace=namespace)
    return {"chunks": len(chunks), "namespace": namespace}
