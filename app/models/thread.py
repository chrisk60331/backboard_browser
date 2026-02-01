from pydantic import BaseModel, ConfigDict, field_validator, ValidationInfo
from typing import Optional, List
from datetime import datetime

class Message(BaseModel):
    """Message model."""
    model_config = ConfigDict(extra='allow', strict=False, validate_assignment=False, arbitrary_types_allowed=True)
    
    role: str = 'user'  # Default to 'user', but accept any string value
    content: str = ''
    timestamp: Optional[datetime] = None
    
    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v, info: ValidationInfo):
        """Normalize role to string, accepting any value including 'tool'."""
        # Accept any value and convert to string
        if v is None:
            return 'user'
        return str(v)
    
    def __init__(self, **data):
        # Override __init__ to bypass strict validation on role
        if 'role' in data:
            data['role'] = str(data['role'])
        super().__init__(**data)

class Thread(BaseModel):
    """Thread model."""
    id: Optional[str] = None
    title: Optional[str] = None
    messages: Optional[List[Message]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[dict] = None

class ThreadCreate(BaseModel):
    """Thread creation model."""
    title: Optional[str] = None
    initial_message: Optional[str] = None
    metadata: Optional[dict] = None
