# embeddings.py
from langchain_huggingface import HuggingFaceEmbeddings


def get_embeddings_model():
    """
    Returns a HuggingFace embedding model.
    Default: all-MiniLM-L6-v2 (768d)
    """
    model_name = "sentence-transformers/all-MiniLM-L6-v2"

    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    return embeddings