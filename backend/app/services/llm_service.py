import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Shared, lazily-created HTTP clients keyed by (base_url, api_key). LLMService
# instances are created per agent/per request, so caching the underlying client
# here lets separate instances reuse the same connection pool (keep-alive)
# instead of opening a fresh client — and a fresh TLS handshake — on every call.
_CLIENT_POOL: dict[tuple[str, str], httpx.AsyncClient] = {}

# Total request timeout and connection-acquisition timeout (seconds).
REQUEST_TIMEOUT = 180.0
CONNECT_TIMEOUT = 10.0

# Retry policy: initial backoff doubles each attempt; 429 responses may carry a
# Retry-After header which takes precedence over the exponential schedule.
MAX_ATTEMPTS = 5
INITIAL_BACKOFF = 1.0


def _get_client(base_url: str, api_key: str) -> httpx.AsyncClient:
    """Return a shared AsyncClient for the given endpoint, creating it lazily."""
    key = (base_url, api_key)
    client = _CLIENT_POOL.get(key)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        _CLIENT_POOL[key] = client
    return client


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    """Parse a Retry-After header (delta-seconds form) if present and valid."""
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    return value if value >= 0 else None


class LLMService:
    """OpenAI-compatible LLM client that resolves settings with priority:
    agent override > default > .env settings.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_user_settings(
        cls, llm_settings: Optional[dict], agent_name: str
    ) -> "LLMService":
        """Create an LLM client with priority: agent override > default > .env settings.

        llm_settings shape:
        {
            "default": {"base_url": ..., "api_key": ..., "model": ...},
            "agents": {"weaver": {...}, "chronicler": {...}, ...}
        }
        """
        base_url: Optional[str] = None
        api_key: Optional[str] = None
        model: Optional[str] = None

        if llm_settings:
            # Try agent-specific override first
            agents_cfg = llm_settings.get("agents") or {}
            agent_cfg = agents_cfg.get(agent_name) or {}

            # Then default
            default_cfg = llm_settings.get("default") or {}

            # Priority: agent override > default > .env
            base_url = agent_cfg.get("base_url") or default_cfg.get("base_url")
            api_key = agent_cfg.get("api_key") or default_cfg.get("api_key")
            model = agent_cfg.get("model") or default_cfg.get("model")

        # Fall back to .env settings (use `or` to handle None values)
        base_url = base_url or settings.LLM_BASE_URL
        api_key = api_key or settings.LLM_API_KEY
        model = model or settings.LLM_MODEL

        return cls(base_url=base_url, api_key=api_key, model=model)

    async def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Call OpenAI-compatible chat/completions endpoint and return content.

        Retries on transient network errors and on retryable HTTP statuses
        (429 rate-limit and 5xx server errors) with exponential backoff,
        honoring the server's Retry-After header when present.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = _get_client(self.base_url, self.api_key)
        last_error: Optional[Exception] = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await client.post(url, json=payload, headers=headers)

                # Retry rate-limiting and server errors with backoff.
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = _retry_after_seconds(response)
                    wait_time = (
                        retry_after
                        if retry_after is not None
                        else INITIAL_BACKOFF * (2 ** attempt)
                    )
                    if attempt < MAX_ATTEMPTS - 1:
                        logger.warning(
                            "LLM chat retry %d after HTTP %d (waiting %.1fs)",
                            attempt + 1,
                            response.status_code,
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.debug(
                    "LLM response received: model=%s, tokens=%s",
                    self.model,
                    data.get("usage", {}),
                )
                return content
            except (
                httpx.RemoteProtocolError,
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
            ) as e:
                last_error = e
                if attempt < MAX_ATTEMPTS - 1:
                    wait_time = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "LLM chat retry %d (waiting %.1fs): %s",
                        attempt + 1,
                        wait_time,
                        e,
                    )
                    await asyncio.sleep(wait_time)

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM chat failed after retries")
