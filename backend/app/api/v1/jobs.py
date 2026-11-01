from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models import ProcessingJob, Document, User
from backend.app.schemas.job import JobOut
from backend.app.api.deps import get_current_user

router = APIRouter()

@router.get("/{job_id}", response_model=JobOut)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = db.query(ProcessingJob).join(Document, ProcessingJob.document_id == Document.id).filter(
        ProcessingJob.id == job_id,
        Document.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found or access denied."
        )

    return job
