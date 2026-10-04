"""Pure text-diff utilities used by the workflow pipeline.

Extracted from ``workflow.py`` so the logic is dependency-free (no DB, no LLM)
and can be unit-tested in isolation.
"""

import difflib

# Unified-diff output is capped to keep persisted payloads small.
MAX_DIFF_CHARS = 6000


def compute_diff(draft: str, final: str) -> dict:
    """Compute the diff between a draft and its finalized content.

    Returns:
        {
            "similarity": float (0-1),
            "magnitude": "none" | "minor" | "moderate" | "major",
            "diff_text": str (unified diff, capped at MAX_DIFF_CHARS chars)
        }
    """
    if not draft and not final:
        return {"similarity": 1.0, "magnitude": "none", "diff_text": ""}

    if not draft or not final:
        return {"similarity": 0.0, "magnitude": "major", "diff_text": ""}

    # Compute similarity
    similarity = difflib.SequenceMatcher(None, draft, final).ratio()

    # Determine magnitude
    if similarity >= 0.99:
        magnitude = "none"
    elif similarity >= 0.90:
        magnitude = "minor"
    elif similarity >= 0.70:
        magnitude = "moderate"
    else:
        magnitude = "major"

    # Generate unified diff (capped)
    draft_lines = draft.splitlines(keepends=True)
    final_lines = final.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            draft_lines,
            final_lines,
            fromfile="draft",
            tofile="final",
            lineterm="",
        )
    )
    diff_text = "\n".join(diff_lines)
    if len(diff_text) > MAX_DIFF_CHARS:
        diff_text = diff_text[:MAX_DIFF_CHARS] + "\n... (truncated)"

    return {
        "similarity": round(similarity, 4),
        "magnitude": magnitude,
        "diff_text": diff_text,
    }
