"""
RAG Chain module for document querying using Milvus (Zilliz Cloud) vector store.
Uses Groq LLM + retriever for question answering.
"""

from app.chatbot.vectorstore import init_milvus, DocumentStore
from app.utils.llm import get_llm, generate_response_from_prompt


# ---- Retriever ----
def get_retriever(collection_name: str = "rag_langchain", k: int = 3):
    """
    Initialize Milvus vector store and return a LangChain retriever.
    
    Args:
        collection_name: Milvus collection name (underscore for validity).
        k: Number of top documents to retrieve.
    
    Returns:
        LangChain retriever instance.
    """
    init_milvus(collection_name=collection_name)  # Ensures connection and collection setup
    
    # Reuse DocumentStore for correct Milvus wrapper (avoids direct init arg errors)
    store = DocumentStore(collection_name=collection_name)
    vectorstore = store._create_langchain_wrapper()  # Handles embedding_function, token auth, schema
    
    if vectorstore is None:
        raise ValueError(f"Failed to create Milvus vectorstore for collection '{collection_name}'")
    
    return vectorstore.as_retriever(search_kwargs={"k": k})


def _format_docs(docs):
    """Format retrieved documents into a single string."""
    return "\n\n".join(doc.page_content for doc in docs)


RAG_PROMPT_TEMPLATE = (
    "You are a careful RAG assistant.\n"
    "Use ONLY the provided context to answer the question. "
    "If the answer is not in the context, say you don't know.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


def get_rag_chain(collection_name: str = "rag_langchain", k: int = 3):
    """
    Returns a callable that runs RAG: retrieve + Groq LLM.
    """
    retriever = get_retriever(collection_name=collection_name, k=k)
    llm_client = get_llm()

    def invoke(question: str) -> str:
        docs = retriever.invoke(question)
        context = _format_docs(docs)
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)
        return generate_response_from_prompt(llm_client, prompt)
    return invoke


def get_rag_chain_with_sources(collection_name: str = "rag_langchain", k: int = 3):
    """
    Returns a RAG callable that includes source documents in the response.
    Returns:
        Dict with 'result' and 'source_documents' keys.
    """
    retriever = get_retriever(collection_name=collection_name, k=k)
    llm_client = get_llm()

    def rag_with_sources(question: str):
        docs = retriever.invoke(question)
        context = _format_docs(docs)
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)
        answer = generate_response_from_prompt(llm_client, prompt)
        return {
            "result": answer,
            "source_documents": docs,
        }
    return rag_with_sources