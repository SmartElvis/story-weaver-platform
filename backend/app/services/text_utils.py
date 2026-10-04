"""Text tokenization helpers for full-text (BM25) search.

Kept free of database/model imports so it can be unit-tested in isolation.
"""

import re

import jieba

# A token is kept only if it contains at least one letter/number. This drops
# jieba's punctuation and whitespace tokens (e.g. "，", "……", "\n"), which are
# invalid tsquery operands ("no operand in tsquery") and useless tsvector noise.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text_value: str) -> list[str]:
    """Jieba-split text and keep only tokens that contain a letter or number."""
    return [t for t in jieba.cut(text_value) if _TOKEN_RE.search(t)]


def build_tsquery(query: str) -> str:
    """Build an OR tsquery string from cleaned query tokens ('' if none)."""
    return " | ".join(tokenize(query))
