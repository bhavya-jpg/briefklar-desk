---
id: objection_payment_order
lang: fr
title: Opposition
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # The official sheet (ch. 2-3) prescribes no formula: the debtor declares the opposition to the office
  # des poursuites orally or in writing within ten days of notification, and need not give reasons. The
  # sentence below only uses the sheet's own terms "former opposition", "commandement de payer" and
  # "poursuite", and gives no reasons.
  # TODO(source): have a counsellor or lawyer confirm this wording before real use.
  objection_sentence: "Je forme opposition au commandement de payer dans la poursuite mentionnée ci-dessus."
free_text: []
# "Fiche d'information sur le commandement de payer", Service Haute surveillance LP (Office fédéral de la
# justice), 1er mars 2020, published on the federal Portail des poursuites.
source: https://www.betreibungsschalter.ch/wp-content/uploads/sites/84/2020/02/Informationsblatt_ZB_fr.pdf
retrieved: 2026-10-12
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
