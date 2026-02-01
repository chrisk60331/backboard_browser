from pydantic import BaseModel
from typing import Optional, List

class ModelInfo(BaseModel):
    """Model information model."""
    id: str
    name: str
    provider: Optional[str] = None
    capabilities: Optional[List[str]] = None
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    supports_streaming: Optional[bool] = None
