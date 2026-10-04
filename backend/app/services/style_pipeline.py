"""Style-profiling background pipeline.

Runs the Profiler agent over a StyleProfile's chunks and stores the resulting
style features. Extracted from ``workflow.py`` because it is logically
independent of ``WorkflowService`` (it does not orchestrate chapter
generation) and its sampling logic benefits from isolated unit testing.
"""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# How many chunks to feed the Profiler. Sampled across the whole corpus so the
# style profile reflects the entire source, not just its opening.
DEFAULT_SAMPLE_BUDGET = 48

# Chunks per Profiler batch (map step). Each batch is small enough to fit well
# within a model context window; the per-batch profiles are then merged (reduce)
# into one consolidated profile. Batching avoids the old failure mode where all
# chunks were concatenated into a single oversized prompt that the provider
# truncated, so only the opening of the corpus was ever analyzed.
PROFILER_BATCH_SIZE = 8

# How many Profiler batches to analyze concurrently. Running the map step
# sequentially made the whole pipeline take 7-14 minutes — far longer than the
# frontend polls — so the UI appeared unresponsive. Bounding concurrency with a
# semaphore speeds this up several-fold without hammering the LLM provider.
PROFILER_CONCURRENCY = 3


def batch_chunks(items: list, size: int = PROFILER_BATCH_SIZE) -> list[list]:
    """Split ``items`` into consecutive batches of at most ``size`` elements."""
    if size <= 0:
        return [items] if items else []
    return [items[i:i + size] for i in range(0, len(items), size)]


def select_stratified_chunk_ids(meta_rows, total_budget: int = DEFAULT_SAMPLE_BUDGET):
    """Pick a representative, corpus-wide subset of style chunk ids.

    Groups chunks by their source book and, within each book, selects
    evenly-spaced positions so the sample spans beginning → middle → end.
    The per-book budget is distributed across all books; books smaller than
    the per-book budget are fully included.

    Args:
        meta_rows: iterable of rows exposing ``source_book``, ``chunk_index``
            and ``id`` attributes.
        total_budget: approximate total number of chunks to select.

    Returns:
        list of chunk ids (order is grouped by book, then position).
    """
    books: dict[str, list] = {}
    for row in meta_rows:
        book_key = row.source_book or "__unknown__"
        books.setdefault(book_key, []).append((row.chunk_index, row.id))
    for book_key in books:
        books[book_key].sort(key=lambda x: x[0])

    if not books:
        return []

    per_book = max(1, total_budget // len(books))

    selected_ids = []
    for book_chunks in books.values():
        n = len(book_chunks)
        if n <= per_book:
            selected_ids.extend(cid for _, cid in book_chunks)
        else:
            # Evenly-spaced picks spanning beginning → end of this book.
            step = (n - 1) / (per_book - 1) if per_book > 1 else 0
            picked_positions = sorted({round(i * step) for i in range(per_book)})
            selected_ids.extend(book_chunks[p][1] for p in picked_positions)

    return selected_ids


async def run_profiler_pipeline(db: AsyncSession, style_id: uuid.UUID):
    """Run the Profiler agent to analyze style chunks and update the StyleProfile.

    Structured in three phases so that no DB transaction is held open during the
    (slow, multi-minute) LLM work. Holding a transaction idle while the Profiler
    runs caused the final write to hit a stale row and fail with
    ``StaleDataError: UPDATE ... expected to update 1 row(s); 0 were matched``,
    silently discarding the profiling result (the UI then showed no output).

    Phase 1: short read transaction — load inputs, then commit to release it.
    Phase 2: LLM map-reduce profiling with no open transaction.
    Phase 3: fresh transaction — re-load the profile and persist the result.
    """
    from app.models.style_profile import StyleProfile
    from app.models.vector_store import StyleChunk
    from app.models.user import User
    from app.agents.profiler import Profiler
    from sqlalchemy.orm.attributes import flag_modified

    # --- Phase 1: read inputs in a short transaction, then release it. ---
    result = await db.execute(select(StyleProfile).where(StyleProfile.id == style_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return

    owner_id = profile.owner_id

    # Stratified sampling across the whole corpus (all books + beginning/middle/end),
    # rather than only the first ~20 chunks. This ensures the style profile reflects
    # the entire source, not just the opening.
    meta_result = await db.execute(
        select(StyleChunk.id, StyleChunk.source_book, StyleChunk.chunk_index)
        .where(StyleChunk.style_profile_id == style_id)
    )
    meta_rows = meta_result.fetchall()

    if not meta_rows:
        logger.warning("No style chunks found for style_id=%s", style_id)
        return

    selected_ids = select_stratified_chunk_ids(meta_rows, DEFAULT_SAMPLE_BUDGET)

    # Load content only for the selected chunks, in stable (book, position) order.
    chunks_result = await db.execute(
        select(StyleChunk.content)
        .where(StyleChunk.id.in_(selected_ids))
        .order_by(StyleChunk.source_book, StyleChunk.chunk_index)
    )
    chunk_texts = [row[0] for row in chunks_result.fetchall()]

    if not chunk_texts:
        logger.warning("No style chunks found for style_id=%s", style_id)
        return

    # Get user's LLM settings (plain scalars/dicts — safe to use after commit).
    user = await db.get(User, owner_id)
    llm_settings = user.llm_settings if user else None

    # Release the read transaction so it does not sit idle during the LLM work.
    await db.commit()

    # --- Phase 2: LLM map-reduce profiling with no open transaction. ---
    # Analyze small batches spanning the whole corpus, then merge the per-batch
    # profiles into one. This ensures the profile reflects the entire source
    # rather than only whatever fit a single oversized prompt (which the provider
    # truncated to the opening).
    profiler = Profiler(llm_settings=llm_settings)
    batches = batch_chunks(chunk_texts, PROFILER_BATCH_SIZE)

    # Analyze batches concurrently (bounded by a semaphore) rather than one at a
    # time. Sequential map calls stretched the pipeline to 7-14 minutes, well past
    # the frontend's polling window, so the UI looked unresponsive. gather keeps
    # result order aligned with ``batches``; return_exceptions ensures one bad
    # batch doesn't lose the rest.
    semaphore = asyncio.Semaphore(PROFILER_CONCURRENCY)

    async def _analyze_batch(batch):
        async with semaphore:
            return await profiler.analyze(batch)

    results = await asyncio.gather(
        *(_analyze_batch(batch) for batch in batches), return_exceptions=True
    )

    partial_profiles = []
    for batch, res in zip(batches, results):
        if isinstance(res, Exception):
            logger.warning("Profiler batch failed (%d chunks): %s", len(batch), res)
        else:
            partial_profiles.append(res)

    if not partial_profiles:
        logger.warning("All Profiler batches failed for style_id=%s", style_id)
        return

    if len(partial_profiles) == 1:
        style_features = partial_profiles[0]
    else:
        try:
            style_features = await profiler.merge_profiles(partial_profiles)
        except Exception as e:  # noqa: BLE001 - fall back to the first partial profile
            logger.warning("Profiler merge failed, using first partial: %s", e)
            style_features = partial_profiles[0]

    logger.info(
        "Style profiling complete for style_id=%s: %d chunks across %d batches",
        style_id,
        len(chunk_texts),
        len(batches),
    )

    # --- Phase 3: fresh transaction — re-load and persist the result. ---
    # The profile may have been deleted while the LLM work was running; re-load
    # it in this new transaction and abort gracefully if it is gone.
    profile = await db.get(StyleProfile, style_id)
    if profile is None:
        logger.warning(
            "Style profile %s no longer exists; discarding profiling result",
            style_id,
        )
        return

    profile.style_features = style_features
    flag_modified(profile, "style_features")
    await db.commit()
