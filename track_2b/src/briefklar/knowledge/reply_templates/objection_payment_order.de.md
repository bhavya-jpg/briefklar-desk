---
id: objection_payment_order
lang: de
title: Rechtsvorschlag
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # The official sheet (points 2-3) prescribes no formula: the objection is declared to the
  # Betreibungsamt orally or in writing within 10 days and needs no reasons. The sentence below only
  # uses the sheet's own term "Rechtsvorschlag erheben" and gives no reasons.
  # TODO(source): have a counsellor or lawyer confirm this wording before real use.
  objection_sentence: "Gegen den Zahlungsbefehl in der oben genannten Betreibung erhebe ich Rechtsvorschlag."
free_text: []
source: https://betreibungsamt.tg.ch/public/upload/assets/92744/Informationsblatt%20zum%20Zahlungsbefehl%20de.pdf
retrieved: 2026-10-11
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Betreibung Nr. {{ enforcement_number }}

{{ objection_sentence }}

Freundliche Grüsse

{{ signature_line }}
