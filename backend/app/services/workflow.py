import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.style_profile import StyleProfile
from app.services.diff_utils import compute_diff as _compute_diff
from app.services.llm_service import LLMService
from app.services.vector_store import VectorStoreService

# Re-exported for backward compatibility (moved to app.services.style_pipeline).
from app.services.style_pipeline import run_profiler_pipeline  # noqa: F401

logger = logging.getLogger(__name__)


# Content-free, technique-only style-feature filtering lives in a dependency-free
# module so it can be unit-tested without importing the ORM models. Aliased here
# for use by execute().
from app.services.style_features import technique_only_features as _technique_only_features  # noqa: E402

# Pure formatters for the accumulated "已達成里程碑" block and the structured
# "故事藍圖" (arc plan) block (dependency-free).
from app.services.arc_context import (  # noqa: E402
    format_milestones_progress as _format_milestones_progress,
    format_arc_plan as _format_arc_plan,
)


class WorkflowService:
    """Orchestrates the novel chapter generation and finalization pipeline."""

    def __init__(self, llm_settings: Optional[dict] = None):
        # Extract base_url and api_key from llm_settings for embedding calls
        base_url = None
        api_key = None
        if llm_settings and llm_settings.get("default"):
            default_cfg = llm_settings["default"]
            base_url = default_cfg.get("base_url")
            api_key = default_cfg.get("api_key")
        self.vector_store = VectorStoreService(base_url=base_url, api_key=api_key)

    async def execute(
        self,
        chapter_id: uuid.UUID,
        project_id: uuid.UUID,
        db: AsyncSession,
        llm_settings: Optional[dict] = None,
    ) -> Optional[Chapter]:
        """Main generation workflow: draft -> review -> revision."""
        from app.agents.weaver import Weaver
        from app.agents.chronicler import Chronicler
        from app.agents.stylist import Stylist

        # Get chapter
        chapter = await db.get(Chapter, chapter_id)
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} not found")

        # Set status DRAFTING
        chapter.status = "DRAFTING"
        await db.commit()

        # Collect context
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Style context
        style_profile = None
        style_examples = []
        style_guide = ""
        style_features_for_gen: dict = {}
        if project.active_style_id:
            style_profile = await db.get(StyleProfile, project.active_style_id)
            if style_profile:
                # Distilled, content-free style guide (technique only)
                style_guide = (style_profile.style_features or {}).get("style_guide", "")
                # Content-free, technique-only subset safe for generation prompts
                # (drops free-text fields that can carry reference content/worldview).
                style_features_for_gen = _technique_only_features(style_profile.style_features)
                try:
                    # Plot-decoupled random sampling — examples are NOT chosen by
                    # plot similarity, so raw reference content cannot bleed into drafts.
                    style_examples = await self.vector_store.sample_style(
                        style_profile.id,
                        top_k=3,
                        db=db,
                    )
                except Exception as e:
                    logger.warning("Style sampling failed: %s", e)

        # Plot context via hybrid search
        plot_context = []
        search_query = chapter.direction or project.outline or project.title
        if search_query:
            try:
                plot_context = await self.vector_store.search_plot(
                    project_id, search_query, top_k=5, db=db
                )
            except Exception as e:
                logger.warning("Plot search failed: %s", e)

        # Previous chapter ending (last 2000 chars)
        previous_ending = ""
        previous_chapters_summary = ""
        milestones_progress = ""
        if chapter.chapter_number > 1:
            stmt = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < chapter.chapter_number)
                .order_by(Chapter.chapter_number.desc())
            )
            result = await db.execute(stmt)
            prev_chapters = result.scalars().all()

            if prev_chapters:
                # Most recent chapter's ending
                latest = prev_chapters[0]
                content = latest.final_content or latest.draft_content or ""
                previous_ending = content[-2000:] if content else ""

                # Summary from previous chapters
                summaries = []
                for ch in reversed(prev_chapters):
                    if ch.extraction_result and ch.extraction_result.get("chapter_summary"):
                        summaries.append(
                            f"Chapter {ch.chapter_number}: {ch.extraction_result['chapter_summary']}"
                        )
                previous_chapters_summary = "\n".join(summaries)

                # Accumulated plot milestones → overall arc progress (ascending).
                milestone_entries = [
                    (ch.chapter_number, ch.extraction_result["plot_milestones"])
                    for ch in reversed(prev_chapters)
                    if ch.extraction_result and ch.extraction_result.get("plot_milestones")
                ]
                milestones_progress = _format_milestones_progress(milestone_entries)

        # Build context dict for agents
        context = {
            "project": project,
            "chapter": chapter,
            "style_profile": style_profile,
            "style_examples": style_examples,
            "style_guide": style_guide,
            "plot_context": plot_context,
            "previous_ending": previous_ending,
            "previous_chapters_summary": previous_chapters_summary,
        }

        # Render the structured story blueprint (if any) for arc-aware drafting.
        arc_plan_summary = _format_arc_plan(project.arc_plan, chapter.chapter_number)

        # Call Weaver to write draft
        weaver = Weaver(llm_settings=llm_settings)
        weaver_result = await weaver.write(
            direction=chapter.direction or "繼續推進劇情",
            style_features=style_features_for_gen,
            style_guide=style_guide,
            plot_context="\n".join(pc if isinstance(pc, str) else pc.get("content", "") for pc in plot_context),
            story_outline=project.outline or "",
            previous_ending=previous_ending,
            character_cards=[
                {"name": k, **v} for k, v in (project.character_cards or {}).items()
            ] if isinstance(project.character_cards, dict) else (project.character_cards or []),
            world_settings=project.world_settings or {},
            previous_chapters_summary=previous_chapters_summary,
            milestones_progress=milestones_progress,
            arc_plan_summary=arc_plan_summary,
            writing_preferences=project.writing_preferences or "",
            style_controls=project.style_controls,
        )
        draft_content = weaver_result.get("content", "") if isinstance(weaver_result, dict) else str(weaver_result)

        # IMMEDIATELY save draft_content + commit (ordering bug fix)
        chapter.draft_content = draft_content
        await db.commit()

        # Set status REVIEW
        chapter.status = "REVIEW"
        await db.commit()

        # Try Chronicler and Stylist reviews (non-fatal)
        logic_review = None
        style_review = None

        character_cards_list = [
            {"name": k, **v} for k, v in (project.character_cards or {}).items()
        ] if isinstance(project.character_cards, dict) else (project.character_cards or [])

        try:
            chronicler = Chronicler(llm_settings=llm_settings)
            logic_review = await chronicler.review(
                draft=draft_content,
                outline=project.outline or "",
                character_cards=character_cards_list,
                world_settings=project.world_settings or {},
                previous_chapters_summary=previous_chapters_summary,
                chapter_number=chapter.chapter_number,
            )
            chapter.logic_review = logic_review
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning("Chronicler review failed: %s", e)

        try:
            stylist = Stylist(llm_settings=llm_settings)
            style_review = await stylist.review(
                draft=draft_content,
                style_features=style_features_for_gen,
                style_examples=[ex if isinstance(ex, str) else ex.get("content", "") for ex in style_examples],
                style_guide=style_guide,
                writing_preferences=project.writing_preferences or "",
            )
            chapter.style_review = style_review
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning("Stylist review failed: %s", e)

        # Up to 2 revision rounds (non-fatal)
        current_content = draft_content
        for revision_round in range(2):
            try:
                # Only revise if there are issues flagged
                has_issues = False
                if logic_review and logic_review.get("issues"):
                    has_issues = True
                if style_review and style_review.get("issues"):
                    has_issues = True

                if not has_issues:
                    break

                revised_result = await weaver.revise(
                    current_content=current_content,
                    logic_review=logic_review,
                    style_review=style_review,
                    direction=chapter.direction or "繼續推進劇情",
                    style_features=style_features_for_gen,
                    style_guide=style_guide,
                    writing_preferences=project.writing_preferences or "",
                    style_controls=project.style_controls,
                )
                revised_content = revised_result.get("content", current_content) if isinstance(revised_result, dict) else str(revised_result)
                current_content = revised_content
                chapter.draft_content = current_content
                chapter.revision_count = revision_round + 1
                await db.commit()

                # Re-review after revision
                try:
                    logic_review = await chronicler.review(
                        draft=current_content,
                        outline=project.outline or "",
                        character_cards=character_cards_list,
                        world_settings=project.world_settings or {},
                        previous_chapters_summary=previous_chapters_summary,
                        chapter_number=chapter.chapter_number,
                    )
                    chapter.logic_review = logic_review
                except Exception:
                    pass

                try:
                    style_review = await stylist.review(
                        draft=current_content,
                        style_features=style_features_for_gen,
                        style_examples=[ex if isinstance(ex, str) else ex.get("content", "") for ex in style_examples],
                        writing_preferences=project.writing_preferences or "",
                    )
                    chapter.style_review = style_review
                except Exception:
                    pass

                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.warning("Revision round %d failed: %s", revision_round + 1, e)
                break

        # Final save — the chapter/project may have been deleted while this
        # long-running job was in flight (e.g. the user removed the project mid
        # generation, which makes earlier UPDATEs match 0 rows). Roll back any
        # poisoned transaction state and re-load the chapter in a fresh
        # transaction so a vanished row aborts gracefully instead of crashing
        # the worker with a PendingRollbackError.
        await db.rollback()
        chapter = await db.get(Chapter, chapter_id)
        if chapter is None:
            logger.warning(
                "Chapter %s no longer exists; aborting workflow final save",
                chapter_id,
            )
            return None
        chapter.draft_content = current_content
        chapter.status = "REVIEW"
        await db.commit()
        await db.refresh(chapter)

        logger.info(
            "Workflow execute completed for chapter=%s, revisions=%d",
            chapter_id,
            chapter.revision_count,
        )
        return chapter

    async def finalize(
        self,
        chapter_id: uuid.UUID,
        project_id: uuid.UUID,
        db: AsyncSession,
        llm_settings: Optional[dict] = None,
    ) -> Chapter:
        """Finalize pipeline: extract -> index -> foresee -> analyze -> finalize."""
        from app.agents.extractor import Extractor
        from app.agents.foreseer import Foreseer
        from app.agents.editor_analyst import EditorAnalyst

        chapter = await db.get(Chapter, chapter_id)
        if not chapter:
            raise ValueError(f"Chapter {chapter_id} not found")

        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get final content (use final_content if set, else draft_content)
        final_content = chapter.final_content or chapter.draft_content
        if not final_content:
            raise ValueError("No content to finalize")

        # 1. Extractor (non-fatal) - merge into project
        try:
            extractor = Extractor(llm_settings=llm_settings)

            # Build character_cards list for extractor
            ext_character_cards = [
                {"name": k, **v} for k, v in (project.character_cards or {}).items()
            ] if isinstance(project.character_cards, dict) else (project.character_cards or [])

            extraction_result = await extractor.extract(
                final_content=final_content,
                outline=project.outline or "",
                character_cards=ext_character_cards,
                world_settings=project.world_settings or {},
                chapter_number=chapter.chapter_number,
            )
            chapter.extraction_result = extraction_result

            # Merge extraction into project (characters, world settings, etc.)
            if extraction_result:
                from sqlalchemy.orm.attributes import flag_modified as _flag_modified

                # Merge new/updated characters
                new_chars = extraction_result.get("new_characters", [])
                updated_chars = extraction_result.get("updated_characters", [])
                if new_chars or updated_chars:
                    existing_chars = project.character_cards or {}
                    for char in new_chars:
                        name = char.get("name", "")
                        if name:
                            existing_chars[name] = {
                                **(existing_chars.get(name) or {}),
                                **{k: v for k, v in char.items() if k != "name"},
                            }
                    for char in updated_chars:
                        name = char.get("name", "")
                        if name:
                            existing_chars[name] = {
                                **(existing_chars.get(name) or {}),
                                **{k: v for k, v in char.items() if k != "name"},
                            }
                    project.character_cards = existing_chars
                    _flag_modified(project, "character_cards")

                # Merge world rules
                new_rules = extraction_result.get("world_rules", [])
                if new_rules:
                    existing_world = project.world_settings or {}
                    rules_list = existing_world.get("rules", [])
                    rules_list.extend(new_rules)
                    existing_world["rules"] = rules_list
                    project.world_settings = existing_world
                    _flag_modified(project, "world_settings")

            await db.commit()
        except Exception as e:
            logger.warning("Extractor failed: %s", e)

        # 2. Index to plot_chunks (non-fatal)
        try:
            from app.services.document_parser import DocumentParserService

            parser = DocumentParserService()
            chunks = parser.chunk_text(final_content, chunk_size=500, overlap=50)
            await self.vector_store.index_plot_chunks(
                project_id, chapter_id, chunks, db
            )
            await db.commit()
        except Exception as e:
            logger.warning("Plot chunk indexing failed: %s", e)

        # 3. Foreseer (non-fatal)
        try:
            foreseer = Foreseer(llm_settings=llm_settings)

            # Build character_cards list
            character_cards_list = [
                {"name": k, **v} for k, v in (project.character_cards or {}).items()
            ] if isinstance(project.character_cards, dict) else (project.character_cards or [])

            # Gather recent hooks from extraction result
            recent_hooks = []
            if chapter.extraction_result and chapter.extraction_result.get("open_hooks"):
                recent_hooks = [
                    {"hook": h} if isinstance(h, str) else h
                    for h in chapter.extraction_result["open_hooks"]
                ]

            # Summaries of all earlier chapters → broader arc for consistency.
            prev_stmt = (
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < chapter.chapter_number)
                .order_by(Chapter.chapter_number)
            )
            prev_rows = (await db.execute(prev_stmt)).scalars().all()
            previous_chapters_summary = "\n".join(
                f"Chapter {ch.chapter_number}: {ch.extraction_result['chapter_summary']}"
                for ch in prev_rows
                if ch.extraction_result and ch.extraction_result.get("chapter_summary")
            )

            # Accumulated milestones → arc progress. Include the just-finalized
            # chapter's own milestones, since we are planning the NEXT chapter.
            milestone_entries = [
                (ch.chapter_number, ch.extraction_result["plot_milestones"])
                for ch in prev_rows
                if ch.extraction_result and ch.extraction_result.get("plot_milestones")
            ]
            if chapter.extraction_result and chapter.extraction_result.get("plot_milestones"):
                milestone_entries.append(
                    (chapter.chapter_number, chapter.extraction_result["plot_milestones"])
                )
            milestones_progress = _format_milestones_progress(milestone_entries)

            arc_plan_summary = _format_arc_plan(project.arc_plan, chapter.chapter_number)

            suggestion = await foreseer.plan_next(
                final_content=final_content,
                chapter_number=chapter.chapter_number,
                outline=project.outline or "",
                character_cards=character_cards_list,
                world_settings=project.world_settings or {},
                recent_hooks=recent_hooks,
                previous_chapters_summary=previous_chapters_summary,
                milestones_progress=milestones_progress,
                arc_plan_summary=arc_plan_summary,
            )
            chapter.next_chapter_suggestion = suggestion
            await db.commit()
        except Exception as e:
            logger.warning("Foreseer failed: %s", e)

        # 3b. Architect (non-fatal) — dynamically refresh the arc plan so
        # milestone status and trajectory track the story as it is written.
        # Only runs when a blueprint already exists (it is created on demand via
        # the "生成藍圖" button, never auto-created here).
        if project.arc_plan:
            try:
                from app.agents.architect import Architect
                from sqlalchemy.orm.attributes import flag_modified as _flag_arc

                extraction = chapter.extraction_result or {}
                chapter_summary = extraction.get("chapter_summary", "") or ""
                milestones_achieved = [
                    (m.get("milestone") if isinstance(m, dict) else str(m)) or ""
                    for m in (extraction.get("plot_milestones") or [])
                ]
                milestones_achieved = [m for m in milestones_achieved if m]
                open_hooks = [
                    (h.get("hook") if isinstance(h, dict) else str(h)) or ""
                    for h in (extraction.get("open_hooks") or [])
                ]
                open_hooks = [h for h in open_hooks if h]

                architect = Architect(llm_settings=llm_settings)
                updated_plan = await architect.update(
                    current_plan=project.arc_plan,
                    chapter_number=chapter.chapter_number,
                    chapter_summary=chapter_summary,
                    milestones_achieved=milestones_achieved,
                    open_hooks=open_hooks,
                )
                project.arc_plan = updated_plan
                _flag_arc(project, "arc_plan")
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.warning("Architect arc-plan update failed: %s", e)

        # 4. Editor Analyst (non-fatal) - compute_diff, learn if magnitude != "none"
        try:
            editor_analyst = EditorAnalyst(llm_settings=llm_settings)
            draft_content = chapter.draft_content or ""

            diff_result = self.compute_diff(draft_content, final_content)

            if diff_result["magnitude"] != "none":
                from sqlalchemy.orm.attributes import flag_modified as _flag_mod

                learned_preferences = await editor_analyst.learn(
                    draft=draft_content,
                    final=final_content,
                    existing_preferences=project.writing_preferences if isinstance(project.writing_preferences, dict) else None,
                    chapter_number=chapter.chapter_number,
                    diff_info=diff_result.get("diff_text", ""),
                )
                # Save learned preferences back to project
                project.writing_preferences = learned_preferences
                _flag_mod(project, "writing_preferences")
            await db.commit()
        except Exception as e:
            logger.warning("Editor Analyst failed: %s", e)

        # 5. Set status FINALIZED
        chapter.final_content = final_content
        chapter.status = "FINALIZED"
        await db.commit()
        await db.refresh(chapter)

        logger.info("Finalize completed for chapter=%s", chapter_id)
        return chapter

    @staticmethod
    def compute_diff(draft: str, final: str) -> dict:
        """Compute diff between draft and final content.

        Thin wrapper around :func:`app.services.diff_utils.compute_diff`.
        """
        return _compute_diff(draft, final)


# --- Module-level helper functions for background tasks ---

async def run_weaver_pipeline(
    db: AsyncSession, project_id: uuid.UUID, chapter_id: uuid.UUID, user_id: uuid.UUID
):
    """Convenience function to run the Weaver workflow from background tasks."""
    from app.models.user import User

    user = await db.get(User, user_id)
    llm_settings = user.llm_settings if user else None

    service = WorkflowService(llm_settings=llm_settings)
    await service.execute(chapter_id, project_id, db, llm_settings)


async def run_finalize_pipeline(
    db: AsyncSession, project_id: uuid.UUID, chapter_id: uuid.UUID, user_id: uuid.UUID
):
    """Convenience function to run the finalize pipeline from background tasks."""
    from app.models.user import User

    user = await db.get(User, user_id)
    llm_settings = user.llm_settings if user else None

    service = WorkflowService(llm_settings=llm_settings)
    await service.finalize(chapter_id, project_id, db, llm_settings)


async def run_arc_plan_pipeline(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
):
    """Generate (or regenerate) the structured arc plan for a project.

    Runs as a background job triggered from the outline page. Follows the
    read → commit → LLM → re-load → write pattern so the slow Architect call
    never holds a database transaction open (which would otherwise surface as a
    StaleDataError on the final flush).
    """
    from app.agents.architect import Architect
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    # Phase 1: read everything needed, then release the transaction.
    user = await db.get(User, user_id)
    llm_settings = user.llm_settings if user else None
    project = await db.get(Project, project_id)
    if project is None:
        logger.warning("Project %s not found; skipping arc plan generation", project_id)
        return
    title = project.title
    outline = project.outline or ""
    genre = project.genre or ""
    world_settings = project.world_settings or {}
    character_cards = [
        {"name": k, **v} for k, v in (project.character_cards or {}).items()
    ] if isinstance(project.character_cards, dict) else (project.character_cards or [])
    await db.commit()

    # Phase 2: LLM work with no open transaction.
    architect = Architect(llm_settings=llm_settings)
    plan = await architect.generate(
        title=title,
        outline=outline,
        genre=genre,
        character_cards=character_cards,
        world_settings=world_settings,
    )

    # Phase 3: re-load fresh (the project may have been deleted) and persist.
    project = await db.get(Project, project_id)
    if project is None:
        logger.warning(
            "Project %s deleted during arc plan generation; discarding result",
            project_id,
        )
        return
    project.arc_plan = plan
    flag_modified(project, "arc_plan")
    await db.commit()
    logger.info("Arc plan generated for project=%s", project_id)

