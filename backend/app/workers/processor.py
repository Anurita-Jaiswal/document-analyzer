import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.models import Document, DocumentPage, Chunk, ProcessingJob
from backend.app.services.document_parser.parser import DocumentParserService
from backend.app.services.chunking.chunker import TextChunkerService
from backend.app.services.embeddings.embedder import embedding_service

logger = logging.getLogger("documind.worker")

def process_document_job(job_id: str, document_id: str):
    db: Session = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        doc = db.query(Document).filter(Document.id == document_id).first()

        if not job or not doc:
            logger.error(f"Job {job_id} or Document {document_id} not found.")
            return

        # 1. Transition to 'processing'
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        doc.status = "processing"
        db.commit()

        # 2. Extract pages using parser
        extracted_pages = DocumentParserService.extract_document(doc.storage_key, doc.mime_type)

        if not extracted_pages or all(len(p.text.strip()) == 0 for p in extracted_pages):
            raise ValueError("Document contains no extractable text. May be an empty file or image scan requiring OCR.")

        # 3. Clean up existing pages/chunks for idempotency
        db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.commit()

        # 4. Save DocumentPage records
        for p in extracted_pages:
            db_page = DocumentPage(
                document_id=doc.id,
                page_number=p.page_number,
                extracted_text=p.text,
                character_count=p.character_count,
                extraction_status="completed"
            )
            db.add(db_page)
        
        doc.page_count = len(extracted_pages)
        db.commit()

        # 5. Chunk the text
        chunker = TextChunkerService()
        chunk_items = chunker.chunk_pages(extracted_pages, doc.id)

        # 6. Generate embeddings and save Chunks
        for c in chunk_items:
            vector = embedding_service.get_embedding(c.text)
            db_chunk = Chunk(
                document_id=doc.id,
                chunk_index=c.chunk_index,
                page_start=c.page_start,
                page_end=c.page_end,
                text=c.text,
                section_title=c.section_title,
                embedding_json=json.dumps(vector),
                metadata_json=c.metadata
            )
            db.add(db_chunk)

        # 7. Transition to 'ready' / 'completed'
        doc.status = "ready"
        doc.error_message = None
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Successfully processed document {doc.id} ({doc.original_filename})")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}", exc_info=True)
        db.rollback()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            doc = db.query(Document).filter(Document.id == document_id).first()
            if job:
                job.status = "failed"
                job.error_code = "PROCESSING_ERROR"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
