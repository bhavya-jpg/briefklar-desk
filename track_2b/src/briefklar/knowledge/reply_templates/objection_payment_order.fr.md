---
id: objection_payment_order
lang: fr
title: Opposition
applies_to: [payment_order]
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
fixed:
  # No official sheet prescribes a formula (checked 2026-10-12). Federal sheet "Fiche d'information sur le commandement de
  # payer" (ch. 2-3): opposition is declared orally or in writing within ten days, no reasons needed. vd.ch, "Vous êtes
  # poursuivi (débiteur)": "former opposition au commandement de payer", by letter to the office, "en indiquant clairement
  # à quelle poursuite est faite l'opposition" (the "Poursuite n°" line above the sentence does that). The sentence below
  # only uses those terms and gives no reasons.
  # TODO(source): have a counsellor or lawyer confirm this wording before real use.
  objection_sentence: "Je forme opposition au commandement de payer dans la poursuite mentionnée ci-dessus."
free_text: []
# vd.ch page and the federal sheet it links ("Fiche d'information sur le commandement de payer", Service Haute surveillance LP,
# 1er mars 2020).
source: https://www.vd.ch/economie/poursuites-et-faillites/procedure-de-poursuite-ordinaire/vous-etes-poursuivi-debiteur
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
