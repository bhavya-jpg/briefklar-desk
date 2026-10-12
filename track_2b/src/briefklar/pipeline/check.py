"""Pass 4: back-translation check of the client-language explanation (no thinking)."""

from __future__ import annotations

import re
import unicodedata

from sacrebleu.metrics import CHRF

from briefklar import i18n
from briefklar.i18n import DUE_DATE_TOKEN
from briefklar.llm import prompts
from briefklar.llm.client import LLMClient
from briefklar.models import Explanation, Letter, LetterFacts

_chrf = CHRF()


def chrf(hypothesis: str, reference: str) -> float:
    return round(_chrf.sentence_score(hypothesis, [reference]).score, 1)


def _normalise_numbers(text: str) -> str:
    text = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text)
    return re.sub(r"(?<=\d)['’‘`´   ](?=\d{3}\b)", "", text)


def field_failures(text: str, reference: str, facts: LetterFacts) -> list[str]:
    """Which of date, amount and sender are in the reference but did not survive in `text`."""
    failures = []
    if DUE_DATE_TOKEN in reference and DUE_DATE_TOKEN not in text:
        failures.append("date")
    if facts.amount_due:
        whole = str(int(facts.amount_due.amount))
        pattern = re.compile(rf"(?<!\d){whole}(?!\d)")
        if pattern.search(_normalise_numbers(reference)) and not pattern.search(_normalise_numbers(text)):
            failures.append("amount")
    if facts.sender_name:
        sender = facts.sender_name.casefold()
        if sender in reference.casefold() and sender not in text.casefold():
            failures.append("sender")
    return failures


def back_translate(client: LLMClient, letter: Letter, explanation: Explanation) -> str:
    response = client.chat(
        [{"role": "system", "content": prompts.load("check")},
         {"role": "user", "content": explanation.text()}],
        pass_name=f"check:{explanation.language}", letter_id=letter.id, label=letter.label or "",
    )
    return (response.content or "").strip()


def check(client: LLMClient, letter: Letter, explanation: Explanation, simple_german: Explanation) -> Explanation:
    """Score `explanation` against the simple-German twin; set low_confidence when it falls short."""
    assert letter.facts is not None
    if explanation.language == "de":
        return explanation
    reference = simple_german.text()
    back = back_translate(client, letter, explanation)
    score = chrf(back, reference)
    failures = sorted(set(field_failures(back, reference, letter.facts))
                      | set(field_failures(explanation.text(), reference, letter.facts)))
    return explanation.model_copy(update={
        "backtranslation_chrf": score,
        "failed_field_checks": failures,
        "low_confidence": score < i18n.chrf_threshold(explanation.language) or bool(failures),
    })
