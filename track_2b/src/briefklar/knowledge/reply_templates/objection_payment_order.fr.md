---
id: objection_payment_order
lang: fr
title: Opposition
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  objection_sentence: null   # TODO(source): SOURCE REQUIRED, official French guidance on declaring opposition to a commandement de payer
free_text: []
source: null   # SOURCE REQUIRED
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, le {{ date }}

Poursuite n° {{ enforcement_number }}

{{ objection_sentence }}

Meilleures salutations

{{ signature_line }}
