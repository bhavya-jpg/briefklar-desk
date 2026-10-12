---
id: objection_payment_order
lang: it
title: Opposizione
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # The official sheet (n. 2-3) prescribes no formula: the debtor declares the opposition to the ufficio
  # d'esecuzione orally or in writing within ten days of notification, and need not give reasons. The
  # sentence below only uses the sheet's own terms "fare opposizione", "precetto esecutivo" and
  # "esecuzione", and gives no reasons.
  # TODO(source): have a counsellor or lawyer confirm this wording before real use.
  objection_sentence: "Faccio opposizione al precetto esecutivo nell'esecuzione sopra indicata."
free_text: []
# "Foglio informativo sul precetto esecutivo", Alta vigilanza in materia di esecuzione e fallimento
# (Ufficio federale di giustizia), 1° marzo 2020, published on the federal Sportello delle esecuzioni.
source: https://www.betreibungsschalter.ch/wp-content/uploads/sites/84/2020/02/Informationsblatt_ZB_it.pdf
retrieved: 2026-10-12
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
