"""Tests for app.services.diff_utils.compute_diff."""

from app.services.diff_utils import compute_diff, MAX_DIFF_CHARS


def test_both_empty_is_none_magnitude():
    result = compute_diff("", "")
    assert result["similarity"] == 1.0
    assert result["magnitude"] == "none"
    assert result["diff_text"] == ""


def test_one_side_empty_is_major():
    result = compute_diff("some draft text", "")
    assert result["similarity"] == 0.0
    assert result["magnitude"] == "major"

    result2 = compute_diff("", "final only")
    assert result2["similarity"] == 0.0
    assert result2["magnitude"] == "major"


def test_identical_text_is_none():
    text = "第一章\n他走進房間，看見窗外的月光。"
    result = compute_diff(text, text)
    assert result["similarity"] == 1.0
    assert result["magnitude"] == "none"


def test_minor_change_bucket():
    draft = "A" * 1000
    final = "A" * 950 + "B" * 50  # ~5% changed → similarity ~0.95
    result = compute_diff(draft, final)
    assert result["magnitude"] == "minor"
    assert 0.90 <= result["similarity"] < 0.99


def test_major_change_bucket():
    draft = "aaaaaaaaaaaaaaaaaaaa"
    final = "completely different content here"
    result = compute_diff(draft, final)
    assert result["magnitude"] == "major"
    assert result["similarity"] < 0.70


def test_diff_text_is_capped():
    draft = "line a\n" * 5000
    final = "line b\n" * 5000
    result = compute_diff(draft, final)
    assert len(result["diff_text"]) <= MAX_DIFF_CHARS + len("\n... (truncated)")
    assert result["diff_text"].endswith("... (truncated)")


def test_similarity_is_rounded():
    result = compute_diff("abcde", "abcdx")
    # 4 decimal places max
    assert result["similarity"] == round(result["similarity"], 4)
