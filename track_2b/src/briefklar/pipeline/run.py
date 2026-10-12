"""Orchestration of the per-letter passes and the case pass (spec section 5.3)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from briefklar.config import Settings
from briefklar.llm.client import LLMClient, ReplayMiss, SchemaError
from briefklar.models import Letter
from briefklar.pipeline import case as case_pass
from briefklar.pipeline import check, explain, extract, verify
from briefklar.session.store import Session

log = logging.getLogger("briefklar.pipeline")

STAGES = ("reading", "sender", "dates", "warnings", "writing")


def case_today(session: Session, settings: Settings) -> date:
    return session.case.today or settings.today()


def process_letter(session: Session, letter: Letter, client: LLMClient, settings: Settings) -> None:
    """Run passes 1-4 for one letter. Blocking; call from a worker thread."""
    case = session.case
    pages = session.pages_of(letter)
    letter.status, letter.error = "processing", None

    def stage(name: str) -> None:
        letter.stage = name
        session.emit("letter.stage", letter_id=letter.id, stage=name)

    try:
        stage("reading")
        letter.facts = extract.extract(client, letter, pages, [session.image_path(p.id, "model") for p in pages])
        stage("sender")
        letter.verification = verify.verify(client, letter, pages, case.canton, case_today(session, settings))
        stage("dates")
        stage("warnings")
        stage("writing")
        simple_german = explain.explain(client, letter, "de")
        letter.explanation_de = simple_german
        if case.client_language == "de":
            letter.explanation = simple_german
        else:
            target = explain.explain(client, letter, case.client_language)
            letter.explanation = check.check(client, letter, target, simple_german)
        letter.status, letter.stage = "done", None
        session.emit("letter.done", letter_id=letter.id)
    except (ReplayMiss, SchemaError) as exc:
        _fail(session, letter, str(exc))
    except Exception as exc:  # noqa: BLE001 - one letter must never take the case down
        log.exception("letter failed stage=%s letter=%s error=%s", letter.stage, letter.id, type(exc).__name__)
        _fail(session, letter, "This letter could not be read. Try again, or take a new photo.")


def _fail(session: Session, letter: Letter, message: str) -> None:
    letter.status, letter.error = "failed", message
    session.emit("error", letter_id=letter.id, stage=letter.stage, message=message)


def finish_case(session: Session, client: LLMClient) -> None:
    case = session.case
    try:
        case_pass.run_case_pass(client, case)
    except (ReplayMiss, SchemaError) as exc:
        # The board still works without model proposals: the linker and the order are deterministic.
        log.info("case pass unavailable: %s", type(exc).__name__)
        threads, _ = case_pass.build_threads(case_pass.done_letters(case), case_pass.CaseProposal())
        case.threads, case.order = threads, case_pass.order_letters(case)
        session.emit("error", letter_id=None, stage="case", message=str(exc))
    case.status = "ready"
    session.emit("case.done")


async def process_case(session: Session, client: LLMClient, settings: Settings) -> None:
    """Process all queued or failed letters, at most `max_parallel_letters` at a time, then the case pass."""
    case = session.case
    case.status = "processing"
    session.loop = asyncio.get_running_loop()
    limit = asyncio.Semaphore(settings.max_parallel_letters)

    async def one(letter: Letter) -> None:
        async with limit:
            await asyncio.to_thread(process_letter, session, letter, client, settings)

    todo = [l for l in case.letters if l.status in ("queued", "failed")]
    for letter in todo:
        letter.status, letter.error, letter.stage = "queued", None, None
    await asyncio.gather(*(one(letter) for letter in todo))
    await asyncio.to_thread(finish_case, session, client)


def recompute_deadline(session: Session, letter: Letter, settings: Settings) -> None:
    """Deterministic only: called when the counsellor enters the delivery date."""
    if letter.facts is None or letter.verification is None:
        return
    letter.verification.deadline = verify.deadline_for(
        letter.facts, letter.delivery_date, session.case.canton, case_today(session, settings)
    )
    session.case.order = case_pass.order_letters(session.case)
