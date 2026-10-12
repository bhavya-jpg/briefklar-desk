"""Judge check: re-run the deterministic parts on cached model outputs and compare with the committed numbers.

    python -m briefklar.verify --replay data/replay --bench data/bench_small

Re-runs tools, linker and scoring over the bench subset in replay mode (no model, no network), prints a
short table, and exits non-zero if the result differs from bench/eval/results/summary_small.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replay", default="data/replay")
    parser.add_argument("--bench", default="data/bench_small")
    args = parser.parse_args()
    os.environ["BRIEFKLAR_MODE"] = "replay"
    os.environ["BRIEFKLAR_DATA_DIR"] = str(Path(args.replay).resolve().parent)
    logging.getLogger("briefklar").setLevel(logging.WARNING)

    from bench.eval.run import RESULTS_DIR, evaluate, print_table
    from briefklar.config import get_settings
    from briefklar.llm.client import LLMClient

    settings = get_settings()
    summary = evaluate(Path(args.bench), settings, LLMClient(settings))["summary"]
    print_table(summary)
    expected_path = RESULTS_DIR / "summary_small.json"
    if not expected_path.is_file():
        print(f"FAIL: {expected_path} is missing. Run `make eval` and commit it.")
        return 1
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(summary))
    if actual != expected:
        diff = [k for k in sorted(set(actual["systems"]) | set(expected["systems"]))
                if actual["systems"].get(k) != expected["systems"].get(k)]
        print(f"FAIL: results differ from {expected_path.name} (systems: {', '.join(diff) or 'see pipeline/provenance'}).")
        return 1
    if summary["pipeline"]["letters_failed"]:
        print(f"FAIL: {summary['pipeline']['letters_failed']} letters have no cached response.")
        return 1
    print("OK: cached outputs reproduce the committed summary exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
