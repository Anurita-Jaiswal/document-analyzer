from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import Document, DocumentPage, User
from backend.app.schemas.extraction import ExtractionRequest, ExtractionResponse, ExtractedField
from backend.app.api.deps import get_current_user
from backend.app.services.generation.generator import generator_service

router = APIRouter()

@router.post("", response_model=ExtractionResponse)
def extract_fields(
    req: ExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not req.document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document_id must be provided for extraction."
        )

    # Verify ownership
    docs = db.query(Document).filter(
        Document.id.in_(req.document_ids),
        Document.user_id == current_user.id,
        Document.status == "ready"
    ).all()

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="None of the selected documents were found, ready, or authorized."
        )

    docs_text = {}
    for doc in docs:
        pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number).all()
        docs_text[doc.original_filename] = "\n".join([p.extracted_text for p in pages if p.extracted_text.strip()])

    target_fields = req.target_fields or [
        "Project Title",
        "Key Stakeholders / Organizations",
        "Critical Dates & Deadlines",
        "Budget / Financial Figures",
        "Major Deliverables",
        "Key Risks",
        "Recommended Action Items"
    ]

    extraction_dict = generator_service.extract_information(docs_text, target_fields)

    field_results = {}
    for k, v in extraction_dict.items():
        if isinstance(v, dict):
            field_results[k] = ExtractedField(
                field_name=v.get("field_name", k),
                value=v.get("value"),
                source_document=v.get("source_document"),
                source_page=v.get("source_page"),
                confidence=v.get("confidence", 0.95 if v.get("status") == "found" else 0.0),
                status=v.get("status", "found" if v.get("value") else "not_found")
            )
        else:
            field_results[k] = ExtractedField(
                field_name=k,
                value=v,
                status="found" if v else "not_found"
            )

    return ExtractionResponse(
        document_ids=[d.id for d in docs],
        extracted_data=field_results,
        processing_notes=f"Extracted {len(target_fields)} fields across {len(docs)} verified document(s)."
    )
