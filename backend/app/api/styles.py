import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.database import get_db
from app.models.style_profile import StyleProfile
from app.models.vector_store import StyleChunk
from app.models.user import User
from app.schemas.style import StyleProfileCreate, StyleProfileUpdate, StyleProfileResponse
from app.api.auth import get_current_user
from app.services.queue_service import enqueue_job

router = APIRouter(prefix="/api/styles", tags=["styles"])


@router.get("/", response_model=List[StyleProfileResponse])
async def list_style_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StyleProfile).where(StyleProfile.owner_id == current_user.id)
    )
    profiles = result.scalars().all()
    return [StyleProfileResponse.model_validate(p) for p in profiles]


@router.post("/", response_model=StyleProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_style_profile(
    profile_data: StyleProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = StyleProfile(
        owner_id=current_user.id,
        name=profile_data.name,
        author_name=profile_data.author_name,
        description=profile_data.description,
        source_books=profile_data.source_books,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return StyleProfileResponse.model_validate(profile)


@router.get("/{style_id}", response_model=StyleProfileResponse)
async def get_style_profile(
    style_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.id == style_id, StyleProfile.owner_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")
    return StyleProfileResponse.model_validate(profile)


@router.put("/{style_id}", response_model=StyleProfileResponse)
async def update_style_profile(
    style_id: uuid.UUID,
    profile_data: StyleProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.id == style_id, StyleProfile.owner_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")

    update_dict = profile_data.model_dump(exclude_unset=True)
    jsonb_fields = {"source_books", "style_features"}

    for field, value in update_dict.items():
        setattr(profile, field, value)
        if field in jsonb_fields:
            flag_modified(profile, field)

    await db.flush()
    await db.refresh(profile)
    return StyleProfileResponse.model_validate(profile)


@router.delete("/{style_id}", status_code=status.HTTP_200_OK)
async def delete_style_profile(
    style_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.id == style_id, StyleProfile.owner_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")

    await db.delete(profile)
    await db.flush()
    return {"message": "Style profile deleted successfully"}


@router.post("/{style_id}/upload-files", status_code=status.HTTP_202_ACCEPTED)
async def upload_style_files(
    style_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify style profile exists and belongs to user
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.id == style_id, StyleProfile.owner_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")

    # Validate file extensions
    allowed_extensions = {".epub", ".txt", ".pdf"}
    file_contents: list[tuple[str, bytes]] = []

    for file in files:
        ext = ""
        if file.filename:
            ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.filename}. Allowed: .epub, .txt, .pdf",
            )
        content = await file.read()
        file_contents.append((file.filename or "unknown", content))

    # Update source_books immediately so user sees the file in the list
    existing_books = profile.source_books or []
    for filename, _ in file_contents:
        if not any(b.get("name") == filename for b in existing_books):
            existing_books.append({"name": filename})
    profile.source_books = existing_books
    profile.processing_status = "processing"
    flag_modified(profile, "source_books")
    await db.flush()

    # Spool uploaded bytes to a staging directory shared with the ARQ worker,
    # then enqueue processing. The worker reads the files back and cleans up.
    staging_dir = Path(settings.FILE_STAGING_DIR) / str(style_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in file_contents:
        (staging_dir / filename).write_bytes(content)

    await enqueue_job("process_style_files", str(style_id), str(staging_dir))

    return {
        "message": "File upload started",
        "files_count": len(file_contents),
        "style_profile_id": str(style_id),
    }


@router.post("/{style_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_style(
    style_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify style profile exists and belongs to user
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.id == style_id, StyleProfile.owner_id == current_user.id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Style profile not found")

    if not profile.total_chunks or profile.total_chunks == 0:
        # Check if files are still being processed
        if profile.processing_status == "processing":
            raise HTTPException(
                status_code=409,
                detail="Files are still being processed. Please wait a moment and try again.",
            )
        # Double-check by querying the database directly
        from app.models.vector_store import StyleChunk
        chunk_count_result = await db.execute(
            select(StyleChunk.id).where(StyleChunk.style_profile_id == style_id).limit(1)
        )
        if not chunk_count_result.first():
            raise HTTPException(
                status_code=400,
                detail="No style chunks to analyze. Upload files first.",
            )

    # Enqueue analysis onto the ARQ worker
    await enqueue_job("run_style_analysis", str(style_id))

    return {
        "message": "Style analysis started",
        "style_profile_id": str(style_id),
        "total_chunks": profile.total_chunks,
    }
