"""Shared helpers for the generator, the fixture recorder and the eval harness."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from briefklar.models import Case, Letter, LetterFacts, RedFlag, Verification
from briefklar.pipeline import case as case_pass
from briefklar.pipeline.verify import deadline_for

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BENCH_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
AS_OF = date(2026, 10, 10)  # the bench's "today": all gold days-left values refer to it
CLIENT_LANGUAGES = ("sq", "pt", "ta", "ti", "ar", "bcs", "es", "uk", "tr", "en", "fr", "it", "de")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def gold_letter(gold: dict, canton: str, as_of: date) -> Letter:
    """A Letter built from gold, as a perfect pipeline would produce it (delivery date known)."""
    facts = LetterFacts.model_validate(gold["facts"])
    delivered = date.fromisoformat(gold["delivered_on"]) if gold.get("delivered_on") else None
    flags = [RedFlag(code=code, severity="high", evidence="gold") for code in gold["gold_red_flags"]]
    return Letter(
        id=gold["id"], page_ids=[], status="done", delivery_date=delivered, facts=facts,
        verification=Verification(deadline=deadline_for(facts, delivered, canton, as_of), red_flags=flags),
    )


def gold_case_view(golds: list[dict], canton: str, as_of: date) -> tuple[list[str], list[list[str]]]:
    """(gold_order, gold_threads) for a case, by the same ordering rules as the product (spec 8.5)."""
    letters = [gold_letter(g, canton, as_of) for g in golds]
    groups: dict[str, list[str]] = {}
    for g in golds:
        if g.get("gold_thread_id"):
            groups.setdefault(g["gold_thread_id"], []).append(g["id"])
    threads = [ids for ids in groups.values() if len(ids) > 1]
    case = Case(id="gold", created_at=datetime.now(timezone.utc), client_language="de", canton=canton,  # type: ignore[arg-type]
                letters=letters, today=as_of)
    case.threads = [
        case_pass.Thread(id=f"t{i}", letter_ids=ids, reason="gold", confirmed=True) for i, ids in enumerate(threads)
    ]
    return case_pass.order_letters(case), threads
