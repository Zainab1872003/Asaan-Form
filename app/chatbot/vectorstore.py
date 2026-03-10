"""
Professional vector store management for Zilliz Cloud (Milvus) with optimized batch processing.
Migrated from Pinecone; maintains API compatibility for RAG workflows.
"""
import hashlib
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from langchain_milvus import Milvus
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from app.chatbot.embeddings import get_embeddings_model
from app.config import settings

logger = logging.getLogger(__name__)

class VectorStoreError(Exception):
    """Custom exception for vector store operations."""
    pass

class MilvusManager:
    """Professional Zilliz Cloud (Milvus) vector store manager."""
    
    def __init__(self, collection_name: str = settings.MILVUS_COLLECTION_NAME, dimension: int = settings.MILVUS_DIMENSION):
        if not re.match(r'^[a-zA-Z0-9_]+$', collection_name):
            raise VectorStoreError(f"Invalid collection name '{collection_name}'. Use only letters, numbers, and underscores.")
        self.collection_name = collection_name
        self.dimension = dimension
        self._validate_environment()
    
    def _validate_environment(self):
        """Validate Zilliz Cloud connection params."""
        if not settings.MILVUS_URI or not settings.MILVUS_PASSWORD:
            raise VectorStoreError("MILVUS_URI or MILVUS_PASSWORD not set in config/.env!")
        if settings.MILVUS_USER and settings.MILVUS_USER.strip():
            logger.warning("MILVUS_USER should be empty for API key auth; ignoring.")
    
    def init_milvus(self) -> None:
        """Connect to Zilliz Cloud (Milvus) and create collection if needed."""
        try:
            connections.connect(
                alias="default",
                uri=settings.MILVUS_URI,
                token=settings.MILVUS_PASSWORD,
                secure=True
            )
            logger.info(f"Connected to Zilliz Cloud at {settings.MILVUS_URI}")
            
            if not utility.has_collection(self.collection_name):
                self._create_collection()
                logger.info(f"Created new Zilliz collection: {self.collection_name}")
            else:
                logger.info(f"Using existing Zilliz collection: {self.collection_name} (drop in UI if schema outdated)")
        except Exception as e:
            raise VectorStoreError(f"Failed to initialize Zilliz Cloud: {e}")
    
    def _create_collection(self) -> None:
        """Create Milvus collection with schema aligned to LangChain defaults."""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64, default_value=0),
            FieldSchema(name="metadata", dtype=DataType.JSON)
        ]
        schema = CollectionSchema(fields, description="RAG Document Chunks")
        collection = Collection(self.collection_name, schema)
        
        if not collection.has_index():
            index_params = {
                "metric_type": settings.MILVUS_METRIC_TYPE,
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 200}
            }
            collection.create_index(field_name="vector", index_params=index_params)
            logger.info(f"Created index on 'vector' field for '{self.collection_name}'")
        
        collection.load()
        collection.flush()
    
    @staticmethod
    def generate_document_id(filename: str, upload_date: str) -> str:
        """Generate unique document ID from filename and upload date using SHA-256."""
        content = f"{filename}_{upload_date}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    @staticmethod
    def create_chunk_id(filename: str, chunk_index: int) -> str:
        """Create consistent chunk ID for updates."""
        return f"{filename}#chunk_{chunk_index}"

class DocumentStore:
    """High-level document storage interface for Zilliz Cloud (Milvus)."""
    
    def __init__(self, collection_name: str = settings.MILVUS_COLLECTION_NAME):
        self.manager = MilvusManager(collection_name)
        self.embeddings = get_embeddings_model()
        self._collection = None
    
    @property
    def collection(self) -> Collection:
        """Get Milvus collection (initialize if needed)."""
        if self._collection is None:
            self.manager.init_milvus()
            self._collection = Collection(self.manager.collection_name)
            self._collection.load()
        return self._collection
    
    def store_documents(
        self,
        docs: List[Any],
        filename: str,
        file_size: int,
        max_batch_size: int = 1000,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[Optional[Milvus], str]:
        """Store documents with optimized batch processing."""
        if not docs:
            logger.warning("No documents provided for storage")
            return None, None
        
        try:
            self.manager.init_milvus()
            upload_date = datetime.now().isoformat()
            document_id = self.manager.generate_document_id(filename, upload_date)
            
            # Embed all documents
            texts = [doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in docs]
            logger.info(f"Embedding {len(texts)} chunks for {filename}")
            all_embeddings = self.embeddings.embed_documents(texts)
            
            # Batch insert
            total_stored = self._batch_insert_vectors(
                docs, all_embeddings, filename, file_size, document_id, upload_date, 
                max_batch_size, extra_metadata
            )
            
            logger.info(f"Successfully stored {total_stored} chunks for {filename}")
            
            # Create LangChain wrapper
            vectorstore = self._create_langchain_wrapper()
            return vectorstore, document_id
            
        except Exception as e:
            logger.error(f"Failed to store documents for {filename}: {e}")
            raise VectorStoreError(f"Document storage failed: {e}")
    
    def _batch_insert_vectors(
        self, docs: List[Any], embeddings: List[List[float]], filename: str, 
        file_size: int, document_id: str, upload_date: str, max_batch_size: int,
        extra_metadata: Optional[Dict[str, Any]]
    ) -> int:
        """Batch insert vectors to Milvus."""
        total_stored = 0
        batch_count = 0
        
        # Process in batches
        for i in range(0, len(docs), max_batch_size):
            batch_docs = docs[i:i + max_batch_size]
            batch_embeddings = embeddings[i:i + max_batch_size]
            
            # Prepare batch data - MUST be lists of individual values
            batch_data = []
            
            for j, (doc, embedding) in enumerate(zip(batch_docs, batch_embeddings)):
                chunk_index = i + j
                chunk_id = self.manager.create_chunk_id(filename, chunk_index)
                
                # Get metadata
                metadata = dict(getattr(doc, "metadata", {}) or {})
                if extra_metadata:
                    metadata.update(extra_metadata)
                
                metadata.update({
                    "document_id": document_id,
                    "filename": filename,
                    "file_type": filename.split(".")[-1].lower(),
                    "upload_date": upload_date,
                    "chunk_index": chunk_index,
                    "file_size": file_size,
                    "total_chunks": len(docs)
                })
                
                text_content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                
                # Each item is a dict representing one entity
                entity = {
                    "id": chunk_id,
                    "vector": embedding,
                    "text": text_content,
                    "filename": filename,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "metadata": metadata
                }
                batch_data.append(entity)
            
            # Insert batch
            try:
                self.collection.insert(batch_data)
                batch_count += 1
                total_stored += len(batch_data)
                logger.info(f"Inserted batch {batch_count}: {len(batch_data)} chunks")
            except Exception as e:
                logger.error(f"Failed to insert batch {batch_count}: {e}")
                raise
        
        self.collection.flush()
        logger.info(f"Successfully stored {total_stored} chunks in {batch_count} batches")
        return total_stored

    
    def _create_langchain_wrapper(self) -> Optional[Milvus]:
        """Create LangChain Milvus wrapper."""
        try:
            return Milvus(
                embedding_function=self.embeddings,
                collection_name=self.manager.collection_name,
                connection_args={
                    "uri": settings.MILVUS_URI,
                    "token": settings.MILVUS_PASSWORD,
                    "secure": True
                },
                text_field="text",
                vector_field="vector"
            )
        except Exception as e:
            logger.warning(f"Failed to create LangChain wrapper: {e}")
            return None
    
    def delete_document_by_filename(self, filename: str) -> bool:
        """Delete all chunks of a document by filename with pagination."""
        try:
            self.manager.init_milvus()
            expr = f'filename == "{filename}"'
            
            # Paginate IDs to respect Zilliz 16384 limit
            all_ids = []
            offset = 0
            batch_limit = 16383
            
            while True:
                results = self.collection.query(
                    expr=expr,
                    output_fields=["id"],
                    limit=batch_limit,
                    offset=offset
                )
                if not results or not results:
                    break
                all_ids.extend(results)
                offset += len(results)
                if len(results) < batch_limit:
                    break
            
            if not all_ids:
                logger.info(f"No chunks found for {filename}; nothing to delete")
                return True
            
            # Extract IDs from results (format: list of dicts with 'id' key)
            id_list = [item['id'] if isinstance(item, dict) else str(item) for item in all_ids]
            
            # Delete using expr with ID list
            id_list_str = ', '.join([f'"{id}"' for id in id_list])
            delete_expr = f'id in [{id_list_str}]'
            self.collection.delete(expr=delete_expr)
            self.collection.flush()
            
            logger.info(f"Deleted {len(id_list)} chunks for document {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def delete_all_documents(self) -> bool:
        """Delete all documents from the collection."""
        try:
            self.manager.init_milvus()
            self.collection.delete(expr="id != ''")
            self.collection.flush()
            logger.info("Deleted all documents from collection")
            return True
        except Exception as e:
            logger.error(f"Failed to delete all documents: {e}")
            return False
    
    def check_connection(self) -> bool:
        """Check if Milvus connection is working."""
        try:
            self.manager.init_milvus()
            return utility.has_collection(self.manager.collection_name)
        except Exception as e:
            logger.error(f"Milvus connection check failed: {e}")
            return False

# Convenience functions
def init_milvus(collection_name: str = settings.MILVUS_COLLECTION_NAME) -> None:
    """Initialize Milvus (backward compatibility)."""
    manager = MilvusManager(collection_name)
    manager.init_milvus()

def check_milvus_connection(collection_name: str = settings.MILVUS_COLLECTION_NAME) -> bool:
    """Check connection (backward compatibility)."""
    store = DocumentStore(collection_name)
    return store.check_connection()