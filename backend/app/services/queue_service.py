"""ARQ task-queue helpers.

Long-running jobs (chapter generation, finalization, style analysis, style-file
processing) used to run via FastAPI ``BackgroundTasks`` inside the web process.
That meant a restart/deploy silently killed in-flight jobs and multiple workers
couldn't share the load. These jobs are now enqueued onto Redis and executed by
a dedicated ARQ worker process (see ``app/worker.py``).
"""

import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

logger = logging.getLogger(__name__)


def redis_settings() -> RedisSettings:
    """Build ARQ Redis settings from the shared REDIS_URL."""
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def enqueue_job(job_name: str, *args, **kwargs):
    """Enqueue a job onto the ARQ queue.

    Opens a short-lived Redis connection per call. The generate/finalize/
    analyze endpoints are low-frequency (one call per user action), so a
    per-call pool is acceptable and avoids managing global connection state.
    """
    redis: ArqRedis = await create_pool(redis_settings())
    try:
        job = await redis.enqueue_job(job_name, *args, **kwargs)
        logger.info("Enqueued job %s (job_id=%s)", job_name, getattr(job, "job_id", "?"))
        return job
    finally:
        await redis.aclose()
