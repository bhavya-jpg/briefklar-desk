"""Build Swiss Letters Bench v0: synthetic letters, case bundles and gold (spec section 14).

    python -m bench.generator.build --seed 7

Writes:
  data/demo/         the 8-letter demo case (scanner quality) used in the video and in replay mode
  data/bench_small/  the judge-facing subset, phone quality only
  bench/out/         the full set in the Hugging Face layout (eval/, metadata/); not committed

Regenerating changes the images, so cached model responses in data/replay/ must be recorded again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from bench.common import AS_OF, BENCH_DIR, CLIENT_LANGUAGES, DATA_DIR, gold_case_view, write_json, write_jsonl
from bench.generator import render
from bench.generator.content import (
    CANTONS, GENERATOR_VERSION, Generator, LetterSpec, Person, available_kinds, gold_due_date,
)

CASE_SIZES = [8, 7] * 10  # 20 bundles, 150 letters
CASE_LANGS = ["de", "de", "fr", "de", "de", "it", "de", "fr", "de", "de",
              "de", "it", "de", "fr", "de", "de", "it", "de", "fr", "de"]
SCAM_CASES = {0, 3, 6, 9, 12, 15}  # 6 of 20 bundles carry a letter with warning signs
SMALL_CASES = 3
CHAIN_KINDS = {"invoice_qr", "reminder", "payment_order"}
LICENCE = "CDLA-Permissive-2.0"


def finish(spec: LetterSpec, case_id: str) -> dict:
    spec.case_id = case_id
    gold = {
        "id": spec.id, "case_id": case_id, "lang": spec.lang, "canton": spec.canton,
        "delivered_on": spec.delivered_on.isoformat() if spec.delivered_on else None,
        **spec.gold, "gold_due_date": gold_due_date(spec, AS_OF),
    }
    return gold


def demo_case(gen: Generator) -> tuple[list[LetterSpec], dict]:
    """The demo case: a reminder chain that became a payment order, a letter with warning signs, and
    four unrelated letters. Delivered Thu 8 Oct 2026 -> objection deadline Mon 19 Oct 2026."""
    lang, canton = "de", "BE"
    client = Person("Arta Krasniqi-Berisha", "Lindenrain 14", "3012 Bern")  # fictional
    claim = gen.claim(lang, "demo-thread-1", creditor_index=0)
    claim.principal = __import__("decimal").Decimal("1126.70")
    claim.invoice_date = date(2026, 7, 28)
    plan = [
        ("demo-01", "reminder", dict(claim=claim, level=1, letter_date=date(2026, 9, 1))),
        ("demo-02", "reminder", dict(claim=claim, level=2, letter_date=date(2026, 9, 22))),
        ("demo-03", "payment_order", dict(claim=claim, letter_date=date(2026, 10, 6),
                                          overrides={"amount_rows": [("principal", "1126.70"), ("fees", "40.00"), ("costs", "73.30")]})),
        ("demo-04", "scam_sem", dict(letter_date=date(2026, 10, 7), overrides={"due": date(2026, 10, 12)})),
        ("demo-05", "serafe_invoice", dict(letter_date=date(2026, 10, 1), overrides={"due": date(2026, 10, 31)})),
        ("demo-06", "tax_assessment", dict(letter_date=date(2026, 9, 29), overrides={"due": date(2026, 11, 13)})),
        ("demo-07", "school_notice", dict(letter_date=date(2026, 10, 5), overrides={"due": date(2026, 10, 23)})),
        ("demo-08", "premium_reduction", dict(letter_date=date(2026, 9, 24))),
    ]
    specs = [gen.build(kind, letter_id, lang, canton, client, **kwargs) for letter_id, kind, kwargs in plan]
    for spec in specs:
        spec.delivered_on = date.fromisoformat(spec.gold["facts"]["letter_date"]) + timedelta(days=2)
    return specs, {"lang": lang, "canton": canton}


def bench_cases(gen: Generator) -> list[tuple[str, str, str, list[LetterSpec]]]:
    cases = []
    counter = 0
    filler_cursor: dict[str, int] = {}

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"SLB-{counter:04d}"

    for index, (size, lang) in enumerate(zip(CASE_SIZES, CASE_LANGS)):
        case_id = f"case-{index + 1:02d}"
        canton = CANTONS[lang][index % len(CANTONS[lang])]
        client = gen.person(lang)
        kinds = available_kinds(lang)
        specs: list[LetterSpec] = []

        # chain 1: reminders that escalate into a payment order (same creditor, rising fees, same reference)
        claim = gen.claim(lang, f"{case_id}-t1")
        levels = 3 if index % 5 == 0 else 2
        order_date = AS_OF - timedelta(days=gen.rng.randint(3, 7))
        for level in range(1, levels + 1):
            when = order_date - timedelta(days=14 + 20 * (levels - level) + gen.rng.randint(0, 4))
            specs.append(gen.build("reminder", next_id(), lang, canton, client, claim=claim, level=level, letter_date=when))
        specs.append(gen.build("payment_order", next_id(), lang, canton, client, claim=claim, letter_date=order_date))

        # chain 2 in every fourth case: an invoice with its first reminder (not yet escalated)
        if index % 4 == 0:
            second = gen.claim(lang, f"{case_id}-t2")
            second.invoice_date = AS_OF - timedelta(days=gen.rng.randint(40, 55))
            specs.append(gen.build("invoice_qr", next_id(), lang, canton, client, claim=second,
                                   letter_date=second.invoice_date))
            specs.append(gen.build("reminder", next_id(), lang, canton, client, claim=second, level=1,
                                   letter_date=AS_OF - timedelta(days=gen.rng.randint(4, 9))))

        scams = [k for k in kinds if k.startswith("scam")]
        if index in SCAM_CASES and scams:
            specs.append(gen.build(scams[index % len(scams)], next_id(), lang, canton, client))

        fillers = [k for k in kinds if not k.startswith("scam") and k not in ("reminder", "payment_order")]
        fillers = [k for k in fillers if not (k == "continuation_notice" and index % 4)]  # keep this one rare
        # an unrelated enforcement letter never names a creditor that already has a matter in this case
        taken = {s.gold["facts"]["creditor_name"] or s.gold["facts"]["sender_name"] for s in specs}
        while len(specs) < size:
            cursor = filler_cursor.get(lang, 0)
            filler_cursor[lang] = cursor + 1
            specs.append(gen.build(fillers[cursor % len(fillers)], next_id(), lang, canton, client, exclude=taken))

        for spec in specs:
            spec.delivered_on = min(spec.delivered_on, AS_OF)
        cases.append((case_id, lang, canton, specs))
    return cases


def write_set(out: Path, cases: list[tuple[str, str, str, list[LetterSpec]]], qualities: tuple[str, ...],
              seed: int, image_dir: str = "images") -> tuple[list[dict], list[dict], list[dict]]:
    letters, case_rows, metadata = [], [], []
    for number, (case_id, lang, canton, specs) in enumerate(cases):
        golds = []
        for spec in specs:
            gold = finish(spec, case_id)
            page = render.render_page(spec)
            images, shas = {}, {}
            for quality in qualities:
                data = render.degrade(page, quality, seed * 100003 + int(hashlib.sha256(spec.id.encode()).hexdigest()[:8], 16))
                rel = f"{image_dir}/{quality}/{spec.id}_p1.jpg"
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                (out / rel).write_bytes(data)
                images[quality], shas[quality] = rel, hashlib.sha256(data).hexdigest()
            gold["images"], gold["sha256"] = images, shas
            write_json(out / "gold" / f"{spec.id}.json", gold)
            golds.append(gold)
            letters.append({"id": spec.id, "case_id": case_id, "type": gold["facts"]["letter_type"], "lang": lang,
                            "canton": canton, "delivered_on": gold["delivered_on"], "images": images, "sha256": shas,
                            "gold_due_date": gold["gold_due_date"], "gold_next_step": gold["gold_next_step"],
                            "gold_red_flags": gold["gold_red_flags"], "gold_scam": gold["gold_scam"],
                            "gold_thread_id": gold["gold_thread_id"], "gold_facts": gold["facts"]})
            metadata.append({"id": spec.id, "generator_version": GENERATOR_VERSION, "seed": seed,
                             "template": gold["template"], "template_source": gold["template_source"],
                             "period_source": gold["period_source"], "licence": LICENCE, "synthetic": True,
                             "contains_personal_data": False})
        order, threads = gold_case_view(golds, canton, AS_OF)
        case_rows.append({"case_id": case_id, "lang": lang, "canton": canton, "as_of": AS_OF.isoformat(),
                          "client_language": CLIENT_LANGUAGES[number % len(CLIENT_LANGUAGES)],
                          "letter_ids": [s.id for s in specs], "gold_order": order, "gold_threads": threads})
    return letters, case_rows, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-full", action="store_true", help="only write data/demo and data/bench_small")
    args = parser.parse_args()

    gen = Generator(args.seed, AS_OF)
    demo_specs, demo_meta = demo_case(gen)
    cases = bench_cases(gen)
    total = sum(len(specs) for *_, specs in cases)
    print(f"generated {total} letters in {len(cases)} cases, plus {len(demo_specs)} demo letters")

    # demo: scanner quality, flat layout
    demo_dir = DATA_DIR / "demo"
    previous = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8")) if (demo_dir / "manifest.json").is_file() else {}
    shutil.rmtree(demo_dir, ignore_errors=True)
    letters, case_rows, _ = write_set(demo_dir, [("demo", demo_meta["lang"], demo_meta["canton"], demo_specs)],
                                      ("clean",), args.seed, image_dir="images")
    shas = {l["id"]: l["sha256"]["clean"] for l in letters}
    write_json(demo_dir / "manifest.json", {
        "as_of": AS_OF.isoformat(), "canton": demo_meta["canton"], "source_language": demo_meta["lang"],
        "note": "Synthetic letters. Every person, company, address and reference is fictional.",
        # cached responses are keyed by the image bytes: they stay valid only if no image changed
        "recorded_languages": previous.get("recorded_languages", []) if previous.get("image_sha256") == shas else [],
        "image_sha256": shas,
        "letters": [
            # the payment order starts without a delivery date: the counsellor enters it (Thu 8 Oct 2026)
            {"id": l["id"], "files": [l["images"]["clean"]], "type": l["type"],
             "delivery_date": None if l["type"] == "payment_order" else l["delivered_on"],
             "suggested_delivery_date": l["delivered_on"]}
            for l in letters
        ],
        "gold_order": case_rows[0]["gold_order"], "gold_threads": case_rows[0]["gold_threads"],
    })

    small_dir = DATA_DIR / "bench_small"
    shutil.rmtree(small_dir, ignore_errors=True)
    letters, case_rows, metadata = write_set(small_dir, cases[:SMALL_CASES], ("phone",), args.seed)
    write_jsonl(small_dir / "letters.jsonl", letters)
    write_jsonl(small_dir / "cases.jsonl", case_rows)
    write_jsonl(small_dir / "metadata.jsonl", metadata)
    print(f"data/bench_small: {len(letters)} letters in {len(case_rows)} cases (phone quality)")

    if not args.skip_full:
        full_dir = BENCH_DIR / "out" / "swiss-letters-bench-v0"
        shutil.rmtree(full_dir, ignore_errors=True)
        letters, case_rows, metadata = write_set(full_dir / "eval", cases, render.QUALITIES, args.seed)
        write_jsonl(full_dir / "eval" / "letters.jsonl", letters)
        write_jsonl(full_dir / "eval" / "cases.jsonl", case_rows)
        write_jsonl(full_dir / "metadata" / "metadata.jsonl", metadata)
        (full_dir / "responses").mkdir(parents=True, exist_ok=True)
        shutil.copy(BENCH_DIR / "dataset_card.md", full_dir / "README.md")
        print(f"bench/out: {len(letters)} letters x {len(render.QUALITIES)} qualities")


if __name__ == "__main__":
    main()
