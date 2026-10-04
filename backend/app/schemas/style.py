import uuid
from typing import Optional, List

from pydantic import BaseModel, Field


class StyleProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    author_name: Optional[str] = None
    description: Optional[str] = None
    source_books: Optional[List[dict]] = None


class StyleProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    author_name: Optional[str] = None
    description: Optional[str] = None
    source_books: Optional[List[dict]] = None
    total_chunks: Optional[int] = None
    style_features: Optional[dict] = None


class StyleProfileResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    author_name: Optional[str] = None
    description: Optional[str] = None
    source_books: Optional[List[dict]] = None
    total_chunks: int
    style_features: Optional[dict] = None
    processing_status: Optional[str] = None

    model_config = {"from_attributes": True}
