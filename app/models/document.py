from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Document(BaseModel):
    """Document model."""
    id: Optional[str] = None
    name: str
    type: Optional[str] = None
    size: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    url: Optional[str] = None

class DocumentCreate(BaseModel):
    """Document creation model."""
    name: str
    type: Optional[str] = None
    metadata: Optional[dict] = None
