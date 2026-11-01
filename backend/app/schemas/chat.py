from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[str] = None
    chunk_id: Optional[str] = None
    document_id: str
    filename: str
    page: int
    excerpt: str

class MessageCreate(BaseModel):
    question: str
    document_ids: List[str]

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    message_id: str
    role: str
    content: str
    grounding_status: str  # supported, insufficient_evidence, not_found
    trace_id: Optional[str] = None
    citations: List[CitationOut] = []
    created_at: datetime

class ChatSessionCreate(BaseModel):
    title: Optional[str] = "Research Chat"

class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut] = []
