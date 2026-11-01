from typing import List, Optional, Any, Dict
from pydantic import BaseModel

class ExtractedField(BaseModel):
    field_name: str
    value: Optional[Any] = None
    source_document: Optional[str] = None
    source_page: Optional[int] = None
    confidence: Optional[float] = None
    status: str = "found"  # found, not_found, partial

class ExtractionRequest(BaseModel):
    document_ids: List[str]
    target_fields: Optional[List[str]] = [
        "Project Title",
        "Key Stakeholders / Organizations",
        "Critical Dates & Deadlines",
        "Budget / Financial Figures",
        "Major Deliverables",
        "Key Risks",
        "Recommended Action Items"
    ]

class ExtractionResponse(BaseModel):
    document_ids: List[str]
    extracted_data: Dict[str, ExtractedField]
    raw_json: Optional[Dict[str, Any]] = None
    processing_notes: Optional[str] = None
