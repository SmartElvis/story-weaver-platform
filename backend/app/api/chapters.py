import uuid
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.vector_store import PlotChunk
from app.models.user import User
from app.schemas.chapter import ChapterCreate, ChapterUpdate, ChapterResponse
from app.api.auth import get_current_user
from app.services.queue_service import enqueue_job

router = APIRouter(prefix="/api/projects/{project_id}/chapters", tags=["chapters"])


async def _verify_project_access(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    """Verify user owns the project and return it."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/", response_model=List[ChapterResponse])
async def list_chapters(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    return [ChapterResponse.model_validate(c) for c in chapters]


@router.post("/", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    project_id: uuid.UUID,
    chapter_data: ChapterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    # Determine initial status and content
    initial_status = "OUTLINE"
    draft_content = None
    final_content = None

    if chapter_data.user_content:
        initial_status = "REVIEW"
        draft_content = chapter_data.user_content
        final_content = chapter_data.user_content

    chapter = Chapter(
        project_id=project_id,
        chapter_number=chapter_data.chapter_number,
        title=chapter_data.title,
        direction=chapter_data.direction,
        status=initial_status,
        draft_content=draft_content,
        final_content=final_content,
    )
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ChapterResponse.model_validate(chapter)


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    chapter_data: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    update_dict = chapter_data.model_dump(exclude_unset=True)
    jsonb_fields = {"logic_review", "style_review", "extraction_result", "next_chapter_suggestion", "generation_cost"}

    for field, value in update_dict.items():
        setattr(chapter, field, value)
        if field in jsonb_fields:
            flag_modified(chapter, field)

    await db.flush()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.delete("/{chapter_id}", status_code=status.HTTP_200_OK)
async def delete_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Delete plot_chunks first due to FK constraints
    await db.execute(delete(PlotChunk).where(PlotChunk.chapter_id == chapter_id))
    await db.delete(chapter)
    await db.flush()
    return {"message": "Chapter deleted successfully"}


@router.post("/{chapter_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Update status to DRAFTING
    chapter.status = "DRAFTING"
    await db.flush()

    # Enqueue the Weaver workflow onto the ARQ worker
    await enqueue_job(
        "run_weaver_workflow", str(project_id), str(chapter_id), str(current_user.id)
    )

    return {
        "message": "Generation started",
        "chapter_id": str(chapter_id),
        "status": "DRAFTING",
    }


@router.post("/{chapter_id}/finalize", status_code=status.HTTP_202_ACCEPTED)
async def finalize_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if not chapter.draft_content:
        raise HTTPException(status_code=400, detail="No draft content to finalize")

    # Enqueue the finalize pipeline onto the ARQ worker
    await enqueue_job(
        "run_finalize_pipeline", str(project_id), str(chapter_id), str(current_user.id)
    )

    return {
        "message": "Finalization started",
        "chapter_id": str(chapter_id),
        "status": chapter.status,
    }


# --- Script Conversion (Simplified / Traditional Chinese) ---


class ConvertScriptRequest(BaseModel):
    target: Literal["simplified", "traditional"]


@router.post("/{chapter_id}/convert-script", response_model=ChapterResponse)
async def convert_chapter_script(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ConvertScriptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert finalized chapter content between Simplified and Traditional Chinese."""
    from opencc import OpenCC

    await _verify_project_access(project_id, current_user, db)

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    content = chapter.final_content
    if not content:
        raise HTTPException(status_code=400, detail="No finalized content to convert")

    config = "t2s" if body.target == "simplified" else "s2t"
    converter = OpenCC(config)
    chapter.final_content = converter.convert(content)

    await db.flush()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)
