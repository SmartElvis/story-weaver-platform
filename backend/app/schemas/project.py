import uuid
from datetime import datetime
from typing import Optional, List, Any, Union

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None
    outline: Optional[str] = None
    character_cards: Optional[Union[List[dict], dict]] = None
    world_settings: Optional[dict] = None
    writing_preferences: Optional[Union[dict, str]] = None
    style_controls: Optional[dict] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None
    outline: Optional[str] = None
    character_cards: Optional[Union[List[dict], dict]] = None
    world_settings: Optional[dict] = None
    active_style_id: Optional[uuid.UUID] = None
    writing_preferences: Optional[Union[dict, str]] = None
    style_controls: Optional[dict] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    outline: Optional[str] = None
    character_cards: Optional[Union[List[dict], dict]] = None
    world_settings: Optional[dict] = None
    active_style_id: Optional[uuid.UUID] = None
    writing_preferences: Optional[Union[dict, str]] = None
    style_controls: Optional[dict] = None
    arc_plan: Optional[dict] = None

    model_config = {"from_attributes": True}
