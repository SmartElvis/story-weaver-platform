"""Tests for stratified style-chunk sampling.

Verifies that select_stratified_chunk_ids samples across the WHOLE corpus
(all books + beginning/middle/end), which is the fix for "style analysis only
looked at the opening".
"""

from types import SimpleNamespace

from app.services.style_pipeline import (
    select_stratified_chunk_ids,
    batch_chunks,
    PROFILER_BATCH_SIZE,
)


def _row(source_book, chunk_index, cid):
    return SimpleNamespace(source_book=source_book, chunk_index=chunk_index, id=cid)


def test_empty_corpus_returns_empty():
    assert select_stratified_chunk_ids([]) == []


def test_single_book_spans_beginning_to_end():
    rows = [_row("BookA", i, f"A{i}") for i in range(200)]
    selected = select_stratified_chunk_ids(rows, total_budget=48)
    idxs = sorted(int(s[1:]) for s in selected)
    assert len(selected) == 48
    assert idxs[0] == 0          # includes the very beginning
    assert idxs[-1] == 199       # includes the very end
    # spread across the whole range, not clustered at the front
    assert idxs[len(idxs) // 2] > 80


def test_tiny_corpus_fully_kept():
    rows = [_row("X", i, f"x{i}") for i in range(4)]
    selected = select_stratified_chunk_ids(rows, total_budget=48)
    assert len(selected) == 4
    assert set(selected) == {"x0", "x1", "x2", "x3"}


def test_multi_book_distribution_small_book_fully_included():
    rows = (
        [_row("B1", i, f"1_{i}") for i in range(100)]
        + [_row("B2", i, f"2_{i}") for i in range(30)]
        + [_row("B3", i, f"3_{i}") for i in range(5)]
    )
    selected = select_stratified_chunk_ids(rows, total_budget=48)
    by_book = {}
    for s in selected:
        by_book.setdefault(s.split("_")[0], []).append(s)
    # every book is represented
    assert set(by_book) == {"1", "2", "3"}
    # the small 5-chunk book is fully included
    assert len(by_book["3"]) == 5


def test_none_source_book_is_grouped():
    rows = [_row(None, i, f"n{i}") for i in range(60)]
    selected = select_stratified_chunk_ids(rows, total_budget=48)
    idxs = sorted(int(s[1:]) for s in selected)
    assert idxs[0] == 0
    assert idxs[-1] == 59


def test_no_duplicate_ids():
    rows = [_row("B", i, f"b{i}") for i in range(500)]
    selected = select_stratified_chunk_ids(rows, total_budget=48)
    assert len(selected) == len(set(selected))


# ── batch_chunks (map step of map-reduce profiling) ────────────────────────


def test_batch_chunks_splits_evenly():
    items = list(range(16))
    batches = batch_chunks(items, size=8)
    assert len(batches) == 2
    assert batches[0] == list(range(8))
    assert batches[1] == list(range(8, 16))


def test_batch_chunks_last_batch_partial():
    items = list(range(10))
    batches = batch_chunks(items, size=8)
    assert len(batches) == 2
    assert batches[1] == [8, 9]
    # order and content fully preserved
    assert [x for b in batches for x in b] == items


def test_batch_chunks_smaller_than_one_batch():
    assert batch_chunks(["a", "b"], size=8) == [["a", "b"]]


def test_batch_chunks_empty():
    assert batch_chunks([], size=8) == []


def test_profiler_batch_size_is_small():
    # Keep batches small enough to fit comfortably in a model context window.
    assert 1 <= PROFILER_BATCH_SIZE <= 12
