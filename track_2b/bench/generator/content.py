"""Synthetic letter content: fictional people and companies, checksum-valid test IBANs, gold facts.

Rules (spec 14.2): nobody and nothing here is real except the names of authorities that letters claim
to come from. Letterheads are text only. The generator never invents a legal period: periods come from
the template YAML, which names its source.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from faker import Faker
from jinja2 import Environment, StrictUndefined
from stdnum.iso7064 import mod_97_10

from briefklar.models import RULE_FAMILY_BY_TYPE
from briefklar.tools.deadline import compute_deadline

TEMPLATE_DIR = Path(__file__).parent / "templates"
GENERATOR_VERSION = "0.1.0"
_env = Environment(undefined=StrictUndefined, autoescape=False)

# TODO(source): confirm that institution id 99999 is not assigned in the SIX bank master, so that these
# checksum-valid test IBANs cannot belong to a real account.
TEST_IID = "99999"
# 99 is not a Swiss area or mobile prefix; used for the made-up phone number on scam letters.
SCAM_PHONE = "+41 99 555 01 42"

MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
           "ottobre", "novembre", "dicembre"],
}
FAKER_LOCALE = {"de": "de_CH", "fr": "fr_CH", "it": "it_CH"}
CANTONS = {"de": ["BE", "ZH"], "fr": ["VD"], "it": ["TI"]}
CAPITAL = {"BE": "3000 Bern", "ZH": "8000 Zürich", "VD": "1000 Lausanne", "TI": "6500 Bellinzona"}
PLACE = {"BE": "Bern", "ZH": "Zürich", "VD": "Lausanne", "TI": "Bellinzona"}

# Names of authorities exactly as listed in knowledge/authorities.yaml.
AUTHORITY = {
    "debt": {"BE": "Betreibungsamt Bern-Mittelland", "ZH": "Betreibungsamt Zürich 4",
             "VD": "Office des poursuites du district de Lausanne", "TI": "Ufficio di esecuzione di Lugano"},
    "tax": {"BE": "Steuerverwaltung des Kantons Bern", "ZH": "Kantonales Steueramt Zürich",
            "VD": "Administration cantonale des impôts", "TI": "Divisione delle contribuzioni"},
    "migration": {"BE": "Amt für Bevölkerungsdienste des Kantons Bern", "ZH": "Migrationsamt des Kantons Zürich"},
    "premium": {"BE": "Amt für Sozialversicherungen des Kantons Bern", "ZH": "SVA Zürich"},
    "police": {"BE": "Kantonspolizei Bern", "ZH": "Kantonspolizei Zürich"},
    "sem": {"de": "Staatssekretariat für Migration SEM", "fr": "Secrétariat d'Etat aux migrations SEM"},
}
# Invented company names.
COMPANIES = {
    "de": [("Alpenblick Versand AG", "Haushaltwaren gemäss Bestellung"),
           ("Morgentau Energie AG", "Stromlieferung für das letzte Quartal"),
           ("Seerose Telecom AG", "Mobilabonnement für drei Monate"),
           ("Lindenhof Dental AG", "Zahnbehandlung gemäss Kostenvoranschlag"),
           ("Tannwald Fitness GmbH", "Jahresabonnement")],
    "fr": [("Lumière du Léman Énergie SA", "fourniture d'électricité du dernier trimestre"),
           ("Télécom Rive-Bleue SA", "abonnement mobile pour trois mois"),
           ("Cabinet dentaire des Tilleuls SA", "traitement dentaire selon devis")],
    "it": [("Energia Valle Verde SA", "fornitura di elettricità dell'ultimo trimestre"),
           ("Telecom Lago Blu SA", "abbonamento mobile per tre mesi"),
           ("Studio dentistico Ai Tigli SA", "trattamento dentistico secondo preventivo")],
}
SCHOOLS = ["Primarschule Lindenhof", "Primarschule Sonnenberg", "Sekundarschule Rebacker"]
LANDLORDS = ["Immobilien Sonnhalde AG", "Wohnbau Rosengarten AG"]


@lru_cache
def load_template(kind: str, lang: str) -> dict | None:
    path = TEMPLATE_DIR / f"{kind}.{lang}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def available_kinds(lang: str) -> list[str]:
    return sorted(p.name.split(".")[0] for p in TEMPLATE_DIR.glob(f"*.{lang}.yaml"))


def date_text(d: date, lang: str) -> str:
    month = MONTHS[lang][d.month - 1]
    if lang == "de":
        return f"{d.day}. {month} {d.year}"
    if lang == "fr":
        return f"{'1er' if d.day == 1 else d.day} {month} {d.year}"
    return f"{'1°' if d.day == 1 else d.day} {month} {d.year}"


def money_text(amount: Decimal) -> str:
    whole, _, cents = f"{amount:.2f}".partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return f"CHF {chr(39).join(groups)}.{cents}"


def make_iban(rng: random.Random, country: str = "CH") -> str:
    if country == "CH":
        bban = TEST_IID + "".join(rng.choice("0123456789") for _ in range(12))
    elif country == "LT":  # used on scam letters only: 5-digit bank code 99999 + 11 digits
        bban = "99999" + "".join(rng.choice("0123456789") for _ in range(11))
    else:
        raise ValueError(country)
    check = mod_97_10.calc_check_digits(bban + country)
    return f"{country}{check}{bban}"


def iban_text(iban: str) -> str:
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


def creditor_reference(rng: random.Random) -> str:
    """ISO 11649 creditor reference (RF..), valid checksum."""
    body = "".join(rng.choice("0123456789") for _ in range(12))
    return f"RF{mod_97_10.calc_check_digits(body + 'RF')}{body}"


def chf(rng: random.Random, low: int, high: int) -> Decimal:
    return Decimal(rng.randrange(low * 20, high * 20)) / 20  # 5-centime steps


@dataclass
class Person:
    name: str
    street: str
    city_line: str

    @property
    def address(self) -> str:
        return f"{self.street}, {self.city_line}"


@dataclass
class Creditor:
    name: str
    service: str
    street: str
    house: str
    pcode: str
    city: str
    iban: str

    @property
    def lines(self) -> list[str]:
        return [f"{self.street} {self.house}", f"{self.pcode} {self.city}"]


@dataclass
class Claim:
    """One unpaid invoice that escalates: invoice, reminders, payment order."""
    creditor: Creditor
    invoice_no: str
    reference: str
    principal: Decimal
    invoice_date: date
    thread_id: str


@dataclass
class LetterSpec:
    id: str
    kind: str
    lang: str
    canton: str
    template: dict
    ctx: dict
    rows: list[dict] = field(default_factory=list)
    qr: dict | None = None
    gold: dict = field(default_factory=dict)
    case_id: str | None = None
    delivered_on: date | None = None


class Generator:
    def __init__(self, seed: int, as_of: date):
        self.rng = random.Random(seed)
        self.as_of = as_of
        self.fakers = {}
        for lang, locale in FAKER_LOCALE.items():
            fake = Faker(locale)
            fake.seed_instance(seed + len(self.fakers))
            self.fakers[lang] = fake

    # -- fictional parties -----------------------------------------------------------------------

    def person(self, lang: str) -> Person:
        fake = self.fakers[lang]
        return Person(f"{fake.first_name()} {fake.last_name()}", f"{fake.street_name()} {self.rng.randint(1, 98)}",
                      f"{fake.postcode()} {fake.city()}")

    def creditor(self, lang: str, index: int | None = None, exclude: set[str] | None = None) -> Creditor:
        fake = self.fakers[lang]
        choices = [c for c in COMPANIES[lang] if c[0] not in (exclude or set())] or COMPANIES[lang]
        name, service = COMPANIES[lang][index] if index is not None else self.rng.choice(choices)
        return Creditor(name, service, fake.street_name(), str(self.rng.randint(1, 98)), fake.postcode(), fake.city(),
                        make_iban(self.rng))

    def claim(self, lang: str, thread_id: str, creditor_index: int | None = None,
              exclude: set[str] | None = None) -> Claim:
        return Claim(
            creditor=self.creditor(lang, creditor_index, exclude),
            invoice_no=f"{self.rng.randint(2026001, 2026999)}-{self.rng.randint(10, 99)}",
            reference=creditor_reference(self.rng),
            principal=chf(self.rng, 180, 2400),
            invoice_date=self.as_of - timedelta(days=self.rng.randint(80, 110)),
            thread_id=thread_id,
        )

    # -- builders: one per template kind ---------------------------------------------------------

    def build(self, kind: str, letter_id: str, lang: str, canton: str, recipient: Person, *,
              claim: Claim | None = None, level: int = 1, letter_date: date | None = None,
              overrides: dict | None = None, exclude: set[str] | None = None) -> LetterSpec:
        template = load_template(kind, lang)
        if template is None:
            raise FileNotFoundError(f"no template {kind}.{lang}")
        rng = self.rng
        letter_date = letter_date or self.as_of - timedelta(days=rng.randint(3, 20))
        due = letter_date + timedelta(days=rng.choice([20, 25, 30]))  # synthetic payment date, not a legal period
        labels = template.get("labels") or {}
        ctx: dict = {"recipient_name": recipient.name, "level": level}
        rows: list[tuple[str, Decimal]] = []
        references: list[str] = []
        sender_lines: list[str]
        qr_creditor: Creditor | None = None
        amount_due: Decimal | None = None
        iban: str | None = None
        creditor_name: str | None = None
        contact: str | None = None
        thread_id: str | None = None

        def authority(group: str) -> tuple[str, list[str]]:
            return AUTHORITY[group][canton], [CAPITAL[canton]]

        if kind in ("invoice_qr", "reminder"):
            claim = claim or self.claim(lang, f"{letter_id}-claim")
            c = claim.creditor
            sender, sender_lines = c.name, c.lines
            thread_id = claim.thread_id
            references = [claim.invoice_no, claim.reference]
            iban = c.iban
            fees = Decimal(20 * level) if kind == "reminder" else Decimal(0)
            amount_due = claim.principal + fees
            rows = [(labels["principal"], claim.principal)]
            if fees:
                rows.append((labels["fees"], fees))
            ctx.update(invoice_no=claim.invoice_no, invoice_date_text=date_text(claim.invoice_date, lang),
                       creditor_ref=claim.reference, service=c.service)
            ref_value = claim.invoice_no
            if kind == "invoice_qr":
                qr_creditor = c
        elif kind in ("payment_order", "continuation_notice"):
            claim = claim or self.claim(lang, f"{letter_id}-claim", exclude=exclude)
            sender, sender_lines = authority("debt")
            thread_id = claim.thread_id
            enforcement_no = f"{rng.randint(20, 26)}{rng.randint(100000, 999999)}"
            references = [enforcement_no, claim.invoice_no, claim.reference] if kind == "payment_order" else [enforcement_no]
            creditor_name = claim.creditor.name
            fees, costs = Decimal(40), chf(rng, 60, 110)
            rows = [(labels["principal"], claim.principal)]
            if "fees" in labels:
                rows.append((labels["fees"], fees))
            else:
                fees = Decimal(0)
            rows.append((labels["costs"], costs))
            amount_due = claim.principal + fees + costs
            ctx.update(creditor_name=claim.creditor.name, creditor_city=claim.creditor.city,
                       invoice_no=claim.invoice_no, invoice_date_text=date_text(claim.invoice_date, lang),
                       creditor_ref=claim.reference)
            ref_value = enforcement_no
            if kind == "continuation_notice":
                due = letter_date + timedelta(days=rng.randint(12, 20))
        elif kind == "serafe_invoice":
            sender, sender_lines = "Serafe AG", ["Postfach"]
            c = Creditor("Serafe AG", "", "Postfach", "", "8000", "Zürich", make_iban(rng))
            qr_creditor, iban = c, c.iban
            amount_due = chf(rng, 80, 340)
            rows = [(labels["principal"], amount_due)]
            ref_value = f"{rng.randint(100000000, 999999999)}"
            references = [ref_value]
            start = date(letter_date.year, letter_date.month, 1)
            ctx["period_text"] = f"{date_text(start, lang)} – {date_text(start + timedelta(days=364), lang)}"
        elif kind == "tax_assessment":
            sender, sender_lines = authority("tax")
            iban = make_iban(rng)
            owed, paid = chf(rng, 1800, 9000), chf(rng, 200, 1500)
            amount_due = owed - paid
            rows = [(labels["principal"], owed), (labels["paid"], paid)]
            ref_value = f"{rng.randint(100, 999)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}"
            references = [ref_value]
            ctx["tax_year"] = letter_date.year - 1
        elif kind == "premium_reduction":
            sender, sender_lines = authority("premium")
            monthly = chf(rng, 60, 260)
            ref_value = f"PV-{rng.randint(100000, 999999)}"
            references = [ref_value]
            ctx.update(year=letter_date.year + 1, monthly_text=money_text(monthly))
            rows = []
            ctx["_amounts"] = [monthly]
        elif kind == "fine":
            sender, sender_lines = authority("police")
            iban = make_iban(rng)
            amount_due = Decimal(rng.choice([40, 60, 100, 120]))
            rows = [(labels["principal"], amount_due)]
            ref_value = f"{rng.randint(10000000, 99999999)}"
            references = [ref_value]
            ctx.update(offence_date_text=date_text(letter_date - timedelta(days=rng.randint(4, 12)), lang),
                       plate=f"{canton} {rng.randint(100000, 999999)}",
                       offence=rng.choice(["Überschreiten der zulässigen Parkzeit", "Parkieren ausserhalb eines Parkfeldes"]))
        elif kind == "rent_increase":
            fake = self.fakers[lang]
            sender, sender_lines = rng.choice(LANDLORDS), [f"{fake.street_name()} {rng.randint(1, 98)}", f"{fake.postcode()} {fake.city()}"]
            old = chf(rng, 1100, 2100)
            new = old + chf(rng, 30, 140)
            ref_value = f"MV-{rng.randint(10000, 99999)}"
            references = [ref_value]
            ctx.update(flat=f"{rng.randint(2, 5)}.5-Zimmer-Wohnung, {recipient.street}", old_rent_text=money_text(old),
                       new_rent_text=money_text(new), effective_text=date_text(letter_date + timedelta(days=110), lang),
                       reason="Anpassung an den Referenzzinssatz", _amounts=[old, new])
        elif kind == "permit_renewal":
            sender, sender_lines = authority("migration")
            ref_value = f"{rng.randint(10000000, 99999999)}"
            references = [ref_value]
            ctx.update(permit=rng.choice(["B", "L"]), expiry_text=date_text(due + timedelta(days=30), lang))
        elif kind == "school_notice":
            sender, sender_lines = rng.choice(SCHOOLS), [recipient.city_line]
            ref_value = None
            ctx.update(klass=f"{rng.randint(1, 6)}{rng.choice('abc')}", event_text=date_text(due + timedelta(days=7), lang))
            due = letter_date + timedelta(days=rng.randint(8, 14))
        elif kind == "scam_sem":
            sender, sender_lines = AUTHORITY["sem"][lang], ["3003 Bern-Wabern"]
            iban = make_iban(rng, "LT")
            amount_due = chf(rng, 280, 780)
            rows = [(labels["principal"], amount_due)]
            ref_value = f"SEM-{rng.randint(10000, 99999)}-{rng.choice('ABCDEFG')}"
            references = [ref_value]
            contact = SCAM_PHONE
            ctx["phone"] = SCAM_PHONE
            due = letter_date + timedelta(days=rng.randint(3, 5))
        elif kind == "scam_tax":
            sender, sender_lines = authority("tax")
            amount_due = chf(rng, 90, 240)
            rows = [(labels["principal"], amount_due)]
            ref_value = f"RE-{rng.randint(100000, 999999)}"
            references = [ref_value]
            ctx.update(tax_year=letter_date.year - 1, refund_text=money_text(chf(rng, 900, 2600)))
            due = letter_date + timedelta(days=rng.randint(3, 6))
        else:
            raise ValueError(f"no builder for {kind}")

        for key, value in (overrides or {}).items():  # demo case pins a few values
            if key == "amount_rows":
                rows = [(labels[name], Decimal(amount)) for name, amount in value]
                amount_due = sum((-Decimal(a) if name == "paid" else Decimal(a)) for name, a in value)
            elif key == "due":
                due = value
            elif key == "references":
                references = value
                ref_value = value[0]

        extra_amounts = ctx.pop("_amounts", [])
        ctx.update(
            amount_text=money_text(amount_due) if amount_due is not None else "",
            iban_text=iban_text(iban) if iban else "",
            due_date_text=date_text(due, lang),
        )
        render = lambda text: _env.from_string(text).render(**ctx).strip()  # noqa: E731
        title = render(template["title"])
        demand = render(template["demand"]) if template.get("demand") else None
        deadline = render(template["deadline"]) if template.get("deadline") else None
        intro = [p for p in (render(t) for t in template.get("intro") or []) if p]
        closing = [p for p in (render(t) for t in template.get("closing") or []) if p]
        options = {key: render(text) for key, text in (template.get("options") or {}).items()}
        body = [p for p in [demand, deadline, *closing] if p]
        table = [{"label": label, "amount": money_text(amount), "total": False} for label, amount in rows]
        if rows and "total" in labels and amount_due is not None:
            table.append({"label": labels["total"], "amount": money_text(amount_due), "total": True})
        ref_line = f"{template['ref_label']} {ref_value}" if template.get("ref_label") and ref_value else None

        full_text = "\n".join([title, ref_line or "", *intro, *body])
        for key, phrase in options.items():
            assert phrase in full_text, f"{kind}.{lang}: option {key!r} is not printed on the letter"

        page = {
            "lang": lang, "letter_id": letter_id, "sender_name": sender, "sender_lines": sender_lines,
            "recipient_name": recipient.name, "recipient_lines": [recipient.street, recipient.city_line],
            "place": PLACE[canton], "letter_date_text": date_text(letter_date, lang), "title": title,
            "ref_line": ref_line, "intro": intro, "rows": table, "body": body, "greeting": template.get("greeting"),
        }
        qr = None
        if template.get("qr") and qr_creditor is not None and amount_due is not None:
            qr = {"account": qr_creditor.iban, "amount": amount_due, "language": lang,
                  "creditor": {"name": qr_creditor.name, "pcode": qr_creditor.pcode, "city": qr_creditor.city,
                               "street": qr_creditor.street, "house_num": qr_creditor.house, "country": "CH"},
                  "debtor": {"name": recipient.name, "line1": recipient.street, "line2": recipient.city_line,
                             "country": "CH"},
                  "reference": claim.reference if kind == "invoice_qr" and claim else None,
                  "message": title}

        period = template.get("period")
        start_event = period["start_event"] if period else ("fixed_date" if deadline else None)
        evidence_phrases: list[tuple[str, str]] = [("letter_type", title), ("sender_name", sender),
                                                   ("recipient_name", recipient.name),
                                                   ("recipient_address", recipient.street),
                                                   ("letter_date", page["letter_date_text"])]
        if sender_lines:
            evidence_phrases.append(("sender_address", sender_lines[-1]))
        if creditor_name:
            evidence_phrases.append(("creditor_name", creditor_name))
        evidence_phrases += [("reference_numbers", r) for r in references]
        if amount_due is not None:
            evidence_phrases.append(("amount_due", money_text(amount_due)))
        if iban:
            evidence_phrases.append(("iban", iban_text(iban)))
        if contact:
            evidence_phrases.append(("sender_contact", contact))
        if demand:
            evidence_phrases.append(("demanded_action", demand))
        if deadline:
            evidence_phrases.append(("deadline_text", deadline))
        evidence_phrases += [("stated_options", phrase) for phrase in options.values()]
        items, evidence = [], {}
        for field_name, phrase in evidence_phrases:
            existing = next((i for i in items if i["text"] == phrase), None)
            if existing is None:
                existing = {"id": f"e{len(items) + 1}", "text": phrase, "page": 0, "bbox": None}
                items.append(existing)
            evidence.setdefault(field_name, []).append(existing["id"])

        amounts = [amount for _, amount in rows] + extra_amounts
        if amount_due is not None and amount_due not in amounts:
            amounts.append(amount_due)
        letter_type = template["letter_type"]
        facts = {
            "letter_type": letter_type, "source_language": lang, "sender_name": sender,
            "sender_address": ", ".join(sender_lines) or None, "sender_contact": contact,
            "recipient_name": recipient.name, "recipient_address": recipient.address,
            "creditor_name": creditor_name, "letter_date": letter_date.isoformat(),
            "reference_numbers": references,
            "amounts": [{"amount": f"{a:.2f}", "currency": "CHF"} for a in amounts],
            "amount_due": {"amount": f"{amount_due:.2f}", "currency": "CHF"} if amount_due is not None else None,
            "iban": iban, "demanded_action": demand, "deadline_text": deadline,
            "deadline_period_value": period["value"] if period else None,
            "deadline_period_unit": period["unit"] if period else None,
            "deadline_start_event": start_event,
            "deadline_fixed_date": due.isoformat() if start_event == "fixed_date" else None,
            "stated_options": list(options.values()), "evidence": evidence, "evidence_items": items,
        }
        delivered = letter_date + timedelta(days=rng.randint(1, 3))
        gold = {
            "facts": facts, "option_keys": list(options), "gold_next_step": template["next_step"],
            "gold_red_flags": template.get("red_flags", []), "gold_scam": bool(template.get("scam")),
            "gold_thread_id": thread_id, "template": f"{kind}.{lang}", "template_source": template.get("source"),
            "period_source": template.get("period_source"), "rule_family": RULE_FAMILY_BY_TYPE[letter_type],
        }
        return LetterSpec(id=letter_id, kind=kind, lang=lang, canton=canton, template=template, ctx=page, qr=qr,
                          gold=gold, delivered_on=delivered)


def gold_due_date(spec: LetterSpec, today: date) -> str | None:
    """Computed by the same engine the product uses; tests/data/deadline_cases.csv checks the engine by hand."""
    facts = spec.gold["facts"]
    event = facts["deadline_start_event"]
    if event is None:
        return None
    start = {"delivery": spec.delivered_on,
             "letter_date": date.fromisoformat(facts["letter_date"]),
             "fixed_date": date.fromisoformat(facts["deadline_fixed_date"]) if facts["deadline_fixed_date"] else None}[event]
    result = compute_deadline(spec.gold["rule_family"], facts["deadline_period_value"], facts["deadline_period_unit"],
                              event, start, spec.canton, today=today)
    return result.due_date.isoformat() if result.due_date else None
