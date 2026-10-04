import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings for a list of texts."""
    service = EmbeddingService()
    return await service.embed_texts(texts)


class EmbeddingService:
    """DashScope embedding and rerank service via OpenAI-compatible API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        rerank_model: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.rerank_model = rerank_model or settings.RERANK_MODEL

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts. Sanitizes empty strings and truncates long inputs.
        
        Splits into batches of 20 to respect API limits.
        """
        sanitized = []
        for t in texts:
            if not t or not t.strip():
                sanitized.append("\uff08\u7a7a\u767d\u6bb5\u843d\uff09")
            elif len(t) > 6000:
                sanitized.append(t[:6000])
            else:
                sanitized.append(t)

        # Process in batches of 6 (DashScope intl limit is 10, use 6 for safety)
        batch_size = 6
        all_embeddings = []

        for i in range(0, len(sanitized), batch_size):
            batch = sanitized[i:i + batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        logger.debug("Embedded %d texts with model=%s", len(texts), self.model)
        return all_embeddings

    async def _embed_batch(self, texts: list[str], retries: int = 3) -> list[list[float]]:
        """Embed a single batch with retry logic."""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": settings.EMBEDDING_DIM,
        }

        last_error = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        logger.error(
                            "Embedding API error %d (batch=%d texts): %s",
                            response.status_code, len(texts), response.text[:300]
                        )
                    response.raise_for_status()
                    data = response.json()

                # Sort by index to preserve order
                embeddings_data = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in embeddings_data]
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    logger.warning("Embedding batch retry %d: %s", attempt + 1, e)

        raise last_error

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query text."""
        results = await self.embed_texts([query])
        return results[0]

    async def rerank(
        self, query: str, documents: list[str], top_n: int = 5
    ) -> list[dict]:
        """Rerank documents using DashScope qwen3-rerank.

        Uses the compatible-api/v1/reranks endpoint (NOT compatible-mode).
        Returns list of {"index": int, "relevance_score": float}.
        """
        # Build the rerank URL: replace /v1 suffix with compatible-api/v1/reranks
        base = self.base_url
        if base.endswith("/v1"):
            rerank_url = base[:-3] + "/compatible-api/v1/reranks"
        else:
            rerank_url = base + "/compatible-api/v1/reranks"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.rerank_model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": False,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(rerank_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        results = data.get("output", {}).get("results", [])
        logger.debug(
            "Reranked %d documents, returned top %d", len(documents), len(results)
        )
        return results
