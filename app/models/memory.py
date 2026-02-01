from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Memory(BaseModel):
    """Memory model."""
    id: Optional[str] = None
    content: str
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MemoryCreate(BaseModel):
    """Memory creation model."""
    content: str
    metadata: Optional[dict] = None
    tags: Optional[List[str]] = None

class MemorySearch(BaseModel):
    """Memory search model."""
    query: str
    limit: Optional[int] = 10
    tags: Optional[List[str]] = None
