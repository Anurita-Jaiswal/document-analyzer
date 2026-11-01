from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    status: str  # queued, processing, completed, failed
    attempts: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
