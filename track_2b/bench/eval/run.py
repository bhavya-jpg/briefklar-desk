"""Evaluation harness (spec section 15).

    python -m bench.eval.run --mode replay      # recompute every metric from cached responses, no GPU
    python -m bench.eval.run --mode live        # re-run the systems against LLM_BASE_URL / JUDGE_BASE_URL

What runs where:
  B0  Tesseract + regex              always (no model)
  BK  Briefklar full pipeline        from data/replay/ (replay) or LLM_BASE_URL (live)
  B1  OCR -> plain translation       live only, needs the reader model (JUDGE_*)
  B2  OCR text -> explanation        live only, needs the reader model
  B3  vision, no tools               live only, needs the reader model

When data/replay/ holds FIXTURE responses, BK's numbers measure the deterministic parts only (deadline
engine, linker, red-flag checks, ordering) on perfect extraction. They are not model results, and the
summary says so in `provenance`.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

from bench.common import DATA_DIR, read_jsonl, write_json
from bench.eval import metrics as m
from bench.eval.baselines import NEXT_STEP_BY_TYPE, b0_predict

RESULTS_DIR = Path(__file__).parent / "results"
LABELS = {"B0": "Tesseract + regex rules", "B1": "OCR + Apertus translation only", "B2": "OCR text + Apertus explanation",
          "B3": "Apertus vision, no tools", "BK": "Briefklar full pipeline"}
NEEDS_MODEL = "needs recorded Apertus responses and the reader model (run `make eval-live`)"


def run_briefklar(set_dir: Path, settings, client) -> tuple[dict[str, dict], dict[str, dict], dict]:
    """Run the product pipeline over a bench set. Returns (letter predictions, case predictions, stats)."""
    from briefklar.models import Case
    from briefklar.pipeline import reply as reply_pass
    from briefklar.pipeline import run as pipeline
    from briefklar.llm.client import ReplayMiss, SchemaError
    from briefklar.preprocess import scan_upload
    from briefklar.present import creditor_totals
    from briefklar.session.store import Store

    store = Store(settings)
    rows = {r["id"]: r for r in read_jsonl(set_dir / "letters.jsonl")}
    letters: dict[str, dict] = {}
    cases: dict[str, dict] = {}
    stats = {"letters_failed": 0, "orchestrator_forced_tool_calls": 0, "model_tool_calls": 0, "model_missed_links": 0}
    for case_row in read_jsonl(set_dir / "cases.jsonl"):
        session = store.create_case(case_row["client_language"], case_row["canton"],
                                    today=date.fromisoformat(case_row["as_of"]))
        case: Case = session.case
        for letter_id in case_row["letter_ids"]:
            path = set_dir / rows[letter_id]["images"]["phone"]
            scans = scan_upload(path.read_bytes(), path.name, settings)
            pages = [store.add_page(session, s, path.name, page_id=f"{letter_id}-p{i}") for i, s in enumerate(scans)]
            store.add_letter(session, [p.id for p in pages], letter_id=letter_id, label=letter_id)
        for letter in case.letters:
            pipeline.process_letter(session, letter, client, settings)
        pipeline.finish_case(session, client)
        today = pipeline.case_today(session, settings)
        for letter in case.letters:
            row = rows[letter.id]
            if letter.status != "done":
                stats["letters_failed"] += 1
                letters[letter.id] = {"letter_type": None, "facts": {}, "due_date": None, "next_step": "unknown",
                                      "red_flags": [], "flagged": False,
                                      # B0 reads the OCR text and must not depend on the model run succeeding
                                      "ocr_text": "\n".join(p.ocr_text for p in session.pages_of(letter)),
                                      "chrf": None,
                                      "low_confidence": None, "reply": None}
                continue
            letter.delivery_date = date.fromisoformat(row["delivered_on"]) if row["delivered_on"] else None
            pipeline.recompute_deadline(session, letter, settings)
            facts, verification = letter.facts, letter.verification
            flags = [f.code for f in verification.red_flags]
            stats["orchestrator_forced_tool_calls"] += len(verification.orchestrator_forced_tools)
            stats["model_tool_calls"] += len(verification.model_tool_calls)
            reply = None
            if facts.letter_type == "payment_order" and not flags:
                try:
                    draft = reply_pass.draft_reply(client, letter, "objection_payment_order", today)
                    reply = {"slots": draft.slots, "missing": draft.missing}
                except (ReplayMiss, SchemaError, FileNotFoundError):
                    reply = {"slots": {}, "missing": ["all"]}
            deadline = verification.deadline
            letters[letter.id] = {
                "letter_type": facts.letter_type, "facts": facts.model_dump(mode="json"),
                "due_date": deadline.due_date.isoformat() if deadline and deadline.due_date else None,
                "next_step": "beware" if flags else NEXT_STEP_BY_TYPE[facts.letter_type],
                "red_flags": flags, "flagged": bool(flags),
                "ocr_text": "\n".join(p.ocr_text for p in session.pages_of(letter)),
                "chrf": letter.explanation.backtranslation_chrf if letter.explanation else None,
                "low_confidence": letter.explanation.low_confidence if letter.explanation else None,
                "reply": reply,
            }
        stats["model_missed_links"] += case.model_misses
        cases[case_row["case_id"]] = {
            "order": list(case.order),
            "threads": [t.letter_ids for t in case.threads if t.confirmed and not t.rejected],
            "totals": {t["creditor"]: t["total"] for t in creditor_totals(case)},
        }
        store.wipe(case.id)
    return letters, cases, stats


def gold_totals(case_row: dict, golds: dict[str, dict]) -> dict[str, str]:
    from bench.common import gold_letter
    from briefklar.models import Case, Thread
    from briefklar.present import creditor_totals

    as_of = date.fromisoformat(case_row["as_of"])
    case = Case(id="gold", created_at=datetime.now(timezone.utc), client_language="de", canton=case_row["canton"],
                letters=[gold_letter(golds[i], case_row["canton"], as_of) for i in case_row["letter_ids"]])
    case.threads = [Thread(id=f"g{i}", letter_ids=ids, reason="gold", confirmed=True)
                    for i, ids in enumerate(case_row["gold_threads"])]
    return {t["creditor"]: t["total"] for t in creditor_totals(case)}


def score_letters(predictions: dict[str, dict], rows: list[dict]) -> tuple[dict, list[dict]]:
    counts = {"deadline": 0, "type": 0, "next_step": 0, "action": 0}
    fields = {f: [0, 0, 0] for f in m.FIELDS}
    flag_letter, flag_code = [0, 0, 0], [0, 0, 0]
    per_letter = []
    for row in rows:
        pred = predictions[row["id"]]
        gold = row["gold_facts"]
        deadline_ok = pred["due_date"] == row["gold_due_date"]
        type_ok = pred["letter_type"] == gold["letter_type"]
        step_ok = pred["next_step"] == row["gold_next_step"]
        counts["deadline"] += deadline_ok
        counts["type"] += type_ok
        counts["next_step"] += step_ok
        counts["action"] += deadline_ok and step_ok
        for field, (tp, fp, fn) in m.field_counts(pred["facts"], gold).items():
            for i, v in enumerate((tp, fp, fn)):
                fields[field][i] += v
        flag_letter[0] += pred["flagged"] and row["gold_scam"]
        flag_letter[1] += pred["flagged"] and not row["gold_scam"]
        flag_letter[2] += (not pred["flagged"]) and row["gold_scam"]
        p_codes, g_codes = set(pred["red_flags"]), set(row["gold_red_flags"])
        flag_code[0] += len(p_codes & g_codes)
        flag_code[1] += len(p_codes - g_codes)
        flag_code[2] += len(g_codes - p_codes)
        per_letter.append({"id": row["id"], "case_id": row["case_id"], "type": gold["letter_type"], "lang": row["lang"],
                           "pred_type": pred["letter_type"], "gold_due_date": row["gold_due_date"],
                           "pred_due_date": pred["due_date"], "deadline_ok": int(deadline_ok), "type_ok": int(type_ok),
                           "next_step_ok": int(step_ok), "pred_flags": " ".join(sorted(p_codes)),
                           "gold_flags": " ".join(sorted(g_codes))})
    n = len(rows)
    totals = [sum(v[i] for v in fields.values()) for i in range(3)]
    precision, recall = m.precision_recall(*flag_letter)
    code_precision, code_recall = m.precision_recall(*flag_code)
    return {
        "action_correctness": m.ratio(counts["action"], n), "deadline_accuracy": m.ratio(counts["deadline"], n),
        "letter_type_accuracy": m.ratio(counts["type"], n), "next_step_accuracy": m.ratio(counts["next_step"], n),
        "field_f1": m.f1(*totals), "field_f1_by_field": {f: m.f1(*v) for f, v in fields.items()},
        "red_flag_precision": precision, "red_flag_recall": recall,
        "red_flag_code_precision": code_precision, "red_flag_code_recall": code_recall,
    }, per_letter


def score_cases(case_predictions: dict[str, dict], case_rows: list[dict], golds: dict[str, dict]) -> tuple[dict, list[dict]]:
    taus, pair_counts, total_hits, total_n, per_case = [], [0, 0, 0], 0, 0, []
    for row in case_rows:
        pred = case_predictions[row["case_id"]]
        tau = m.kendall_tau(pred["order"], row["gold_order"])
        if tau is not None:
            taus.append(tau)
        for i, v in enumerate(m.pairwise_counts(pred["threads"], row["gold_threads"])):
            pair_counts[i] += v
        expected = gold_totals(row, golds)
        hits = sum(pred["totals"].get(creditor) == total for creditor, total in expected.items())
        total_hits += hits
        total_n += len(expected)
        per_case.append({"case_id": row["case_id"], "lang": row["lang"], "letters": len(row["letter_ids"]),
                         "triage_tau": tau, "totals_correct": hits, "totals_expected": len(expected)})
    return {"triage_tau": round(statistics.mean(taus), 4) if taus else None, "thread_f1": m.f1(*pair_counts),
            "open_total_accuracy": m.ratio(total_hits, total_n)}, per_case


def score_replies(predictions: dict[str, dict], rows: list[dict]) -> float | None:
    """Share of required objection elements that are present and correct."""
    hits = total = 0
    for row in rows:
        reply = predictions[row["id"]].get("reply")
        if reply is None:
            continue
        gold = row["gold_facts"]
        expected = {"debtor_name": gold["recipient_name"], "office_name": gold["sender_name"],
                    "enforcement_number": gold["reference_numbers"][0]}
        for slot, value in expected.items():
            total += 1
            hits += reply["slots"].get(slot) == value
        for slot in ("debtor_address", "office_address", "objection_sentence", "date", "signature_line"):
            total += 1
            hits += bool(reply["slots"].get(slot)) and slot not in reply["missing"]
    return m.ratio(hits, total)


def evaluate(set_dir: Path, settings, client) -> dict:
    from briefklar.llm.client import replay_manifest

    rows = read_jsonl(set_dir / "letters.jsonl")
    case_rows = read_jsonl(set_dir / "cases.jsonl")
    golds = {r["id"]: json.loads((set_dir / "gold" / f"{r['id']}.json").read_text(encoding="utf-8")) for r in rows}
    bk_letters, bk_cases, stats = run_briefklar(set_dir, settings, client)

    bk_metrics, per_letter = score_letters(bk_letters, rows)
    case_metrics, per_case = score_cases(bk_cases, case_rows, golds)
    bk_metrics.update(case_metrics)
    bk_metrics["reply_completeness"] = score_replies(bk_letters, rows)
    chrfs = [p["chrf"] for p in bk_letters.values() if p["chrf"] is not None]
    low = [p["low_confidence"] for p in bk_letters.values() if p["low_confidence"] is not None]
    bk_metrics["median_backtranslation_chrf"] = round(statistics.median(chrfs), 1) if chrfs else None
    bk_metrics["low_confidence_share"] = m.ratio(sum(low), len(low))

    b0 = {r["id"]: b0_predict(bk_letters[r["id"]]["ocr_text"], date.fromisoformat(r["delivered_on"]) if r["delivered_on"] else None)
          for r in rows}
    b0_metrics, b0_per_letter = score_letters(b0, rows)
    for row, b0_row in zip(per_letter, b0_per_letter):
        row.update(b0_pred_due_date=b0_row["pred_due_date"], b0_deadline_ok=b0_row["deadline_ok"], b0_type_ok=b0_row["type_ok"])

    language_of = {c["case_id"]: c["client_language"] for c in case_rows}
    by_language: dict[str, list[float]] = {}
    for row in rows:
        chrf = bk_letters[row["id"]]["chrf"]
        if chrf is not None:
            by_language.setdefault(language_of[row["case_id"]], []).append(chrf)
    per_language = [{"language": lang, "letters": len(v), "median_backtranslation_chrf": round(statistics.median(v), 1)}
                    for lang, v in sorted(by_language.items())]

    manifest = replay_manifest(settings) if settings.mode == "replay" else {"backend": "http", "model": settings.llm_name}
    fixture = manifest.get("backend") == "fixture"
    summary = {
        "set": set_dir.name, "letters": len(rows), "cases": len(case_rows),
        "provenance": {
            "model_outputs": manifest.get("backend", "unknown"), "model": manifest.get("model"),
            "note": ("FIXTURE responses, not Apertus output. BK shows how the deterministic parts behave on perfect "
                     "extraction. B0 is a real measurement. No number here describes Apertus."
                     if fixture else "Model responses recorded from the endpoint named in data/replay/MANIFEST.json."),
        },
        "systems": {
            "B0": {"label": LABELS["B0"], "status": "ok", "metrics": b0_metrics},
            "B1": {"label": LABELS["B1"], "status": "not_run", "reason": NEEDS_MODEL},
            "B2": {"label": LABELS["B2"], "status": "not_run", "reason": NEEDS_MODEL},
            "B3": {"label": LABELS["B3"], "status": "not_run", "reason": NEEDS_MODEL},
            "BK": {"label": LABELS["BK"], "status": "ok", "metrics": bk_metrics},
        },
        "pipeline": stats,
        "not_measured": ["faithfulness (needs the judge model)", "native-speaker language checks",
                         "latency and cost per case (needs a GPU run)", "judge-human agreement"],
    }
    return {"summary": summary, "per_letter": per_letter, "per_case": per_case, "per_language": per_language}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def bar_figure(path: Path, title: str, metric: str, summary: dict) -> None:
    """One horizontal bar per system: teal for Briefklar, grey for baselines, values labelled directly."""
    systems = summary["systems"]
    width, row_h, left = 720, 44, 250
    height = 70 + row_h * len(systems) + 34
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="Inter Tight, sans-serif">',
             f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
             f'<text x="24" y="34" font-size="18" font-weight="600" fill="#14161A">{title}</text>',
             f'<text x="24" y="56" font-size="12" fill="#4A4F57">{summary["set"]}: {summary["letters"]} letters, {summary["cases"]} cases</text>']
    for i, (key, system) in enumerate(systems.items()):
        y = 78 + i * row_h
        value = (system.get("metrics") or {}).get(metric)
        parts.append(f'<text x="24" y="{y + 19}" font-size="13" fill="#14161A">{key} · {system["label"]}</text>')
        if value is None:
            reason = "not run" if system["status"] != "ok" else "n/a"
            parts.append(f'<text x="{left}" y="{y + 19}" font-size="13" fill="#4A4F57">{reason}</text>')
            continue
        length = max(2, (width - left - 80) * max(0.0, value))
        colour = "#0F6E6A" if key == "BK" else "#A9AEB6"
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{length:.1f}" height="22" rx="3" fill="{colour}"/>')
        parts.append(f'<text x="{left + length + 8:.1f}" y="{y + 20}" font-size="13" font-weight="600" fill="#14161A">{value:.2f}</text>')
    if summary["provenance"]["model_outputs"] == "fixture":
        parts.append(f'<text x="24" y="{height - 14}" font-size="12" font-weight="600" fill="#8F5D00">'
                     'BK bar uses FIXTURE responses, not Apertus output. Not a result.</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    global RESULTS_DIR
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["replay", "live"], default="replay")
    parser.add_argument("--set", default=str(DATA_DIR / "bench_small"), help="bench directory with letters.jsonl")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR), help="where to write the summary, CSVs and figures")
    args = parser.parse_args()
    os.environ["BRIEFKLAR_MODE"] = args.mode
    if args.mode == "live":
        os.environ["BRIEFKLAR_RECORD"] = "1"

    from briefklar.config import get_settings
    from briefklar.llm.client import LLMClient

    settings = get_settings()
    set_dir = Path(args.set)
    result = evaluate(set_dir, settings, LLMClient(settings))
    summary = result["summary"]
    RESULTS_DIR = Path(args.results_dir)
    name = "summary_small.json" if set_dir.name == "bench_small" else "summary.json"
    write_json(RESULTS_DIR / name, summary)
    write_csv(RESULTS_DIR / "per_letter.csv", result["per_letter"])
    write_csv(RESULTS_DIR / "per_case.csv", result["per_case"])
    write_csv(RESULTS_DIR / "per_language.csv", result["per_language"])
    bar_figure(RESULTS_DIR / "figures" / "deadline_accuracy.svg", "Deadline: exact date", "deadline_accuracy", summary)
    bar_figure(RESULTS_DIR / "figures" / "action_correctness.svg", "Action correctness", "action_correctness", summary)
    print_table(summary)
    print(f"wrote {RESULTS_DIR / name}")


def print_table(summary: dict) -> None:
    print(f"\n{summary['set']}: {summary['letters']} letters, {summary['cases']} cases")
    print(f"model outputs: {summary['provenance']['model_outputs']}  ({summary['provenance']['note']})\n")
    keys = ["action_correctness", "deadline_accuracy", "letter_type_accuracy", "field_f1", "red_flag_recall",
            "triage_tau", "thread_f1", "open_total_accuracy", "reply_completeness"]
    print(f"{'metric':<24}" + "".join(f"{k:>10}" for k in summary["systems"]))
    for key in keys:
        cells = []
        for system in summary["systems"].values():
            value = (system.get("metrics") or {}).get(key)
            cells.append(f"{'not run' if system['status'] != 'ok' else '-' if value is None else format(value, '.2f'):>10}")
        print(f"{key:<24}" + "".join(cells))
    print()


if __name__ == "__main__":
    main()
