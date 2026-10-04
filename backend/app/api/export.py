"""
Export API: endpoints for downloading project as EPUB or DOCX.
"""

import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.user import User
from app.api.auth import get_current_user
from app.services.export_service import generate_epub, generate_docx


router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


class ExportFormat(str, Enum):
    EPUB = "epub"
    DOCX = "docx"


@router.get("/{format}")
async def export_project(
    project_id: uuid.UUID,
    format: ExportFormat,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export project chapters as EPUB or DOCX file.
    Only includes chapters with final_content (FINALIZED status) or draft_content.
    """
    # Verify project access
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch all chapters ordered by chapter_number
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    # Filter chapters that have content
    export_chapters = []
    for ch in chapters:
        content = ch.final_content or ch.draft_content
        if content:
            export_chapters.append({
                "chapter_number": ch.chapter_number,
                "title": ch.title or f"第{ch.chapter_number}章",
                "content": content,
            })

    if not export_chapters:
        raise HTTPException(
            status_code=400,
            detail="沒有可導出的章節內容，請先生成或撰寫章節。",
        )

    # Generate file
    author = current_user.display_name or current_user.username
    title = project.title

    if format == ExportFormat.EPUB:
        file_bytes = generate_epub(
            title=title,
            author=author,
            description=project.description,
            chapters=export_chapters,
        )
        media_type = "application/epub+zip"
        filename = f"{title}.epub"
    else:
        file_bytes = generate_docx(
            title=title,
            author=author,
            description=project.description,
            chapters=export_chapters,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{title}.docx"

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
