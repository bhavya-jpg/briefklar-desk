"""In-memory session store. Images live under a tmpfs path; nothing survives a wipe or the TTL."""

from __future__ import annotations

import asyncio
import secrets
import shutil
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from briefklar.config import Settings, get_settings
from briefklar.models import Case, Letter, Page, ReplyDraft, Thread
from briefklar.preprocess import PageScan


class NotFound(KeyError):
    pass


@dataclass
class Session:
    case: Case
    dir: Path
    last_active: float = field(default_factory=time.monotonic)
    events: list[dict] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None
    loop: asyncio.AbstractEventLoop | None = None

    def touch(self) -> None:
        self.last_active = time.monotonic()

    def emit(self, event: str, **data) -> None:
        """Publish a progress event. Safe to call from worker threads. Events carry no letter content."""
        message = {"event": event, "data": data}

        def publish() -> None:
            self.events.append(message)
            for queue in list(self.subscribers):
                queue.put_nowait(message)

        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(publish)
        else:
            publish()

    def image_path(self, page_id: str, kind: str = "display") -> Path:
        return self.dir / f"{page_id}.{kind}.jpg"

    def page(self, page_id: str) -> Page:
        for page in self.case.pages:
            if page.id == page_id:
                return page
        raise NotFound(page_id)

    def letter(self, letter_id: str) -> Letter:
        for letter in self.case.letters:
            if letter.id == letter_id:
                return letter
        raise NotFound(letter_id)

    def pages_of(self, letter: Letter) -> list[Page]:
        return [self.page(pid) for pid in letter.page_ids]


class Store:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.sessions: dict[str, Session] = {}

    def create_case(self, client_language: str, canton: str, *, demo: bool = False,
                    today: date | None = None) -> Session:
        case_id = secrets.token_urlsafe(9)  # random, not tied to client identity
        directory = self.settings.tmp_dir / case_id
        directory.mkdir(parents=True, exist_ok=True)
        case = Case(
            id=case_id, created_at=datetime.now(timezone.utc), client_language=client_language,  # type: ignore[arg-type]
            canton=canton, demo=demo, today=today,  # type: ignore[arg-type]
        )
        session = Session(case=case, dir=directory)
        self.sessions[case_id] = session
        return session

    def get(self, case_id: str) -> Session:
        session = self.sessions.get(case_id)
        if session is None:
            raise NotFound(case_id)
        session.touch()
        return session

    def add_page(self, session: Session, scan: PageScan, filename: str, page_id: str | None = None) -> Page:
        page = Page(
            id=page_id or secrets.token_urlsafe(6), filename=filename, sha256=scan.sha256,
            width=scan.width, height=scan.height, ocr_text=scan.ocr_text, ocr_words=scan.ocr_words,
            qr_payloads=scan.qr_payloads, source_language=scan.source_language,  # type: ignore[arg-type]
        )
        session.image_path(page.id, "display").write_bytes(scan.display_jpeg)
        session.image_path(page.id, "model").write_bytes(scan.model_jpeg)
        session.case.pages.append(page)
        return page

    def add_letter(self, session: Session, page_ids: list[str], letter_id: str | None = None,
                   label: str | None = None) -> Letter:
        for page_id in page_ids:
            session.page(page_id)
        for letter in session.case.letters:  # a page belongs to one letter
            letter.page_ids = [p for p in letter.page_ids if p not in page_ids]
        session.case.letters = [l for l in session.case.letters if l.page_ids]
        letter = Letter(id=letter_id or secrets.token_urlsafe(6), page_ids=page_ids, label=label)
        session.case.letters.append(letter)
        return letter

    def find_letter(self, letter_id: str) -> tuple[Session, Letter]:
        for session in self.sessions.values():
            for letter in session.case.letters:
                if letter.id == letter_id:
                    session.touch()
                    return session, letter
        raise NotFound(letter_id)

    def find_reply(self, reply_id: str) -> tuple[Session, ReplyDraft]:
        for session in self.sessions.values():
            for reply in session.case.replies:
                if reply.id == reply_id:
                    session.touch()
                    return session, reply
        raise NotFound(reply_id)

    def find_thread(self, case_id: str | None, thread_id: str) -> tuple[Session, Thread]:
        sessions = [self.get(case_id)] if case_id else list(self.sessions.values())
        for session in sessions:
            for thread in session.case.threads:
                if thread.id == thread_id:
                    session.touch()
                    return session, thread
        raise NotFound(thread_id)

    def wipe(self, case_id: str) -> None:
        """Delete images from disk and results from memory."""
        session = self.sessions.pop(case_id, None)
        if session is None:
            raise NotFound(case_id)
        if session.task is not None and not session.task.done():
            session.task.cancel()
        session.emit("case.closed")
        shutil.rmtree(session.dir, ignore_errors=True)
        session.case.letters.clear()
        session.case.pages.clear()
        session.case.replies.clear()
        session.case.threads.clear()
        session.events.clear()
        session.case.status = "closed"

    def sweep(self) -> list[str]:
        """Wipe sessions idle for longer than the TTL."""
        limit = self.settings.session_ttl_min * 60
        now = time.monotonic()
        expired = [cid for cid, s in self.sessions.items() if now - s.last_active > limit]
        for case_id in expired:
            self.wipe(case_id)
        return expired

    def wipe_all(self) -> None:
        for case_id in list(self.sessions):
            self.wipe(case_id)
