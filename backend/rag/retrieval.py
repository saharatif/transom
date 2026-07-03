from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

def build_retriever(property_id, doc_type="warranty"):
    """Build a retriever scoped to one property's namespace: MMR search
    over Pinecone for a broad, diverse candidate set (fetch_k=20), then a
    cross-encoder reranker narrows it down to the top matches. MMR +
    reranking gives better precision than a plain top-k similarity search
    for legal/warranty text, where the top-k nearest neighbors by
    embedding distance can still be off-topic.

    k=6 / top_n=4 (rather than k=5 / top_n=3): testing against a real
    warranty clause found the cross-encoder can rank a lexically-similar
    but semantically wrong chunk above the correct one (e.g. a stucco
    crack-width clause outranking the drywall crack-width clause because
    both mention a specific fraction-of-an-inch number). A tighter top_n
    silently dropped the correct chunk from the final context. Widening
    both stages reduces the chance the reranker discards the right answer
    before it ever reaches the LLM.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = PineconeVectorStore(
        index_name="property-intelligence", embedding=embeddings,
        namespace=f"property_{property_id}_{doc_type}")
    base = vs.as_retriever(search_type="mmr",
                           search_kwargs={"k": 6, "fetch_k": 24, "lambda_mult": 0.5})
    reranker = CrossEncoderReranker(
        model=HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base"),
        top_n=4)
    return ContextualCompressionRetriever(
        base_compressor=reranker, base_retriever=base)
