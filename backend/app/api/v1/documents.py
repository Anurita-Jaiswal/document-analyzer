import os
import uuid
import threading
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import User, Document, DocumentPage, ProcessingJob
from backend.app.schemas.document import (
    DocumentOut,
    DocumentDetailOut,
    DocumentSummaryRequest,
    DocumentSummaryResponse
)
from backend.app.schemas.extraction import ExtractionRequest, ExtractionResponse
from backend.app.schemas.job import JobOut
from backend.app.core.config import settings
from backend.app.api.deps import get_current_user
from backend.app.workers.processor import process_document_job
from backend.app.services.generation.generator import generator_service

router = APIRouter()

@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    original_name = file.filename or "untitled"
    ext = os.path.splitext(original_name)[1].lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Read content and validate size
    content = await file.read()
    size_bytes = len(content)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # Generate secure storage path
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}{ext}"
    storage_path = os.path.join(settings.STORAGE_DIR, stored_filename)

    with open(storage_path, "wb") as f:
        f.write(content)

    # Create Document record
    doc = Document(
        id=file_id,
        user_id=current_user.id,
        filename=stored_filename,
        original_filename=original_name,
        storage_key=storage_path,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        status="queued"
    )
    db.add(doc)

    # Create ProcessingJob record
    job = ProcessingJob(
        document_id=doc.id,
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    # Dispatch asynchronous indexing
    background_tasks.add_task(process_document_job, job.id, doc.id)

    return doc

@router.get("", response_model=List[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc()).all()

@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

    return doc

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

    # Remove underlying file if it exists
    if os.path.exists(doc.storage_key):
        try:
            os.remove(doc.storage_key)
        except Exception:
            pass

    # Cascades will clean up document_pages, chunks, jobs, and citations
    db.delete(doc)
    db.commit()

    return {"message": "Document and all associated vector indexes successfully deleted.", "document_id": document_id}

@router.post("/{document_id}/summary", response_model=DocumentSummaryResponse)
def get_document_summary(
    document_id: str,
    req: DocumentSummaryRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

    if doc.status != "ready":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Document is in '{doc.status}' state and not yet ready for summarization.")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number).all()
    pages_text = [p.extracted_text for p in pages if p.extracted_text.strip()]

    summary_data = generator_service.summarize_document(doc.original_filename, pages_text)

    return DocumentSummaryResponse(
        document_id=doc.id,
        document_name=doc.original_filename,
        executive_summary=summary_data.get("executive_summary", ""),
        major_findings=summary_data.get("major_findings", []),
        key_points=summary_data.get("key_points", []),
        risks_identified=summary_data.get("risks_identified", []),
        action_items=summary_data.get("action_items", []),
        is_ai_generated=True
    )
