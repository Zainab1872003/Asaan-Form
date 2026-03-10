# FastAPI entry point
# Allow running from this directory (ai-backend/app): add project root to path so "app" package resolves
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from apis.routes import router as document_intake_router
from apis.form_upload import router as form_router
from apis.document_upload import router as document_router
from apis.chatbot import router as chatbot_router
from apis.fill import router as fills
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.on_event("startup")
async def startup_event():
    """
    Preload OCR models in background to avoid blocking first request
    """
    try:
        from app.services.ocr_service import preload_ocr
        print("🚀 Preloading OCR models in background...")
        preload_ocr()
        print("  ✓ OCR preload initiated (models will be ready shortly)")
    except Exception as e:
        print(f"  ⚠️ OCR preload failed: {e}")
        # Continue anyway - OCR will load on first use

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Form routes - for uploading and processing form templates
app.include_router(form_router)

# Document routes - for uploading and processing documents (ID cards, certificates)
app.include_router(document_router)

# Chatbot routes - ingest KB + ask questions via RAG
app.include_router(chatbot_router)

# Legacy document intake route
app.include_router(document_intake_router)
app.include_router(fills)

@app.get("/")
def root():
    return {
        "status": "AI system running",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "endpoints": {
            "forms": "/form - Upload and process form templates",
            "documents": "/document - Upload and process documents (ID cards, etc.)",
            "docs": "/docs - API documentation"
        }
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "services": {
            "api": "running",
            "llm": "configured" if settings.GROQ_API_KEY else "not configured"
        }
    }



# explicitly define port and startup reload or not

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",        # must be a string when using reload=True
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["asaan-env"],
        log_level="info",
        workers=4,
    )