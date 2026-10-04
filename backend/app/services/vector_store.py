import logging
import uuid
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.vector_store import PlotChunk, StyleChunk
from app.services.embedding_service import EmbeddingService
from app.services.text_utils import build_tsquery, tokenize

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Hybrid search service combining vector similarity, BM25, RRF fusion, and reranking."""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.embedding_service = EmbeddingService(base_url=base_url, api_key=api_key)

    async def index_plot_chunks(
        self,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID,
        chunks: list[str],
        db: AsyncSession,
    ) -> list[PlotChunk]:
        """Embed chunks, tokenize with jieba, and save as PlotChunk records."""
        if not chunks:
            return []

        embeddings = await self.embedding_service.embed_texts(chunks)

        plot_chunks = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            # Jieba tokenize for BM25 (punctuation/whitespace stripped)
            tokens = " ".join(tokenize(chunk_text))

            plot_chunk = PlotChunk(
                id=uuid.uuid4(),
                project_id=project_id,
                chapter_id=chapter_id,
                content=chunk_text,
                chunk_index=i,
                tokens=tokens,
                embedding=embedding,
            )
            db.add(plot_chunk)
            plot_chunks.append(plot_chunk)

        await db.flush()
        logger.info(
            "Indexed %d plot chunks for project=%s chapter=%s",
            len(plot_chunks),
            project_id,
            chapter_id,
        )
        return plot_chunks

    async def index_style_chunks(
        self,
        style_profile_id: uuid.UUID,
        source_book: Optional[str],
        chunks: list[str],
        db: AsyncSession,
    ) -> list[StyleChunk]:
        """Embed chunks, tokenize with jieba, and save as StyleChunk records."""
        if not chunks:
            return []

        embeddings = await self.embedding_service.embed_texts(chunks)

        style_chunks = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            tokens = " ".join(tokenize(chunk_text))

            style_chunk = StyleChunk(
                id=uuid.uuid4(),
                style_profile_id=style_profile_id,
                source_book=source_book,
                content=chunk_text,
                chunk_index=i,
                tokens=tokens,
                embedding=embedding,
            )
            db.add(style_chunk)
            style_chunks.append(style_chunk)

        await db.flush()
        logger.info(
            "Indexed %d style chunks for style_profile=%s source=%s",
            len(style_chunks),
            style_profile_id,
            source_book,
        )
        return style_chunks

    async def search_plot(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        db: AsyncSession = None,
    ) -> list[dict]:
        """Hybrid search: vector recall + BM25 recall + RRF fusion + rerank."""
        recall_top_n = settings.RECALL_TOP_N
        rrf_k = settings.RRF_K

        # 1. Vector recall
        query_embedding = await self.embedding_service.embed_query(query)
        vector_results = await self._vector_recall_plot(
            project_id, query_embedding, recall_top_n, db
        )

        # 2. BM25 recall
        bm25_results = await self._bm25_recall_plot(project_id, query, recall_top_n, db)

        # 3. RRF fusion
        fused = self._rrf_fusion(vector_results, bm25_results, rrf_k)

        # 4. Rerank (non-fatal)
        if fused:
            try:
                documents = [item["content"] for item in fused]
                reranked = await self.embedding_service.rerank(
                    query, documents, top_n=top_k
                )
                # Reorder by rerank results
                result = []
                for r in reranked:
                    idx = r["index"]
                    item = fused[idx].copy()
                    item["rerank_score"] = r["relevance_score"]
                    result.append(item)
                return result
            except Exception as e:
                logger.warning("Rerank failed, falling back to RRF order: %s", e)

        return fused[:top_k]

    async def search_style(
        self,
        style_profile_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        db: AsyncSession = None,
    ) -> list[dict]:
        """Hybrid search for style chunks: vector + BM25 + RRF + rerank."""
        recall_top_n = settings.RECALL_TOP_N
        rrf_k = settings.RRF_K

        # 1. Vector recall
        query_embedding = await self.embedding_service.embed_query(query)
        vector_results = await self._vector_recall_style(
            style_profile_id, query_embedding, recall_top_n, db
        )

        # 2. BM25 recall
        bm25_results = await self._bm25_recall_style(
            style_profile_id, query, recall_top_n, db
        )

        # 3. RRF fusion
        fused = self._rrf_fusion(vector_results, bm25_results, rrf_k)

        # 4. Rerank (non-fatal)
        if fused:
            try:
                documents = [item["content"] for item in fused]
                reranked = await self.embedding_service.rerank(
                    query, documents, top_n=top_k
                )
                result = []
                for r in reranked:
                    idx = r["index"]
                    item = fused[idx].copy()
                    item["rerank_score"] = r["relevance_score"]
                    result.append(item)
                return result
            except Exception as e:
                logger.warning("Rerank failed, falling back to RRF order: %s", e)

        return fused[:top_k]

    async def sample_style(
        self,
        style_profile_id: uuid.UUID,
        top_k: int = 3,
        db: AsyncSession = None,
    ) -> list[dict]:
        """Return diverse, plot-decoupled style excerpts for style reference.

        Unlike ``search_style``, this does NOT retrieve by plot similarity. It
        samples representative passages at random across the whole corpus so the
        examples reflect *how* the author writes (diction, rhythm, tone) rather
        than *what* the current chapter is about. This is the key to avoiding
        the reference work's content/worldbuilding leaking into generation.
        """
        stmt = (
            select(
                StyleChunk.id,
                StyleChunk.content,
                StyleChunk.source_book,
                StyleChunk.chunk_index,
            )
            .where(StyleChunk.style_profile_id == style_profile_id)
            .order_by(func.random())
            .limit(top_k)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "source_book": row.source_book,
                "chunk_index": row.chunk_index,
            }
            for row in rows
        ]

    # ─── Private Methods ───────────────────────────────────────────────

    async def _vector_recall_plot(
        self,
        project_id: uuid.UUID,
        query_embedding: list[float],
        top_n: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Vector similarity search for plot chunks."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        stmt = (
            select(
                PlotChunk.id,
                PlotChunk.content,
                PlotChunk.chapter_id,
                PlotChunk.chunk_index,
                PlotChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(PlotChunk.project_id == project_id)
            .where(PlotChunk.embedding.isnot(None))
            .order_by("distance")
            .limit(top_n)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "chapter_id": str(row.chapter_id) if row.chapter_id else None,
                "chunk_index": row.chunk_index,
                "vector_distance": row.distance,
            }
            for row in rows
        ]

    async def _vector_recall_style(
        self,
        style_profile_id: uuid.UUID,
        query_embedding: list[float],
        top_n: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Vector similarity search for style chunks."""
        stmt = (
            select(
                StyleChunk.id,
                StyleChunk.content,
                StyleChunk.source_book,
                StyleChunk.chunk_index,
                StyleChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(StyleChunk.style_profile_id == style_profile_id)
            .where(StyleChunk.embedding.isnot(None))
            .order_by("distance")
            .limit(top_n)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "source_book": row.source_book,
                "chunk_index": row.chunk_index,
                "vector_distance": row.distance,
            }
            for row in rows
        ]

    async def _bm25_recall_plot(
        self,
        project_id: uuid.UUID,
        query: str,
        top_n: int,
        db: AsyncSession,
    ) -> list[dict]:
        """BM25 full-text search for plot chunks using jieba tokenization."""
        tsquery_str = build_tsquery(query)
        if not tsquery_str:
            return []

        stmt = text("""
            SELECT id, content, chapter_id, chunk_index,
                   ts_rank(to_tsvector('simple', coalesce(tokens, '')),
                           to_tsquery('simple', :tsquery)) AS rank
            FROM plot_chunks
            WHERE project_id = :project_id
              AND to_tsvector('simple', coalesce(tokens, '')) @@ to_tsquery('simple', :tsquery)
            ORDER BY rank DESC
            LIMIT :top_n
        """)
        result = await db.execute(
            stmt,
            {
                "project_id": str(project_id),
                "tsquery": tsquery_str,
                "top_n": top_n,
            },
        )
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "chapter_id": str(row.chapter_id) if row.chapter_id else None,
                "chunk_index": row.chunk_index,
                "bm25_rank": row.rank,
            }
            for row in rows
        ]

    async def _bm25_recall_style(
        self,
        style_profile_id: uuid.UUID,
        query: str,
        top_n: int,
        db: AsyncSession,
    ) -> list[dict]:
        """BM25 full-text search for style chunks using jieba tokenization."""
        tsquery_str = build_tsquery(query)
        if not tsquery_str:
            return []

        stmt = text("""
            SELECT id, content, source_book, chunk_index,
                   ts_rank(to_tsvector('simple', coalesce(tokens, '')),
                           to_tsquery('simple', :tsquery)) AS rank
            FROM style_chunks
            WHERE style_profile_id = :style_profile_id
              AND to_tsvector('simple', coalesce(tokens, '')) @@ to_tsquery('simple', :tsquery)
            ORDER BY rank DESC
            LIMIT :top_n
        """)
        result = await db.execute(
            stmt,
            {
                "style_profile_id": str(style_profile_id),
                "tsquery": tsquery_str,
                "top_n": top_n,
            },
        )
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "content": row.content,
                "source_book": row.source_book,
                "chunk_index": row.chunk_index,
                "bm25_rank": row.rank,
            }
            for row in rows
        ]

    def _rrf_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        rrf_k: int,
    ) -> list[dict]:
        """Reciprocal Rank Fusion: score = sum(1/(rrf_k + rank)) for each list."""
        scores: dict[str, float] = {}
        items: dict[str, dict] = {}

        # Score from vector results
        for rank, item in enumerate(vector_results):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            items[item_id] = item

        # Score from BM25 results
        for rank, item in enumerate(bm25_results):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            items[item_id] = item

        # Sort by fused score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        result = []
        for item_id in sorted_ids:
            item = items[item_id].copy()
            item["rrf_score"] = scores[item_id]
            result.append(item)

        return result
