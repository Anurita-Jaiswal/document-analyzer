from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_number: int
    extracted_text: str
    character_count: int
    extraction_status: str

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    page_count: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class DocumentDetailOut(DocumentOut):
    pages: List[DocumentPageOut] = []

class DocumentSummaryRequest(BaseModel):
    focus_area: Optional[str] = None

class DocumentSummaryResponse(BaseModel):
    document_id: str
    document_name: str
    executive_summary: str
    major_findings: List[str]
    key_points: List[str]
    risks_identified: List[str]
    action_items: List[str]
    is_ai_generated: bool = True
