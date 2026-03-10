# Env & settings
import os
from pathlib import Path
from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    """Application configuration settings"""
    
    # ========================================================================
    # PROJECT INFO
    # ========================================================================
    PROJECT_NAME: str = "Asaan Form FYP"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "AI-powered form processing system"
    
    # ========================================================================
    # API SETTINGS
    # ========================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # ========================================================================
    # LLM CONFIGURATION (Groq)
    # ========================================================================
    GROQ_API_KEY: str = ""
    # Groq model: llama-3.1-8b-instant (fast) or llama-3.3-70b-versatile (larger)
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 8000
    

    
    # Milvus Settings
    # Zilliz Cloud (Milvus) Settings
    # Zilliz Cloud (Milvus) Settings
    MILVUS_URI: str = ""
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION_NAME: str = "rag_langchain"
    MILVUS_DIMENSION: int = 384
    MILVUS_METRIC_TYPE: str = "COSINE"

    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "form_processing"
    MONGODB_COLLECTION: str = "forms"

    # Embedding Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    EMBEDDING_DIMENSION: int = 384  # all-MiniLM-L6-v2 dimension





    # ========================================================================
    # FILE STORAGE
    # ========================================================================
    BASE_DIR: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads1"
    USERS_DIR: Path = UPLOAD_DIR / "users"  # Root for all user folders
    OUTPUT_DIR: Path = UPLOAD_DIR / "output"
    
    # File upload limits
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: list = [".pdf", ".png", ".jpg", ".jpeg" , ".docx", ".doc"]
    
    # PDF conversion settings
    PDF_DPI: int = 300  # DPI for PDF to image conversion
    
    # ========================================================================
    # FORM PROCESSING SETTINGS
    # ========================================================================
    # JSON chunking for LLM (increased since we're not sending markdown anymore)
    MAX_JSON_CHUNK_SIZE: int = 20000
    
    # Docling settings
    DOCLING_DO_TABLE_STRUCTURE: bool = True
    DOCLING_GENERATE_PAGE_IMAGES: bool = True
    DOCLING_DO_OCR: bool = True  # Use built-in OCR for PDFs
    
    # ========================================================================
    # CORS SETTINGS
    # ========================================================================
    CORS_ORIGINS: list = ["*"]
    
    class Config:
        # Load .env from project root (ai-backend) so it works when running from app/
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        case_sensitive = True
        extra = "ignore"

        
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        self._create_directories()
    
    def _create_directories(self):
        """Create required directories if they don't exist"""
        for directory in [
            self.UPLOAD_DIR,
            self.USERS_DIR,
            self.OUTPUT_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_user_dir(self, user_id: str) -> Path:
        """Get user's root directory"""
        user_dir = self.USERS_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def get_user_forms_dir(self, user_id: str) -> Path:
        """Get user's forms directory"""
        forms_dir = self.get_user_dir(user_id) / "forms"
        forms_dir.mkdir(parents=True, exist_ok=True)
        return forms_dir
    
    def get_user_documents_dir(self, user_id: str) -> Path:
        """Get user's documents directory"""
        docs_dir = self.get_user_dir(user_id) / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir
    
    def get_user_output_dir(self, user_id: str) -> Path:
        """Get user's output directory for processed results"""
        output_dir = self.get_user_dir(user_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


# Create global settings instance
settings = Settings()


# Helper function to validate settings
def validate_settings():
    """Validate critical settings"""
    errors = []
    
    if not settings.GROQ_API_KEY:
        errors.append("GROQ_API_KEY is not set")
    
    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    
    return True


# Print settings on import (for debugging)
def print_settings():
    """Print current settings (for debugging)"""
    print("\n" + "="*60)
    print("⚙️  APPLICATION SETTINGS")
    print("="*60)
    print(f"Project: {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"Debug: {settings.DEBUG}")
    print(f"API: {settings.API_HOST}:{settings.API_PORT}")
    print("\nLLM (Groq):")
    print(f"  Model: {settings.LLM_MODEL}")
    print(f"  Temperature: {settings.LLM_TEMPERATURE}")
    print("\nDirectories:")
    print(f"  Upload: {settings.UPLOAD_DIR}")
    print(f"  Output: {settings.OUTPUT_DIR}")
    print("\nFile Limits:")
    print(f"  Max size: {settings.MAX_FILE_SIZE / (1024*1024):.0f} MB")
    print(f"  Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Test the config
    print_settings()
    validate_settings()
    print("✅ Configuration valid!\n")