import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    TokenResponse,
    LLMSettingsUpdate,
    AgentLLMDisplay,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

AGENT_NAMES = [
    "weaver",
    "chronicler",
    "stylist",
    "extractor",
    "foreseer",
    "profiler",
    "editor_analyst",
]


# --- Password Helpers ---

def hash_password(password: str, salt: str) -> str:
    """Hash password using PBKDF2-HMAC SHA256."""
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return hashed.hex()


def verify_password(password: str, salt: str, hashed_password: str) -> bool:
    """Verify a password against salt and hash."""
    return hash_password(password, salt) == hashed_password


# --- JWT Helpers ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


# --- Dependencies ---

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


# --- Mask API Key Helper ---

def mask_api_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


# --- Routes ---

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if username or email already exists
    result = await db.execute(
        select(User).where((User.username == user_data.username) | (User.email == user_data.email))
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.username == user_data.username:
            raise HTTPException(status_code=400, detail="Username already registered")
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user with pbkdf2_hmac hashing
    salt = secrets.token_hex(16)
    hashed_password = hash_password(user_data.password, salt)

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        salt=salt,
        display_name=user_data.display_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Generate token
    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.salt, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.get("/llm-settings")
async def get_llm_settings(current_user: User = Depends(get_current_user)):
    user_settings = current_user.llm_settings or {}
    default_config = user_settings.get("default", {})
    agents_config = user_settings.get("agents", {})

    # Return raw settings in a format frontend can directly edit and save back
    return {
        "default": default_config,
        "agents": agents_config,
    }


@router.put("/llm-settings")
async def update_llm_settings(
    settings_update: LLMSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_settings = current_user.llm_settings or {}
    old_default = old_settings.get("default", {})
    old_agents = old_settings.get("agents", {})

    # Build new default - preserve old api_key if new one is empty
    new_default = settings_update.default.model_dump(exclude_none=True)
    if not new_default.get("api_key") and old_default.get("api_key"):
        new_default["api_key"] = old_default["api_key"]

    # Build new agents config
    new_agents = {}
    if settings_update.agents:
        for agent_name, agent_config in settings_update.agents.items():
            agent_dict = agent_config.model_dump(exclude_none=True)
            old_agent = old_agents.get(agent_name, {})
            # Preserve old api_key if new one is empty
            if not agent_dict.get("api_key") and old_agent.get("api_key"):
                agent_dict["api_key"] = old_agent["api_key"]
            if agent_dict:
                new_agents[agent_name] = agent_dict

    current_user.llm_settings = {
        "default": new_default,
        "agents": new_agents,
    }
    flag_modified(current_user, "llm_settings")
    await db.flush()
    await db.refresh(current_user)

    # Return updated display
    return await get_llm_settings(current_user)


@router.delete("/llm-settings", status_code=status.HTTP_200_OK)
async def reset_llm_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.llm_settings = None
    flag_modified(current_user, "llm_settings")
    await db.flush()
    return {"message": "LLM settings reset to defaults"}
