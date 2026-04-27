"""Approximate string matching for the manga search endpoints.

Wraps stdlib `difflib` with simple normalization and a substring-aware
similarity score. Tolerates roughly one error per three characters
(default threshold 0.55), enough to forgive typos like "berzerk" / "berserk"
or "atak on titan" / "attack on titan".

This runs candidate ranking in Python — fine for catalogs in the low
thousands. For substantially larger catalogs, swap to a database-side
trigram index (pg_trgm) and treat this as a fallback.
"""

import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List, NamedTuple, Sequence


DEFAULT_THRESHOLD = 0.55


class Scored(NamedTuple):
    item: object
    score: float


def normalize(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


def similarity(query_norm: str, target_norm: str) -> float:
    if not target_norm:
        return 0.0
    if query_norm == target_norm:
        return 1.0
    if query_norm and query_norm in target_norm:
        # substring match — strong signal; longer overlap is better
        return 0.9 + 0.1 * (len(query_norm) / max(len(target_norm), len(query_norm)))
    return SequenceMatcher(None, query_norm, target_norm).ratio()


def best_field_score(query_norm: str, fields: Sequence[str]) -> float:
    if not query_norm:
        return 0.0
    best = 0.0
    for field in fields:
        score = similarity(query_norm, normalize(field))
        if score > best:
            best = score
    return best


def fuzzy_rank(
    query: str,
    candidates: Iterable[tuple[object, Sequence[str]]],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    limit: int | None = None,
) -> List[Scored]:
    """Score candidates against query and return matches above threshold."""
    q = normalize(query)
    if not q:
        return []

    scored: List[Scored] = []
    for item, fields in candidates:
        score = best_field_score(q, fields)
        if score >= threshold:
            scored.append(Scored(item, score))

    scored.sort(key=lambda r: r.score, reverse=True)
    if limit is not None:
        scored = scored[:limit]
    return scored
