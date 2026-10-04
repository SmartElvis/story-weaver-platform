"""Content-free style-feature filtering.

The Profiler produces a rich style profile, but several of its free-text fields
tend to carry reference-specific content (character names, places, worldview,
plot). Injecting that verbatim into generation prompts lets the reference works
bleed into the novel. This module provides a dependency-free helper that keeps
only a curated allowlist of categorical/structural fields that are inherently
content-free, so it can be unit-tested without importing the ORM models.
"""

from typing import Optional

# Technique-only allowlist of style-feature fields. Free-text fields that tend to
# carry reference content (frequent_phrases, sentence_patterns,
# paragraph_structure, dialogue_style, description_style, scene_transition,
# overall_mood, dialect_features) are deliberately excluded. ``style_guide`` is
# handled separately by callers (passed as its own argument) and is not included.
TECHNIQUE_ALLOWLIST = {
    "lexicon": ("vocabulary_level",),
    "syntax": ("avg_sentence_length",),
    "rhetoric": ("figurative_devices",),
    "narrative": ("pov", "tense", "pacing"),
    "tone": ("humor_level", "emotional_intensity"),
}


def technique_only_features(style_features: Optional[dict]) -> dict:
    """Reduce a full style profile to content-free, technique-only fields.

    Args:
        style_features: The full Profiler output (may be None or malformed).

    Returns:
        A dict containing only the allowlisted categorical/structural fields,
        preserving the section structure. Empty/missing sections are omitted.
    """
    if not isinstance(style_features, dict):
        return {}
    filtered: dict = {}
    for section, keys in TECHNIQUE_ALLOWLIST.items():
        source = style_features.get(section)
        if not isinstance(source, dict):
            continue
        kept = {key: source[key] for key in keys if key in source}
        if kept:
            filtered[section] = kept
    return filtered
