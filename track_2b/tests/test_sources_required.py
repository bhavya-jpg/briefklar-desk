"""Open source work, as failing tests (spec section 0, rule 3).

Each test fails until a person has filled the item from an official source. They are marked
`source_required`; `make test-code` leaves them out, `make test` runs everything.
"""

from pathlib import Path

import pytest
import yaml

from bench.generator import content
from briefklar import i18n
from briefklar.config import KNOWLEDGE_DIR
from briefklar.models import LETTER_TYPES
from briefklar.pipeline import reply as reply_pass
from briefklar.tools import qrbill
from briefklar.tools.authority import load_directory
from briefklar.tools.scam import load_patterns

pytestmark = pytest.mark.source_required
TEMPLATE_DIR = Path(content.__file__).parent / "templates"


def test_every_authority_has_a_sourced_contact():
    open_entries = [e["id"] for e in load_directory()
                    if not (e.get("source_url") and e.get("retrieved") and (e.get("phone") or e.get("web")))]
    assert not open_entries, f"TODO(source): copy the official contact for {len(open_entries)} authorities: {open_entries}"


def test_every_letter_type_has_explainer_cards():
    missing = [f"{t}.{lang}" for t in LETTER_TYPES if t != "unknown" for lang in ("de", "fr", "it")
               if not (KNOWLEDGE_DIR / "explainers" / f"{t}.{lang}.md").is_file()]
    assert not missing, f"TODO(source): write these explainer cards from official information sheets: {missing}"


def test_reply_templates_have_sourced_fixed_wording():
    open_slots = [f"{t}.{lang}:{slot}" for t in reply_pass.TEMPLATE_IDS for lang in ("de", "fr", "it")
                  for slot, text in reply_pass.load_template(t, lang)["fixed"].items() if not text]
    assert not open_slots, f"TODO(source): fixed wording without an official source: {open_slots}"


def test_remedy_notice_types_are_sourced():
    assert load_patterns().get("remedy_notice_expected"), (
        "TODO(source): list the letter types that must carry instructions on appeal, each with its source"
    )


def test_bench_templates_with_legal_periods_are_sourced():
    open_templates = []
    for path in sorted(TEMPLATE_DIR.glob("*.yaml")):
        template = yaml.safe_load(path.read_text(encoding="utf-8"))
        if template["rule_family"] != "contract" and not template.get("scam") and not template.get("period_source"):
            if template["letter_type"] != "school_notice":
                open_templates.append(path.name)
    assert not open_templates, f"TODO(source): legal period and appeal wording missing for {open_templates}"


def test_qr_bill_layout_cites_the_implemented_standard():
    assert "TODO(source)" not in (qrbill.__doc__ or ""), "TODO(source): cite the edition of the QR-bill guidelines"


def test_test_iban_range_is_confirmed_unassigned():
    source = Path(content.__file__).read_text(encoding="utf-8")
    assert "TODO(source): confirm that institution id" not in source, "TODO(source): confirm IID 99999 is unassigned"


def test_client_language_strings_are_reviewed_by_native_speakers():
    open_languages = [code for code, meta in i18n.languages().items() if not meta.get("reviewed")]
    assert not open_languages, f"TODO(native-check): unreviewed client-language strings: {open_languages}"
