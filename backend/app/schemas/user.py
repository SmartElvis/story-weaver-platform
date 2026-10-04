import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    display_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    llm_settings: Optional[dict] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LLMProviderConfig(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LLMSettingsUpdate(BaseModel):
    default: LLMProviderConfig
    agents: Optional[dict[str, LLMProviderConfig]] = None  # weaver/chronicler/stylist/extractor/foreseer/profiler/editor_analyst


class AgentLLMDisplay(BaseModel):
    agent: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key_masked: Optional[str] = None
    is_custom: bool = False
