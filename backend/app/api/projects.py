import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.project import Project
from app.models.vector_store import PlotChunk
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.api.auth import get_current_user
from app.services.queue_service import enqueue_job

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.owner_id == current_user.id).order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        owner_id=current_user.id,
        title=project_data.title,
        description=project_data.description,
        genre=project_data.genre,
        outline=project_data.outline,
        character_cards=project_data.character_cards,
        world_settings=project_data.world_settings,
        writing_preferences=project_data.writing_preferences,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


# IMPORTANT: Register the writing-preferences DELETE route BEFORE the {project_id} routes
# to avoid path collision where "writing-preferences" is interpreted as a project_id
@router.delete("/{project_id}/writing-preferences", status_code=status.HTTP_200_OK)
async def reset_writing_preferences(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.writing_preferences = None
    flag_modified(project, "writing_preferences")
    await db.flush()
    return {"message": "Writing preferences reset successfully"}


@router.post("/{project_id}/arc-plan/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_arc_plan(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger background generation of the structured story blueprint."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await enqueue_job("run_arc_plan_generation", str(project_id), str(current_user.id))
    return {"message": "Arc plan generation started", "project_id": str(project_id)}


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_dict = project_data.model_dump(exclude_unset=True)
    jsonb_fields = {"character_cards", "world_settings", "writing_preferences", "style_controls"}

    for field, value in update_dict.items():
        setattr(project, field, value)
        # Flag JSONB fields as modified so SQLAlchemy detects the change
        if field in jsonb_fields:
            flag_modified(project, field)

    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete plot_chunks first due to FK constraints
    await db.execute(delete(PlotChunk).where(PlotChunk.project_id == project_id))
    await db.delete(project)
    await db.flush()
    return {"message": "Project deleted successfully"}
