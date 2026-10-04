"""Tests for content-free style-feature filtering.

Verifies that technique_only_features strips the free-text fields that tend to
carry reference content (character names, places, worldview, plot) while keeping
the categorical/structural technique fields that are safe to inject into
generation prompts.
"""

from app.services.style_features import technique_only_features


def _full_profile():
    """A realistic Profiler output mixing safe fields with content-prone ones."""
    return {
        "lexicon": {
            "frequent_phrases": ["畢文中", "舊公寓", "落地鐘"],  # reference content!
            "vocabulary_level": "literary",
            "dialect_features": ["北方口語"],
        },
        "syntax": {
            "avg_sentence_length": "long",
            "sentence_patterns": ["他覺得婚姻是一座圍城"],  # reference content!
            "paragraph_structure": "短段密集",
        },
        "rhetoric": {
            "figurative_devices": ["比喻", "擬人"],
            "dialogue_style": "含蓄書面",
            "description_style": "細膩",
        },
        "narrative": {
            "pov": "third_limited",
            "tense": "past",
            "pacing": "slow",
            "scene_transition": "在舊公寓與士多之間切換",  # reference content!
        },
        "tone": {
            "overall_mood": "末日後獨身者的孤絕",  # worldview-ish!
            "humor_level": "subtle",
            "emotional_intensity": "restrained",
        },
        "style_guide": "短句為主，善用感官描寫。",
    }


def test_keeps_allowlisted_technique_fields():
    filtered = technique_only_features(_full_profile())
    assert filtered["lexicon"] == {"vocabulary_level": "literary"}
    assert filtered["syntax"] == {"avg_sentence_length": "long"}
    assert filtered["rhetoric"] == {"figurative_devices": ["比喻", "擬人"]}
    assert filtered["narrative"] == {"pov": "third_limited", "tense": "past", "pacing": "slow"}
    assert filtered["tone"] == {"humor_level": "subtle", "emotional_intensity": "restrained"}


def test_drops_content_prone_freetext_fields():
    filtered = technique_only_features(_full_profile())
    flat = str(filtered)
    # None of the reference-specific content may survive filtering.
    for leaked in ("畢文中", "舊公寓", "落地鐘", "圍城", "士多", "末日"):
        assert leaked not in flat
    # The free-text field keys themselves are excluded.
    assert "frequent_phrases" not in flat
    assert "sentence_patterns" not in flat
    assert "overall_mood" not in flat
    assert "scene_transition" not in flat


def test_style_guide_not_included():
    # style_guide is passed to agents as a separate argument, so the filter
    # deliberately omits it to avoid duplication.
    filtered = technique_only_features(_full_profile())
    assert "style_guide" not in filtered


def test_handles_none_and_malformed():
    assert technique_only_features(None) == {}
    assert technique_only_features({}) == {}
    # Non-dict sections are skipped without error.
    assert technique_only_features({"lexicon": "oops", "tone": {"humor_level": "heavy"}}) == {
        "tone": {"humor_level": "heavy"}
    }
