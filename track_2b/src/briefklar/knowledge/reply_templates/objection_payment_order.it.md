---
id: objection_payment_order
lang: it
title: Opposizione
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # No official sheet prescribes a formula (checked 2026-10-12). Federal sheet "Foglio informativo sul precetto esecutivo"
  # (n. 2-3): opposition is declared orally or in writing within ten days, no reasons needed. ti.ch, Sezione di esecuzione e
  # fallimento, FAQ: "Come devo comportarmi se ricevo un precetto ingiusto? Faccio opposizione." and "Posso fare opposizione
  # al precetto ... entro 10 giorni dalla notifica". The sentence below only uses those terms and gives no reasons.
  # TODO(source): have a counsellor or lawyer confirm this wording before real use.
  objection_sentence: "Faccio opposizione al precetto esecutivo nell'esecuzione sopra indicata."
free_text: []
# ti.ch FAQ and the federal sheet ("Foglio informativo sul precetto esecutivo", Alta vigilanza in materia di esecuzione e
# fallimento, 1° marzo 2020).
source: https://www4.ti.ch/index.php?id=21937
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
