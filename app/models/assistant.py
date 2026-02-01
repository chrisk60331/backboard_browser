from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Assistant(BaseModel):
    """Assistant model."""
    id: Optional[str] = None
    name: str
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[dict] = None

class AssistantCreate(BaseModel):
    """Assistant creation model."""
    name: str
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    metadata: Optional[dict] = None

class AssistantUpdate(BaseModel):
    """Assistant update model."""
    name: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    metadata: Optional[dict] = None
