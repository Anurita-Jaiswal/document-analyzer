from fastapi import APIRouter
from backend.app.api.v1 import auth, documents, chat, jobs, health, extraction

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["Research Chat"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(extraction.router, prefix="/extraction", tags=["Information Extraction"])
api_router.include_router(health.router, tags=["Health & Observability"])
