"""IBAN, QR-bill, reply templates and red-flag checks (spec 17.3)."""

import random
from decimal import Decimal
from pathlib import Path

import pytest

from bench.generator.content import creditor_reference, make_iban
from briefklar.models import LetterFacts, Money
from briefklar.pipeline import reply as reply_pass
from briefklar.tools import authority, scam
from briefklar.tools.iban import validate_iban
from briefklar.tools.qrbill import parse_qr_bill

# -- IBAN ----------------------------------------------------------------------------------------


def test_iban_valid_swiss():
    result = validate_iban("CH93 0076 2011 6238 5295 7")  # the example IBAN from the IBAN standard
    assert result == {"iban": "CH9300762011623852957", "valid": True, "country": "CH", "swiss": True}


def test_iban_valid_foreign():
    result = validate_iban("DE89 3704 0044 0532 0130 00")  # the standard German example
    assert result["valid"] and result["country"] == "DE" and not result["swiss"]


def test_iban_invalid_checksum():
    assert not validate_iban("CH94 0076 2011 6238 5295 7")["valid"]


def test_generated_test_ibans_are_valid():
    rng = random.Random(1)
    for country in ("CH", "LT"):
        assert validate_iban(make_iban(rng, country))["valid"]


# -- QR-bill -------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(10))
def test_qr_bill_round_trip(seed, tmp_path: Path):
    """Generate a bill with the `qrbill` library, read its payload back, compare every field."""
    from qrbill import QRBill

    rng = random.Random(seed)
    iban = make_iban(rng)
    amount = Decimal(rng.randrange(100, 500000)) / 100
    reference = creditor_reference(rng) if seed % 2 else None
    creditor = {"name": f"Testfirma {seed} AG", "street": "Musterweg", "house_num": str(seed + 1), "pcode": "3000",
                "city": "Bern", "country": "CH"}
    debtor = {"name": "Erika Muster", "line1": "Beispielgasse 2", "line2": "8000 Zürich", "country": "CH"}
    bill = QRBill(account=iban, creditor=creditor, debtor=debtor, amount=str(amount), reference_number=reference,
                  additional_information=f"Rechnung {seed}", language="de")
    parsed = parse_qr_bill(bill.qr_data())
    assert parsed["version"] == "0200"
    assert parsed["iban"] == iban
    assert Decimal(parsed["amount"]) == amount
    assert parsed["currency"] == "CHF"
    assert parsed["creditor"]["name"] == creditor["name"]
    assert parsed["creditor"]["postal_code"] == "3000" and parsed["creditor"]["town"] == "Bern"
    assert parsed["creditor"]["country"] == "CH"
    assert parsed["debtor"]["name"] == "Erika Muster"
    assert parsed["reference_type"] == ("SCOR" if reference else "NON")
    assert parsed["reference"] == reference
    assert parsed["message"] == f"Rechnung {seed}"
    assert parsed["trailer"] == "EPD"


def test_qr_bill_rejects_other_payloads():
    with pytest.raises(ValueError):
        parse_qr_bill("https://example.org")


# -- reply templates -----------------------------------------------------------------------------

TEMPLATES = [(t, lang) for t in reply_pass.TEMPLATE_IDS for lang in ("de", "fr", "it")]
COMPLETE = {
    "debtor_name": "Erika Muster", "debtor_address": "Beispielgasse 2\n8000 Zürich", "office_name": "Betreibungsamt Muster",
    "office_address": "8000 Zürich", "enforcement_number": "26123456", "reference": "R-1", "place": "Zürich",
    "date": "10.10.2026", "signature_line": "Erika Muster", "letter_date": "01.10.2026", "amount": "CHF 100.00",
    "reason": "Grund.", "proposal": "Vorschlag.", "objection_sentence": "FIXED", "request_sentence": "FIXED",
}


@pytest.mark.parametrize("template_id,lang", TEMPLATES)
def test_template_renders_every_required_element(template_id, lang):
    template = reply_pass.load_template(template_id, lang)
    text = reply_pass.render_template(template, COMPLETE)
    for slot in template["required"]:
        assert COMPLETE[slot].split("\n")[0] in text, f"{slot} missing from the rendered reply"


@pytest.mark.parametrize("template_id,lang", TEMPLATES)
def test_template_with_missing_slot_raises(template_id, lang):
    template = reply_pass.load_template(template_id, lang)
    slots = {k: v for k, v in COMPLETE.items() if k != "debtor_name"}
    with pytest.raises(reply_pass.MissingSlots):
        reply_pass.render_template(template, slots)


def test_unsourced_fixed_wording_is_never_filled_in():
    template = reply_pass.load_template("objection_payment_order", "fr")
    template = {**template, "fixed": {**template["fixed"], "objection_sentence": None}}   # a slot without an official source
    draft = reply_pass.assemble(template, dict(COMPLETE), {}, [], "letter")
    assert draft.slots["objection_sentence"] == reply_pass.SOURCE_REQUIRED
    assert "objection_sentence" in draft.missing


# -- red-flag checks: one positive and one negative per code ---------------------------------------

DIRECTORY = ({"id": "x_tax", "names": ["Steueramt Musterkanton"], "phone": "+41 31 000 11 22", "web": "steuern.muster.ch",
              "email": "info@steuern.muster.ch", "address": None, "source_url": "https://steuern.muster.ch/kontakt"},)
PATTERNS = {**scam.load_patterns(), "remedy_notice_expected": [{"letter_type": "tax_assessment", "source_url": "test"}]}


def facts(**overrides) -> LetterFacts:
    base = dict(letter_type="tax_assessment", source_language="de", sender_name="Steueramt Musterkanton",
                amount_due=Money(amount=Decimal("120.00")), amounts=[Money(amount=Decimal("120.00"))],
                evidence={"iban": ["e1"], "sender_name": ["e2"]})
    return LetterFacts(**{**base, **overrides})


def codes(letter: LetterFacts, text: str = "Rechtsmittelbelehrung: Einsprache", qr=None, directory=DIRECTORY) -> set[str]:
    entry = authority.lookup_authority(letter.sender_name, directory)
    return {flag.code for flag in scam.run_checks(letter, text, qr=qr, authority=entry, patterns=PATTERNS)}


def test_clean_letter_raises_no_flag():
    assert codes(facts(iban="CH9300762011623852957", sender_contact="Tel. 031 000 11 22, www.steuern.muster.ch")) == set()


def test_sender_not_in_directory():
    assert "SENDER_NOT_IN_DIRECTORY" in codes(facts(sender_name="Kantonales Inkassoamt Nirgendwo"))
    assert "SENDER_NOT_IN_DIRECTORY" not in codes(facts(letter_type="invoice_qr", sender_name="Alpenblick Versand AG"))


def test_contact_mismatch():
    assert "CONTACT_MISMATCH" in codes(facts(sender_contact="Tel. +41 99 555 01 42"))
    assert "CONTACT_MISMATCH" in codes(facts(sender_contact="steuer-muster.example.com"))
    assert "CONTACT_MISMATCH" not in codes(facts(sender_contact="+41 31 000 11 22 · info@steuern.muster.ch"))


def test_foreign_iban_for_authority():
    assert "FOREIGN_IBAN_FOR_AUTHORITY" in codes(facts(iban="LT049999981948219935"))
    assert "FOREIGN_IBAN_FOR_AUTHORITY" not in codes(facts(iban="CH9300762011623852957"))
    private = facts(letter_type="invoice_qr", sender_name="Alpenblick Versand AG", iban="DE89370400440532013000")
    assert "FOREIGN_IBAN_FOR_AUTHORITY" not in codes(private)


def test_qr_mismatch():
    qr = {"iban": "CH9300762011623852957", "amount": "120.00", "currency": "CHF", "creditor": {"name": "Steueramt Musterkanton"}}
    assert "QR_MISMATCH" not in codes(facts(iban="CH9300762011623852957"), qr=qr)
    assert "QR_MISMATCH" in codes(facts(iban="CH9300762011623852957"), qr={**qr, "amount": "920.00"})
    assert "QR_MISMATCH" in codes(facts(iban="CH9300762011623852957"), qr={**qr, "creditor": {"name": "Fremde Firma GmbH"}})


def test_unusual_payment_channel():
    assert "URGENCY_PAYMENT_UNUSUAL_CHANNEL" in codes(facts(demanded_action="Bezahlen Sie mit Paysafecard Guthabenkarten."))
    assert "URGENCY_PAYMENT_UNUSUAL_CHANNEL" not in codes(facts(demanded_action="Bitte überweisen Sie den Betrag."))


def test_legal_basis_inconsistent():
    text = "Gestützt auf die Ventilklausel wird Ihr Aufenthalt beendet. Einsprache möglich."
    flags = scam.run_checks(facts(), text, authority=DIRECTORY[0], patterns=PATTERNS)
    hit = [f for f in flags if f.code == "LEGAL_BASIS_INCONSISTENT"]
    assert hit and hit[0].source_url
    assert "LEGAL_BASIS_INCONSISTENT" not in codes(facts(), "Ihr Aufenthalt wird verlängert. Einsprache möglich.")


def test_no_legal_remedy_notice():
    assert "NO_LEGAL_REMEDY_NOTICE" in codes(facts(), "Bitte bezahlen Sie den Betrag.")
    assert "NO_LEGAL_REMEDY_NOTICE" not in codes(facts(), "Rechtsmittelbelehrung: Einsprache innert der Frist.")
    assert "NO_LEGAL_REMEDY_NOTICE" not in codes(facts(letter_type="school_notice", sender_name="Primarschule Lindenhof"), "Elternabend")


def test_flags_are_evidence_never_a_verdict():
    letter = facts(iban="LT049999981948219935", sender_contact="+41 99 555 01 42",
                   demanded_action="Bezahlen Sie mit Paysafecard.")
    entry = authority.lookup_authority(letter.sender_name, DIRECTORY)
    text = "Gestützt auf die Ventilklausel wird Ihr Aufenthalt beendet."
    for flag in scam.run_checks(letter, text, authority=entry, patterns=PATTERNS):
        assert flag.evidence
        for word in ("fake", "scam", "fraud", "genuine", "real letter", "betrug", "gefälscht"):
            assert word not in flag.evidence.lower()


def test_authority_lookup_threshold():
    assert authority.lookup_authority("Steueramt Musterkanton, Abteilung Bezug", DIRECTORY)["id"] == "x_tax"
    assert authority.lookup_authority("Steueramt Anderswo", DIRECTORY) is None
    assert authority.lookup_authority("Staatssekretariat für Migration SEM")["id"] == "sem"
