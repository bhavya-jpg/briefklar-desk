"""Case pass: thread linking and urgency order (spec section 8.5).

The model proposes threads and an order. A deterministic linker confirms each link; the final order is
deterministic. Model reasons are kept as tooltips only.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from itertools import combinations

from pydantic import BaseModel
from rapidfuzz import fuzz

from briefklar.llm import prompts
from briefklar.llm.client import LLMClient
from briefklar.models import Case, Letter, Thread
from briefklar.tools.authority import normalise
from briefklar.tools.iban import compact

SAME_NAME_THRESHOLD = 90
AMOUNT_TOLERANCE = Decimal("0.20")  # "same amount ± fees within 20%"


class ProposedThread(BaseModel):
    letter_ids: list[str]
    reason: str


class OrderItem(BaseModel):
    letter_id: str
    reason: str


class CaseProposal(BaseModel):
    threads: list[ProposedThread] = []
    order: list[OrderItem] = []


def compact_letter(letter: Letter, ref: str) -> dict:
    facts, verification = letter.facts, letter.verification
    assert facts is not None and verification is not None
    deadline = verification.deadline
    return {
        "id": ref,
        "type": facts.letter_type,
        "sender": facts.sender_name,
        "creditor": facts.creditor_name,
        "reference_numbers": facts.reference_numbers,
        "iban": facts.iban,
        "amount_due": f"{facts.amount_due.amount:.2f}" if facts.amount_due else None,
        "letter_date": facts.letter_date.isoformat() if facts.letter_date else None,
        "due_date": deadline.due_date.isoformat() if deadline and deadline.due_date else None,
        "needs_delivery_date": bool(deadline and deadline.needs_delivery_date),
        "red_flags": [flag.code for flag in verification.red_flags],
    }


def done_letters(case: Case) -> list[Letter]:
    return [l for l in case.letters if l.status == "done" and l.facts and l.verification]


def propose(client: LLMClient, case: Case) -> CaseProposal:
    """Ask the model. Letters are named L1..Ln so the request does not depend on random session ids."""
    letters = done_letters(case)
    refs = {f"L{i + 1}": letter.id for i, letter in enumerate(letters)}
    schema = json.dumps(CaseProposal.model_json_schema(), ensure_ascii=False, sort_keys=True)
    payload = [compact_letter(letter, ref) for ref, letter in zip(refs, letters)]
    proposal = client.chat_json(
        [{"role": "system", "content": f"{prompts.load('case')}\n\nJSON schema:\n{schema}"},
         {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}],
        CaseProposal, pass_name="case", letter_id=case.id, label="the case pass",
    )
    return CaseProposal(
        threads=[
            ProposedThread(letter_ids=[refs[r] for r in t.letter_ids if r in refs], reason=t.reason)
            for t in proposal.threads
        ],
        order=[OrderItem(letter_id=refs[o.letter_id], reason=o.reason) for o in proposal.order if o.letter_id in refs],
    )


# -- deterministic linker ------------------------------------------------------------------------


def _refs(letter: Letter) -> set[str]:
    return {re.sub(r"[^A-Z0-9]", "", r.upper()) for r in letter.facts.reference_numbers if len(r.strip()) >= 5}


def _same_name(a: str | None, b: str | None) -> bool:
    return bool(a and b) and fuzz.token_sort_ratio(normalise(a), normalise(b)) >= SAME_NAME_THRESHOLD


def _amount_close(a: Letter, b: Letter) -> bool:
    x, y = a.facts.amount_due, b.facts.amount_due
    if not x or not y or x.currency != y.currency:
        return False
    low, high = sorted((x.amount, y.amount))
    return low > 0 and (high - low) <= AMOUNT_TOLERANCE * low


def link_reason(a: Letter, b: Letter) -> str | None:
    """Why two letters belong to the same matter, or None. Any one condition is enough (spec 8.5).

    Refinement of the spec: reference numbers that contradict each other veto the two fuzzy conditions.
    Otherwise two separate invoices from one creditor would be merged into one matter.
    """
    fa, fb = a.facts, b.facts
    refs_a, refs_b = _refs(a), _refs(b)
    shared = refs_a & refs_b
    if shared:
        return f"same reference number ({sorted(shared)[0]})"
    if fa.iban and fb.iban and compact(fa.iban) == compact(fb.iban):
        return "same creditor IBAN"
    if _same_name(fa.sender_name, fb.sender_name) and _amount_close(a, b) and not (refs_a and refs_b):
        return "same sender and the same amount (± fees)"
    for order, other in ((a, b), (b, a)):
        if order.facts.letter_type == "payment_order" and other.facts.letter_type == "reminder":
            # a payment order that names the claim (a reference besides its own number) must match it
            names_other_claim = len(_refs(order)) >= 2 and bool(_refs(other))
            if _same_name(order.facts.creditor_name, other.facts.sender_name) and not names_other_claim:
                return "payment order for the creditor who sent the reminder"
    return None


def linker_groups(letters: list[Letter]) -> list[tuple[list[str], str]]:
    parent = {l.id: l.id for l in letters}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    reasons: dict[str, list[str]] = defaultdict(list)
    pair_reasons = []
    for a, b in combinations(letters, 2):
        if a.verification.red_flags or b.verification.red_flags:
            continue  # a letter with warning signs is never merged into a real matter automatically
        reason = link_reason(a, b)
        if reason:
            parent[find(a.id)] = find(b.id)
            pair_reasons.append((a.id, reason))
    for letter_id, reason in pair_reasons:
        if reason not in reasons[find(letter_id)]:
            reasons[find(letter_id)].append(reason)
    groups: dict[str, list[str]] = defaultdict(list)
    for letter in letters:
        groups[find(letter.id)].append(letter.id)
    return [(ids, "; ".join(reasons[root])) for root, ids in groups.items() if len(ids) > 1]


def build_threads(letters: list[Letter], proposal: CaseProposal) -> tuple[list[Thread], int]:
    """Combine model proposals with the linker. Returns (threads, model_misses)."""
    threads: list[Thread] = []
    misses = 0
    confirmed_sets = []
    known = {l.id for l in letters}
    proposed = [set(t.letter_ids) & known for t in proposal.threads]
    for ids, reason in linker_groups(letters):
        group = set(ids)
        confirmed_sets.append(group)
        seen_by_model = any(len(p & group) >= 2 for p in proposed)
        if not seen_by_model:
            misses += 1
        threads.append(Thread(id=f"t{len(threads) + 1}", letter_ids=ids, reason=reason, confirmed=True,
                              origin="both" if seen_by_model else "linker"))
    for candidate, original in zip(proposed, proposal.threads):
        if len(candidate) < 2 or any(candidate <= group for group in confirmed_sets):
            continue
        ordered = [l.id for l in letters if l.id in candidate]
        threads.append(Thread(id=f"t{len(threads) + 1}", letter_ids=ordered, reason=original.reason,
                              confirmed=False, origin="model"))
    return threads, misses


# -- deterministic order -------------------------------------------------------------------------


def urgency_key(letter: Letter) -> tuple:
    """(1) red-flagged first, (2) days left ascending, (3) needs a delivery date, (4) no deadline."""
    verification = letter.verification
    deadline = verification.deadline if verification else None
    if deadline and deadline.due_date:
        bucket, when = 0, deadline.due_date.toordinal()
    elif deadline and deadline.needs_delivery_date:
        bucket, when = 1, 0
    else:
        bucket, when = 2, 0
    flagged = 0 if verification and verification.red_flags else 1
    return (flagged, bucket, when)


def thread_heads(case: Case) -> dict[str, str]:
    """letter id -> id of the most recent letter of its confirmed thread (the one that counts now)."""
    index = {l.id: i for i, l in enumerate(case.letters)}
    by_id = {l.id: l for l in case.letters if l.status == "done" and l.facts}
    heads: dict[str, str] = {}
    for thread in case.threads:
        members = [by_id[i] for i in thread.letter_ids if i in by_id]
        if not thread.confirmed or thread.rejected or len(members) < 2:
            continue
        head = max(members, key=lambda l: (l.facts.letter_date or date.min, index[l.id]))
        for member in members:
            heads[member.id] = head.id
    return heads


def order_letters(case: Case) -> list[str]:
    """Deterministic urgency order (spec 8.5), refined for threads: a matter is ranked by its most recent
    letter, and the older letters of the same confirmed thread follow it directly, newest first.
    Without this, a reminder that has since become a payment order would outrank the payment order."""
    index = {l.id: i for i, l in enumerate(case.letters)}
    by_id = {l.id: l for l in case.letters}
    heads = thread_heads(case)

    def key(letter: Letter) -> tuple:
        head = by_id[heads.get(letter.id, letter.id)]
        age = -(letter.facts.letter_date or date.min).toordinal() if letter.facts else 0
        return (*urgency_key(head), index[head.id], 0 if head is letter else 1, age, index[letter.id])

    ranked = sorted((l for l in case.letters if l.status == "done"), key=key)
    return [l.id for l in ranked] + [l.id for l in case.letters if l.status != "done"]


def run_case_pass(client: LLMClient, case: Case) -> None:
    letters = done_letters(case)
    proposal = propose(client, case) if len(letters) >= 2 else CaseProposal()
    kept = {tuple(sorted(t.letter_ids)): t for t in case.threads if t.origin == "counsellor" or t.rejected}
    threads, case.model_misses = build_threads(letters, proposal)
    for thread in threads:  # keep decisions the counsellor already made
        previous = kept.get(tuple(sorted(thread.letter_ids)))
        if previous:
            thread.confirmed, thread.rejected, thread.origin = previous.confirmed, previous.rejected, previous.origin
    case.threads = threads
    reasons = {item.letter_id: item.reason for item in proposal.order}
    for letter in case.letters:
        letter.priority_reason = reasons.get(letter.id)
    case.order = order_letters(case)
