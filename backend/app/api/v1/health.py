from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db.session import get_db
from backend.app.core.config import settings

router = APIRouter()

@router.get("/health", response_model=Dict[str, Any])
def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    has_gemini = bool(settings.GEMINI_API_KEY)

    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status,
        "ai_engine": {
            "provider": "Google Gemini" if has_gemini else "DocuMind Offline Semantic Engine",
            "model": settings.GENERATION_MODEL if has_gemini else "Deterministic Grounded RAG",
            "embedding": settings.EMBEDDING_MODEL if has_gemini else "768-dim Semantic Vectorizer",
            "gemini_api_key_configured": has_gemini
        }
    }
