"""ARQ worker process.

Run with: ``arq app.worker.WorkerSettings``

Executes the long-running jobs that were previously FastAPI BackgroundTasks.
Each task opens its own database session and records failures back onto the
relevant record so the frontend polling surfaces a meaningful error.
"""

import logging
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.queue_service import redis_settings

logger = logging.getLogger(__name__)


async def run_weaver_workflow(ctx: dict, project_id: str, chapter_id: str, user_id: str):
    """Generate a chapter draft via the Weaver pipeline."""
    from app.models.chapter import Chapter
    from app.services.workflow import run_weaver_pipeline

    async with AsyncSessionLocal() as db:
        try:
            await run_weaver_pipeline(db, uuid.UUID(project_id), uuid.UUID(chapter_id), uuid.UUID(user_id))
            await db.commit()
        except Exception as e:  # noqa: BLE001 - record error then re-raise for ARQ retry
            await db.rollback()
            result = await db.execute(select(Chapter).where(Chapter.id == uuid.UUID(chapter_id)))
            chapter = result.scalar_one_or_none()
            if chapter:
                chapter.status = "OUTLINE"
                chapter.logic_review = {"error": str(e)}
                flag_modified(chapter, "logic_review")
                await db.commit()
            logger.exception("Weaver workflow failed for chapter=%s", chapter_id)
            raise


async def run_finalize_pipeline(ctx: dict, project_id: str, chapter_id: str, user_id: str):
    """Run the finalize pipeline (reviews, extraction, foresight) for a chapter."""
    from app.models.chapter import Chapter
    from app.services.workflow import run_finalize_pipeline as _finalize

    async with AsyncSessionLocal() as db:
        try:
            await _finalize(db, uuid.UUID(project_id), uuid.UUID(chapter_id), uuid.UUID(user_id))
            await db.commit()
        except Exception as e:  # noqa: BLE001
            await db.rollback()
            result = await db.execute(select(Chapter).where(Chapter.id == uuid.UUID(chapter_id)))
            chapter = result.scalar_one_or_none()
            if chapter:
                chapter.logic_review = {"error": str(e)}
                flag_modified(chapter, "logic_review")
                await db.commit()
            logger.exception("Finalize pipeline failed for chapter=%s", chapter_id)
            raise


async def run_arc_plan_generation(ctx: dict, project_id: str, user_id: str):
    """Generate (or regenerate) the structured arc plan for a project."""
    from app.services.workflow import run_arc_plan_pipeline

    async with AsyncSessionLocal() as db:
        try:
            await run_arc_plan_pipeline(db, uuid.UUID(project_id), uuid.UUID(user_id))
            await db.commit()
        except Exception:  # noqa: BLE001 - record then re-raise for ARQ retry
            await db.rollback()
            logger.exception("Arc plan generation failed for project=%s", project_id)
            raise


async def run_style_analysis(ctx: dict, style_id: str):
    """Run the Profiler agent over all style chunks for a profile."""
    from app.services.style_pipeline import run_profiler_pipeline

    async with AsyncSessionLocal() as db:
        try:
            await run_profiler_pipeline(db, uuid.UUID(style_id))
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
            logger.exception("Style analysis failed for style=%s", style_id)
            raise


async def process_style_files(ctx: dict, style_id: str, staging_dir: str):
    """Parse/chunk/embed files spooled to ``staging_dir`` for a style profile.

    The API endpoint writes uploaded bytes to a shared staging directory and
    passes its path; this task reads them back, processes them, then removes
    the staging directory.
    """
    from app.services.style_processing import process_style_files as _process

    directory = Path(staging_dir)
    try:
        files: list[tuple[str, bytes]] = []
        for path in sorted(directory.iterdir()):
            if path.is_file():
                files.append((path.name, path.read_bytes()))
        if not files:
            logger.warning("No staged files found for style=%s in %s", style_id, staging_dir)
            return
        async with AsyncSessionLocal() as db:
            await _process(db, uuid.UUID(style_id), files)
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Style file processing failed for style=%s", style_id)
        # _process marks the profile as failed on its own; nothing to re-raise
        # for retry because the staging files may be partially consumed.
    finally:
        shutil.rmtree(directory, ignore_errors=True)


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [
        run_weaver_workflow,
        run_finalize_pipeline,
        run_arc_plan_generation,
        run_style_analysis,
        process_style_files,
    ]
    redis_settings = redis_settings()
    # LLM generation can take a while; allow generous job runtime.
    job_timeout = 1800
    max_jobs = 4
    allow_abort_jobs = True
