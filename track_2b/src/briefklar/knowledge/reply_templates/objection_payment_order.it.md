---
id: objection_payment_order
lang: it
title: Opposizione
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
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
