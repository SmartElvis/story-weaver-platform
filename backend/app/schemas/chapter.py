import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChapterCreate(BaseModel):
    chapter_number: int = Field(..., ge=1)
    title: Optional[str] = None
    direction: Optional[str] = None
    user_content: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = Field(
        None, pattern="^(OUTLINE|DRAFTING|REVIEW|REVISION|FINALIZED)$"
    )
    direction: Optional[str] = None
    draft_content: Optional[str] = None
    final_content: Optional[str] = None
    logic_review: Optional[dict] = None
    style_review: Optional[dict] = None
    extraction_result: Optional[dict] = None
    next_chapter_suggestion: Optional[dict] = None
    revision_count: Optional[int] = None
    tokens_used: Optional[int] = None
    generation_cost: Optional[dict] = None


class ChapterResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_number: int
    title: Optional[str] = None
    status: str
    direction: Optional[str] = None
    draft_content: Optional[str] = None
    final_content: Optional[str] = None
    logic_review: Optional[dict] = None
    style_review: Optional[dict] = None
    extraction_result: Optional[dict] = None
    next_chapter_suggestion: Optional[dict] = None
    revision_count: int
    tokens_used: int
    generation_cost: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
