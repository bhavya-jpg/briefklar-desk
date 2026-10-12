"""HTTP API (spec section 11). No database: everything lives in the session store."""

from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from briefklar import i18n
from briefklar.api import demo
from briefklar.config import PROJECT_DIR
from briefklar.llm.client import ReplayMiss, SchemaError, replay_manifest
from briefklar.models import CantonCode, LangCode
from briefklar.pipeline import reply as reply_pass
from briefklar.pipeline import run as pipeline
from briefklar.pipeline.case import order_letters
from briefklar.preprocess import scan_upload
from briefklar.preprocess.image import UnreadablePage
from briefklar.present import present_case
from briefklar.render import handout as render
from briefklar.session.store import NotFound, Session

router = APIRouter(prefix="/api")

MAX_PAGES_PER_CASE = 40
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
PDF_HEADERS = {"Cache-Control": "no-store"}


class NewCase(BaseModel):
    client_language: LangCode
    canton: CantonCode | None = None


class GroupPages(BaseModel):
    page_ids: list[str]


class DeliveryDate(BaseModel):
    date: date | None


class NewReply(BaseModel):
    template_id: str


class ReplyEdit(BaseModel):
    slots: dict[str, str]


class ThreadDecision(BaseModel):
    confirmed: bool = True
    case_id: str | None = None


class CaseEdit(BaseModel):
    client_name: str | None = None


def _state(request: Request):
    return request.app.state


def _session(request: Request, case_id: str) -> Session:
    try:
        return _state(request).store.get(case_id)
    except NotFound:
        raise HTTPException(404, "This case no longer exists. It was closed or has expired.") from None


def _today(request: Request, session: Session) -> date:
    return pipeline.case_today(session, _state(request).settings)


def _present(request: Request, session: Session) -> dict:
    return present_case(session.case, _today(request, session))


# -- health and reference data -------------------------------------------------------------------


@router.get("/health")
def health(request: Request) -> dict:
    settings = _state(request).settings
    replay = settings.mode == "replay"
    manifest = replay_manifest(settings) if replay else None
    return {
        "status": "ok",
        "mode": settings.mode,
        "model": settings.llm_name,
        "endpoint_host": None if replay else settings.llm_host,
        "offline": settings.offline,
        "canton": settings.canton,
        "replay": manifest,
        "demo": demo.summary(settings),
    }


@router.get("/languages")
def languages() -> dict:
    lights = i18n.language_lights()
    return {
        "languages": [
            {"code": code, **meta, **lights["languages"].get(code, {"light": "unmeasured"}),
             "strings": i18n.strings_for(code)}
            for code, meta in i18n.languages().items()
        ],
        "thresholds": lights["thresholds"],
        "generated_by": lights.get("generated_by"),
    }


@router.get("/eval")
def eval_summary() -> dict:
    """The committed evaluation summary for the bench subset, shown on the landing page."""
    path = PROJECT_DIR / "bench" / "eval" / "results" / "summary_small.json"
    if not path.is_file():
        raise HTTPException(404, "No evaluation has been run on this build yet.")
    return json.loads(path.read_text(encoding="utf-8"))


# -- cases ---------------------------------------------------------------------------------------


@router.get("/cases")
def list_cases(request: Request) -> list[dict]:
    """Cases open in this session (memory only)."""
    return [
        {"id": s.case.id, "status": s.case.status, "client_language": s.case.client_language,
         "letters": len(s.case.letters), "created_at": s.case.created_at.isoformat(), "demo": s.case.demo}
        for s in _state(request).store.sessions.values()
    ]


@router.post("/cases")
def create_case(body: NewCase, request: Request) -> dict:
    state = _state(request)
    session = state.store.create_case(body.client_language, body.canton or state.settings.canton)
    return {"case_id": session.case.id}


@router.post("/demo")
async def create_demo_case(body: NewCase, request: Request) -> dict:
    state = _state(request)
    try:
        session = await asyncio.to_thread(demo.load_demo_case, state.store, state.settings, body.client_language)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    return {"case_id": session.case.id}


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request) -> dict:
    return _present(request, _session(request, case_id))


@router.put("/cases/{case_id}")
def edit_case(case_id: str, body: CaseEdit, request: Request) -> dict:
    session = _session(request, case_id)
    session.case.client_name = (body.client_name or "").strip() or None
    return _present(request, session)


@router.delete("/cases/{case_id}")
def wipe_case(case_id: str, request: Request) -> dict:
    try:
        _state(request).store.wipe(case_id)
    except NotFound:
        raise HTTPException(404, "This case no longer exists.") from None
    return {"wiped": True}


@router.post("/cases/{case_id}/pages")
async def upload_pages(case_id: str, request: Request, files: list[UploadFile] = File(...)) -> dict:
    state = _state(request)
    session = _session(request, case_id)
    added, errors = [], []
    for upload in files:
        data = await upload.read()
        name = upload.filename or "page"
        if len(data) > MAX_UPLOAD_BYTES:
            errors.append({"filename": name, "message": "This file is too large. Use a file under 25 MB."})
            continue
        try:
            scans = await asyncio.to_thread(scan_upload, data, name, state.settings)
        except UnreadablePage as exc:
            errors.append({"filename": name, "message": str(exc)})
            continue
        if len(session.case.pages) + len(scans) > MAX_PAGES_PER_CASE:
            errors.append({"filename": name, "message": f"A case can hold {MAX_PAGES_PER_CASE} pages."})
            break
        pages = [state.store.add_page(session, scan, name) for scan in scans]
        letter = state.store.add_letter(session, [p.id for p in pages])  # one upload = one letter by default
        added.append({"letter_id": letter.id, "page_ids": letter.page_ids})
    return {"added": added, "errors": errors, "case": _present(request, session)}


@router.get("/cases/{case_id}/pages/{page_id}.jpg")
def page_image(case_id: str, page_id: str, request: Request) -> FileResponse:
    session = _session(request, case_id)
    try:
        session.page(page_id)
    except NotFound:
        raise HTTPException(404, "Page not found.") from None
    return FileResponse(session.image_path(page_id), media_type="image/jpeg", headers=PDF_HEADERS)


@router.delete("/cases/{case_id}/pages/{page_id}")
def delete_page(case_id: str, page_id: str, request: Request) -> dict:
    session = _session(request, case_id)
    case = session.case
    case.pages = [p for p in case.pages if p.id != page_id]
    for letter in case.letters:
        letter.page_ids = [p for p in letter.page_ids if p != page_id]
    case.letters = [l for l in case.letters if l.page_ids]
    for kind in ("display", "model"):
        session.image_path(page_id, kind).unlink(missing_ok=True)
    return _present(request, session)


@router.post("/cases/{case_id}/letters")
def group_pages(case_id: str, body: GroupPages, request: Request) -> dict:
    session = _session(request, case_id)
    if not body.page_ids:
        raise HTTPException(422, "Choose at least one page.")
    try:
        letter = _state(request).store.add_letter(session, body.page_ids)
    except NotFound:
        raise HTTPException(404, "Page not found.") from None
    return {"letter_id": letter.id, "case": _present(request, session)}


@router.post("/cases/{case_id}/process")
async def process(case_id: str, request: Request) -> dict:
    state = _state(request)
    session = _session(request, case_id)
    if session.task is not None and not session.task.done():
        return {"started": False, "status": session.case.status}
    if not session.case.letters:
        raise HTTPException(422, "Add at least one letter first.")
    session.case.status = "processing"
    session.task = asyncio.create_task(pipeline.process_case(session, state.client, state.settings))
    return {"started": True, "status": "processing"}


@router.get("/cases/{case_id}/events")
async def events(case_id: str, request: Request) -> StreamingResponse:
    session = _session(request, case_id)
    queue: asyncio.Queue = asyncio.Queue()
    backlog = list(session.events)
    session.subscribers.add(queue)

    async def stream():
        try:
            for message in backlog:
                yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"
                if message["event"] == "case.closed":
                    break
        finally:
            session.subscribers.discard(queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# -- letters -------------------------------------------------------------------------------------


def _letter(request: Request, letter_id: str):
    try:
        return _state(request).store.find_letter(letter_id)
    except NotFound:
        raise HTTPException(404, "This letter no longer exists.") from None


@router.post("/letters/{letter_id}/delivery-date")
def set_delivery_date(letter_id: str, body: DeliveryDate, request: Request) -> dict:
    session, letter = _letter(request, letter_id)
    today = _today(request, session)
    if body.date and body.date > today:
        raise HTTPException(422, "The delivery date cannot be in the future.")
    letter.delivery_date = body.date
    pipeline.recompute_deadline(session, letter, _state(request).settings)
    return _present(request, session)


@router.post("/letters/{letter_id}/retry")
async def retry_letter(letter_id: str, request: Request) -> dict:
    state = _state(request)
    session, letter = _letter(request, letter_id)
    if session.task is not None and not session.task.done():
        raise HTTPException(409, "The case is still being read.")
    letter.status, letter.error = "queued", None
    session.task = asyncio.create_task(pipeline.process_case(session, state.client, state.settings))
    return {"started": True}


@router.post("/letters/{letter_id}/skip")
def skip_letter(letter_id: str, request: Request) -> dict:
    session, letter = _letter(request, letter_id)
    letter.status, letter.stage = "skipped", None
    session.case.order = order_letters(session.case)
    return _present(request, session)


# -- threads -------------------------------------------------------------------------------------


@router.post("/threads/{thread_id}/confirm")
def confirm_thread(thread_id: str, body: ThreadDecision, request: Request) -> dict:
    try:
        session, thread = _state(request).store.find_thread(body.case_id, thread_id)
    except NotFound:
        raise HTTPException(404, "This link no longer exists.") from None
    thread.confirmed, thread.rejected = body.confirmed, not body.confirmed
    thread.origin = "counsellor"
    return _present(request, session)


# -- replies -------------------------------------------------------------------------------------


@router.post("/letters/{letter_id}/replies")
async def create_reply(letter_id: str, body: NewReply, request: Request) -> dict:
    state = _state(request)
    session, letter = _letter(request, letter_id)
    if letter.facts is None:
        raise HTTPException(409, "This letter has not been read yet.")
    if letter.verification and letter.verification.red_flags:
        raise HTTPException(409, "This letter shows warning signs. No reply is drafted to its sender.")
    if body.template_id not in {t["id"] for t in reply_pass.available_templates(letter.facts)}:
        raise HTTPException(422, "This reply does not fit this kind of letter.")
    try:
        draft = await asyncio.to_thread(reply_pass.draft_reply, state.client, letter, body.template_id,
                                        _today(request, session))
    except (ReplayMiss, SchemaError) as exc:
        raise HTTPException(503, str(exc)) from None
    session.case.replies = [r for r in session.case.replies
                            if not (r.letter_id == letter.id and r.template_id == draft.template_id)]
    session.case.replies.append(draft)
    return {"reply": draft.model_dump(mode="json"), "case_id": session.case.id}


def _reply(request: Request, reply_id: str):
    try:
        return _state(request).store.find_reply(reply_id)
    except NotFound:
        raise HTTPException(404, "This reply no longer exists.") from None


@router.get("/replies/{reply_id}.pdf")
async def reply_pdf(reply_id: str, request: Request) -> Response:
    _, draft = _reply(request, reply_id)
    if reply_pass.SOURCE_REQUIRED in draft.slots.values():
        raise HTTPException(409, "The fixed wording of this reply has no official source yet, so it cannot be printed.")
    pdf = await asyncio.to_thread(render.reply_pdf, draft)
    return Response(pdf, media_type="application/pdf", headers=PDF_HEADERS)


@router.get("/replies/{reply_id}")
def get_reply(reply_id: str, request: Request) -> dict:
    session, draft = _reply(request, reply_id)
    template = reply_pass.load_template(draft.template_id, draft.language)
    return {"reply": draft.model_dump(mode="json"), "case_id": session.case.id,
            "template": {"title": template["title"], "body": template["body"], "fixed": list(template["fixed"]),
                         "free_text": template["free_text"], "source": template.get("source")}}


@router.put("/replies/{reply_id}")
def edit_reply(reply_id: str, body: ReplyEdit, request: Request) -> dict:
    session, draft = _reply(request, reply_id)
    updated = reply_pass.update_reply(draft, body.slots)
    session.case.replies = [updated if r.id == draft.id else r for r in session.case.replies]
    return {"reply": updated.model_dump(mode="json")}


# -- printouts -----------------------------------------------------------------------------------


@router.get("/cases/{case_id}/handout.pdf")
async def handout_pdf(case_id: str, request: Request) -> Response:
    session = _session(request, case_id)
    pdf = await asyncio.to_thread(render.handout_pdf, session.case, _today(request, session))
    return Response(pdf, media_type="application/pdf", headers=PDF_HEADERS)


@router.get("/cases/{case_id}/handout.html")
def handout_preview(case_id: str, request: Request) -> HTMLResponse:
    session = _session(request, case_id)
    html = render.handout_html(session.case, _today(request, session), font_base_url="/fonts")
    return HTMLResponse(html, headers=PDF_HEADERS)


@router.get("/cases/{case_id}/case-note.pdf")
async def case_note_pdf(case_id: str, request: Request) -> Response:
    session = _session(request, case_id)
    pdf = await asyncio.to_thread(render.case_note_pdf, session.case, _today(request, session))
    return Response(pdf, media_type="application/pdf", headers=PDF_HEADERS)
