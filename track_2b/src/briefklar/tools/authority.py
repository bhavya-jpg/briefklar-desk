"""Lookup of a claimed sender in the local authority directory (spec section 9.4)."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from briefklar.config import KNOWLEDGE_DIR

MATCH_THRESHOLD = 90
CONTACT_FIELDS = ("phone", "email", "web", "address")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


@lru_cache
def load_directory(path: Path | None = None) -> tuple[dict, ...]:
    data = yaml.safe_load((path or KNOWLEDGE_DIR / "authorities.yaml").read_text(encoding="utf-8"))
    return tuple(data["authorities"])


def _score(query: str, name: str) -> float:
    q, n = normalise(query), normalise(name)
    if not q or not n:
        return 0.0
    if len(n) <= 5:  # acronyms such as "SEM": whole-word match only
        return 100.0 if n in q.split() else 0.0
    if n in q:
        return 100.0
    return fuzz.token_sort_ratio(q, n)


def lookup_authority(sender_name: str | None, directory: tuple[dict, ...] | None = None) -> dict | None:
    """Return the best directory entry (with `match_score`) or None below the threshold."""
    if not sender_name:
        return None
    best, best_score = None, 0.0
    for entry in directory if directory is not None else load_directory():
        score = max((_score(sender_name, name) for name in entry.get("names", [])), default=0.0)
        if score > best_score:
            best, best_score = entry, score
    if best is None or best_score < MATCH_THRESHOLD:
        return None
    return {**best, "match_score": round(best_score, 1)}


def contact_of(entry: dict | None) -> dict | None:
    """The official contact to show instead of anything printed on a suspicious letter."""
    if entry is None:
        return None
    contact = {field: entry.get(field) for field in CONTACT_FIELDS}
    return {
        "id": entry["id"],
        "name": entry["names"][0],
        **contact,
        "source_url": entry.get("source_url"),
        "retrieved": str(entry["retrieved"]) if entry.get("retrieved") else None,
        "sourced": bool(entry.get("source_url")) and any(contact.values()),
    }
