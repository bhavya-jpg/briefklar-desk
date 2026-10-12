"""The 8-letter demo case in data/demo/: synthetic letters, usable in replay mode without a GPU."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from briefklar.config import Settings
from briefklar.preprocess import scan_upload
from briefklar.session.store import Session, Store


@lru_cache
def _manifest(demo_dir: Path) -> dict | None:
    path = demo_dir / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def summary(settings: Settings) -> dict:
    manifest = _manifest(settings.data_dir / "demo")
    if manifest is None:
        return {"available": False}
    return {"available": True, "letters": len(manifest["letters"]), "as_of": manifest["as_of"],
            "canton": manifest["canton"], "languages": manifest.get("recorded_languages", [])}


def load_demo_case(store: Store, settings: Settings, client_language: str) -> Session:
    demo_dir = settings.data_dir / "demo"
    manifest = _manifest(demo_dir)
    if manifest is None:
        raise FileNotFoundError("The demo case is not installed (data/demo/manifest.json is missing).")
    session = store.create_case(client_language, manifest["canton"], demo=True,
                                today=date.fromisoformat(manifest["as_of"]))
    suffix = session.case.id  # letter ids are global in the API, so demo ids carry the case id
    for entry in manifest["letters"]:
        page_ids = []
        for index, filename in enumerate(entry["files"]):
            data = (demo_dir / filename).read_bytes()
            for scan in scan_upload(data, filename, settings):
                page = store.add_page(session, scan, filename, page_id=f"{entry['id']}-p{index}.{suffix}")
                page_ids.append(page.id)
        letter = store.add_letter(session, page_ids, letter_id=f"{entry['id']}.{suffix}", label=entry["id"])
        if entry.get("delivery_date"):
            letter.delivery_date = date.fromisoformat(entry["delivery_date"])
    return session
