"""Prompt files, versioned with the code. Changing a prompt changes every replay key that uses it."""

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    return (_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
