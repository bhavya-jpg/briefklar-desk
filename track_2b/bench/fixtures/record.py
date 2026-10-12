"""Record FIXTURE responses for the demo case and bench_small into data/replay/.

    python -m bench.fixtures.record

This runs the real pipeline (pre-processing, OCR, tools, linker, printouts) with the fixture backend
in place of the model, so that replay mode works before Apertus has been run. It is a stand-in:
`make record-live` runs the same script against LLM_BASE_URL and replaces every record.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def configure(live: bool) -> None:
    os.environ["BRIEFKLAR_MODE"] = "live"
    os.environ["BRIEFKLAR_RECORD"] = "1"
    os.environ.setdefault("LLM_NAME", "apertus-8b")
    if not live:
        os.environ["LLM_BASE_URL"] = "fixture://gold"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="record from LLM_BASE_URL instead of the fixture backend")
    parser.add_argument("--languages", default="all", help="comma-separated client languages for the demo case")
    args = parser.parse_args()
    configure(args.live)

    from bench.common import DATA_DIR, read_jsonl, write_json
    from bench.fixtures.model import CURRENT
    from briefklar.api.demo import load_demo_case
    from briefklar.config import get_settings
    from briefklar.llm.client import LLMClient
    from briefklar.models import LANG_CODES
    from briefklar.pipeline import reply as reply_pass
    from briefklar.pipeline import run as pipeline
    from briefklar.preprocess import scan_upload
    from briefklar.preprocess.ocr import ocr_languages
    from briefklar.session.store import Store

    settings = get_settings()
    if ocr_languages() != "deu+fra+ita":
        sys.exit(f"Tesseract has {ocr_languages()!r}, need deu+fra+ita (set TESSDATA_PREFIX). Refusing to record.")
    shutil.rmtree(settings.replay_dir, ignore_errors=True)
    client = LLMClient(settings)
    store = Store(settings)
    languages = list(LANG_CODES) if args.languages == "all" else args.languages.split(",")

    def run_letters(session, golds: dict[str, dict]) -> None:
        for letter in session.case.letters:
            token = CURRENT.set({"gold": golds[letter.label]})
            try:
                pipeline.process_letter(session, letter, client, settings)
            finally:
                CURRENT.reset(token)
            if letter.status != "done":
                sys.exit(f"recording failed for {letter.label}: {letter.error}")

    def run_case(session, case_gold: dict) -> None:
        token = CURRENT.set({"case": case_gold})
        try:
            pipeline.finish_case(session, client)
        finally:
            CURRENT.reset(token)

    # -- demo case, once per client language -----------------------------------------------------
    demo_dir = DATA_DIR / "demo"
    manifest = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))
    demo_gold = {e["id"]: json.loads((demo_dir / "gold" / f"{e['id']}.json").read_text(encoding="utf-8"))
                 for e in manifest["letters"]}
    for language in languages:
        session = load_demo_case(store, settings, language)
        run_letters(session, demo_gold)
        run_case(session, {"letter_ids": [l.label for l in session.case.letters],
                           "gold_order": manifest["gold_order"], "gold_threads": manifest["gold_threads"]})
        today = pipeline.case_today(session, settings)
        for letter in session.case.letters:  # every reply the UI offers for the demo letters
            if letter.verification.red_flags:
                continue
            for template in reply_pass.available_templates(letter.facts):
                token = CURRENT.set({"gold": demo_gold[letter.label]})
                try:
                    reply_pass.draft_reply(client, letter, template["id"], today)
                finally:
                    CURRENT.reset(token)
        store.wipe(session.case.id)
        print(f"demo recorded: {language}")

    # -- bench_small ------------------------------------------------------------------------------
    small = DATA_DIR / "bench_small"
    rows = {r["id"]: r for r in read_jsonl(small / "letters.jsonl")}
    for case_row in read_jsonl(small / "cases.jsonl"):
        session = store.create_case(case_row["client_language"], case_row["canton"],
                                    today=date.fromisoformat(case_row["as_of"]))
        golds = {}
        for letter_id in case_row["letter_ids"]:
            path = small / rows[letter_id]["images"]["phone"]
            scans = scan_upload(path.read_bytes(), path.name, settings)
            pages = [store.add_page(session, scan, path.name, page_id=f"{letter_id}-p{i}") for i, scan in enumerate(scans)]
            store.add_letter(session, [p.id for p in pages], letter_id=letter_id, label=letter_id)
            golds[letter_id] = json.loads((small / "gold" / f"{letter_id}.json").read_text(encoding="utf-8"))
        run_letters(session, golds)
        run_case(session, {"letter_ids": case_row["letter_ids"], "gold_order": case_row["gold_order"],
                           "gold_threads": case_row["gold_threads"]})
        for letter in session.case.letters:  # the eval drafts an objection for every payment order
            if letter.facts.letter_type == "payment_order" and not letter.verification.red_flags:
                token = CURRENT.set({"gold": golds[letter.id]})
                try:
                    reply_pass.draft_reply(client, letter, "objection_payment_order", pipeline.case_today(session, settings))
                finally:
                    CURRENT.reset(token)
        store.wipe(session.case.id)
        print(f"bench_small recorded: {case_row['case_id']} ({case_row['client_language']})")

    backend = "http" if args.live else "fixture"
    write_json(settings.replay_dir / "MANIFEST.json", {
        "backend": backend,
        "model": settings.llm_name if args.live else None,
        "note": ("Responses recorded from the model served at LLM_BASE_URL." if args.live else
                 "FIXTURE responses: written by bench/fixtures from gold data, NOT produced by Apertus. "
                 "They exercise the pipeline and the UI only. Record real ones with `make record-live`."),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "responses": len(list(settings.replay_dir.glob("*.json"))),
        "schema_retries": client.stats["schema_retries"],
        "demo_languages": languages,
    })
    manifest["recorded_languages"] = languages
    write_json(demo_dir / "manifest.json", manifest)
    print(f"{len(list(settings.replay_dir.glob('*.json')))} responses in {settings.replay_dir} (backend: {backend})")


if __name__ == "__main__":
    main()
