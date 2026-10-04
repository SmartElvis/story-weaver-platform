"""
BaseAgent (Agent 基礎類別)

Provides shared infrastructure for all AI agents:
- LLM client construction from user settings
- A robust, reusable JSON parser for LLM responses that handles code fences,
  fullwidth punctuation, trailing commas, collapsed empty strings, and
  (optionally) truncated JSON repair.

Individual agents subclass ``BaseAgent`` and reuse ``_parse_json_response``
instead of each defining their own copy. Failure behaviour is configurable
per call so agents can either raise (strict) or fall back to a safe default.
"""

import copy
import json
import logging
import re
from typing import Any, Callable, Optional, Union

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# A fallback may be a plain dict (returned as a deep copy) or a callable that
# receives the raw response string and returns a dict.
Fallback = Union[dict, Callable[[str], dict], None]


def _extract_json_candidate(raw: str) -> str:
    """Extract the most likely JSON payload from a raw LLM response."""
    # Strip code fences (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Otherwise, extract the outermost {...} span
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]

    return raw.strip()


def _sanitize_candidate(candidate: str) -> str:
    """Fix common formatting issues in near-JSON text produced by LLMs."""
    candidate = candidate.replace("\uff0c", ",")  # fullwidth comma
    candidate = candidate.replace("\u201c", '"').replace("\u201d", '"')  # fullwidth double quotes
    candidate = candidate.replace("\u2018", "'").replace("\u2019", "'")  # fullwidth single quotes
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
    candidate = re.sub(r'""', '"-"', candidate)  # collapsed empty strings
    return candidate


def _repair_truncated(candidate: str) -> str:
    """Best-effort repair of truncated JSON by closing open brackets/braces."""
    repaired = candidate
    # Remove a trailing incomplete key/value fragment, then dangling commas
    repaired = re.sub(r',\s*"[^"]*"?\s*:?\s*"?[^"]*$', "", repaired)
    repaired = re.sub(r",\s*$", "", repaired)

    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")

    # Close arrays first, then objects
    repaired += "]" * max(open_brackets, 0)
    repaired += "}" * max(open_braces, 0)
    return repaired


def parse_json_response(
    raw: str,
    *,
    fallback: Fallback = None,
    repair_truncated: bool = False,
    agent_name: str = "agent",
) -> dict:
    """
    Robustly parse JSON from an LLM response.

    Args:
        raw: The raw text returned by the LLM.
        fallback: What to return if parsing fails. ``None`` means raise
            ``ValueError``. A dict is returned as a deep copy. A callable is
            invoked with ``raw`` and its result is returned.
        repair_truncated: If True, attempt to repair truncated JSON before
            giving up.
        agent_name: Used for log messages.

    Returns:
        The parsed dict.

    Raises:
        ValueError: If parsing fails and no fallback is provided.
    """
    candidate = _sanitize_candidate(_extract_json_candidate(raw))

    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError as first_error:
        if repair_truncated:
            try:
                result = json.loads(_repair_truncated(candidate), strict=False)
                logger.warning("%s JSON was truncated but successfully repaired", agent_name)
                return result
            except json.JSONDecodeError:
                pass

        logger.error(
            "%s JSON parse failed: %s\nRaw: %s", agent_name, first_error, raw[:500]
        )

        if fallback is None:
            raise ValueError(
                f"Failed to parse {agent_name} response as JSON: {first_error}"
            )
        if callable(fallback):
            return fallback(raw)
        return copy.deepcopy(fallback)


class BaseAgent:
    """Base class for all AI agents.

    Subclasses set ``agent_name`` and gain a configured ``LLMService`` plus a
    shared ``_parse_json_response`` helper.
    """

    agent_name: str = "agent"

    def __init__(self, llm_settings: Optional[dict] = None):
        self.llm = LLMService.from_user_settings(llm_settings, agent_name=self.agent_name)

    def _parse_json_response(
        self,
        raw: str,
        *,
        fallback: Fallback = None,
        repair_truncated: bool = False,
    ) -> dict:
        """Parse a JSON response using this agent's name for diagnostics."""
        return parse_json_response(
            raw,
            fallback=fallback,
            repair_truncated=repair_truncated,
            agent_name=self.agent_name,
        )
