"""Core style-file processing logic (parse -> chunk -> embed -> store).

Extracted from the API layer so it can be invoked by the ARQ worker without
importing FastAPI routers. The caller owns the database session and commit.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.models.style_profile import StyleProfile
from app.models.user import User
from app.models.vector_store import StyleChunk

logger = logging.getLogger(__name__)


async def process_style_files(db, style_id, file_contents: list[tuple[str, bytes]]):
    """Parse, chunk, embed, and store uploaded files as StyleChunks.

    On failure the style profile's ``processing_status`` is set to ``failed``
    and committed so the frontend can surface the error.
    """
    from app.services.document_parser import parse_document
    from app.services.embedding_service import EmbeddingService

    try:
        result = await db.execute(select(StyleProfile).where(StyleProfile.id == style_id))
        profile = result.scalar_one_or_none()
        if not profile:
            return

        # Resolve the owner's embedding credentials (agent override > default).
        user_result = await db.execute(select(User).where(User.id == profile.owner_id))
        user = user_result.scalar_one_or_none()
        user_settings = (user.llm_settings or {}) if user else {}
        default_cfg = user_settings.get("default", {})

        embedding_service = EmbeddingService(
            base_url=default_cfg.get("base_url") or None,
            api_key=default_cfg.get("api_key") or None,
        )

        total_new_chunks = 0

        for filename, content_bytes in file_contents:
            chunks = await parse_document(filename, content_bytes)
            if not chunks:
                continue

            texts = [c["content"] for c in chunks]
            embeddings = await embedding_service.embed_texts(texts)

            for idx, (chunk_data, embedding) in enumerate(zip(chunks, embeddings)):
                style_chunk = StyleChunk(
                    style_profile_id=style_id,
                    source_book=filename,
                    chapter_source=chunk_data.get("chapter_source"),
                    content=chunk_data["content"],
                    chunk_index=idx,
                    tokens=chunk_data.get("tokens"),
                    embedding=embedding,
                )
                db.add(style_chunk)
                total_new_chunks += 1

        profile.total_chunks = (profile.total_chunks or 0) + total_new_chunks
        profile.processing_status = "ready"
        flag_modified(profile, "total_chunks")
    except Exception as exc:  # noqa: BLE001 - mark profile failed for the UI
        logger.exception("Style file processing failed: %s", exc)
        try:
            result = await db.execute(select(StyleProfile).where(StyleProfile.id == style_id))
            profile = result.scalar_one_or_none()
            if profile:
                profile.processing_status = "failed"
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
