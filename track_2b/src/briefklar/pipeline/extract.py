"""Pass 1: extract LetterFacts from the page images (vision, thinking off)."""

from __future__ import annotations

import json
from pathlib import Path

from briefklar.llm import prompts
from briefklar.llm.client import LLMClient, image_part
from briefklar.models import Letter, LetterFacts, Page
from briefklar.preprocess.ocr import align_phrase


def build_messages(pages: list[Page], image_paths: list[Path]) -> list[dict]:
    schema = json.dumps(LetterFacts.model_json_schema(), ensure_ascii=False, sort_keys=True)
    ocr_text = "\n\n".join(f"[page {i}]\n{page.ocr_text}" for i, page in enumerate(pages))
    language = pages[0].source_language if pages else "de"
    return [
        {"role": "system", "content": f"{prompts.load('extract')}\n\nJSON schema:\n{schema}"},
        {"role": "user", "content": [
            *[image_part(path, page.sha256) for page, path in zip(pages, image_paths)],
            {"type": "text", "text": f"OCR (may contain errors):\n{ocr_text}\n\nSource language guess: {language}"},
        ]},
    ]


def ground_evidence(facts: LetterFacts, pages: list[Page]) -> None:
    """Fill each evidence box by aligning its phrase to the OCR word boxes of its page."""
    for item in facts.evidence_items:
        candidates = [item.page] if 0 <= item.page < len(pages) else []
        candidates += [i for i in range(len(pages)) if i not in candidates]
        for index in candidates:
            box = align_phrase(item.text, pages[index].ocr_words)
            if box is not None:
                item.page, item.bbox = index, box
                break
    known = {item.id for item in facts.evidence_items}
    facts.evidence = {field: [i for i in ids if i in known] for field, ids in facts.evidence.items()}


def extract(client: LLMClient, letter: Letter, pages: list[Page], image_paths: list[Path]) -> LetterFacts:
    facts = client.chat_json(
        build_messages(pages, image_paths), LetterFacts,
        pass_name="extract", letter_id=letter.id, label=letter.label or "",
    )
    ground_evidence(facts, pages)
    return facts
