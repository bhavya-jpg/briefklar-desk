---
id: objection_payment_order
lang: it
title: Opposizione
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # Checked 2026-10-12: the federal sheet (betreibungsschalter.ch, Informationsblatt_ZB_it.pdf, ch. 2-3) only says that the
  # opposition is declared orally or in writing and needs no reasons. It gives no sentence, so none is filled in.
  objection_sentence: null   # TODO(source): SOURCE REQUIRED, official Italian guidance on declaring opposizione to a precetto esecutivo
free_text: []
source: null   # SOURCE REQUIRED
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Esecuzione n. {{ enforcement_number }}

{{ objection_sentence }}

Distinti saluti

{{ signature_line }}
