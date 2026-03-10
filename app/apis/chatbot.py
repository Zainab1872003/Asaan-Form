"""
Chatbot API Routes
 - Upload/ingest FAQ (knowledge base) files into Milvus (Zilliz Cloud)
 - Ask questions answered via RAG over the stored knowledge base
"""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import os
from typing import List, Optional, Dict, Any

from config import settings
from chatbot.document_loader import load_and_chunk_file
from chatbot.vectorstore import DocumentStore
from chatbot.rag_chain import get_rag_chain_with_sources


router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


def _save_upload_to_disk(file: UploadFile, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    out_path = target_dir / f"{uuid.uuid4()}_{safe_name}"
    with out_path.open("wb") as f:
        f.write(file.file.read())
    return out_path


@router.post("/ingest")
async def ingest_faq_files(
    files: List[UploadFile] = File(..., description="FAQ / knowledge base files (.pdf, .docx, .pptx, .xlsx, .txt)"),
    collection_name: str = Query(settings.MILVUS_COLLECTION_NAME, description="Milvus collection name (knowledge base)"),
    source: str = Query("faqs", description="Metadata label for these documents"),
):
    """
    Upload and ingest knowledge-base files into the vector store.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Store raw uploads under uploads/kb/<collection>/
    kb_dir = Path(settings.UPLOAD_DIR) / "kb" / collection_name

    store = DocumentStore(collection_name=collection_name)

    results: List[Dict[str, Any]] = []
    total_chunks = 0

    for file in files:
        if not file.filename:
            results.append({"success": False, "error": "Missing filename"})
            continue

        file_ext = Path(file.filename).suffix.lower()
        allowed = [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"]
        if file_ext not in allowed:
            results.append({
                "success": False,
                "filename": file.filename,
                "error": f"Invalid file type '{file_ext}'. Allowed: {allowed}",
            })
            continue

        try:
            saved_path = _save_upload_to_disk(file, kb_dir)
            chunks = load_and_chunk_file(
                str(saved_path),
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )

            if not chunks:
                results.append({
                    "success": False,
                    "filename": file.filename,
                    "saved_path": str(saved_path),
                    "error": "No text could be extracted from this file",
                })
                continue

            vectorstore, document_id = store.store_documents(
                docs=chunks,
                filename=saved_path.name,
                file_size=saved_path.stat().st_size,
                extra_metadata={"source": source},
            )

            results.append({
                "success": True,
                "filename": file.filename,
                "saved_path": str(saved_path),
                "document_id": document_id,
                "chunks": len(chunks),
            })
            total_chunks += len(chunks)

        except Exception as e:
            results.append({
                "success": False,
                "filename": file.filename,
                "error": str(e),
            })

    return JSONResponse(content={
        "collection_name": collection_name,
        "total_files": len(files),
        "total_chunks": total_chunks,
        "results": results,
    })


@router.post("/ask")
async def ask_chatbot(
    question: str = Query(..., description="User question"),
    collection_name: str = Query(settings.MILVUS_COLLECTION_NAME, description="Milvus collection name (knowledge base)"),
    k: int = Query(3, ge=1, le=10, description="Top-k chunks to retrieve"),
):
    """
    Ask a question. The answer is generated using retrieved context from the vector store.
    """
    try:
        qa = get_rag_chain_with_sources(collection_name=collection_name, k=k)
        result = qa(question)

        answer = result.get("result")
        sources = []
        for d in result.get("source_documents") or []:
            meta = dict(getattr(d, "metadata", {}) or {})
            sources.append({
                "filename": meta.get("filename") or meta.get("source"),
                "page_number": meta.get("page_number"),
                "chunk_reference": meta.get("chunk_reference"),
            })

        return JSONResponse(content={
            "collection_name": collection_name,
            "question": question,
            "answer": answer,
            "sources": sources,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
