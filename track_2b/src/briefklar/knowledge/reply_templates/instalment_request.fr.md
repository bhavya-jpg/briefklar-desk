---
id: instalment_request
lang: fr
title: Demande de paiement par acomptes
applies_to: [tax_assessment, fine, invoice_qr, serafe_invoice, reminder]
required: [debtor_name, debtor_address, office_name, office_address, reference, amount, request_sentence, proposal, date, signature_line]
fixed:
  request_sentence: "Je ne peux pas payer ce montant en une seule fois. Je vous prie donc de m'accorder un paiement par acomptes."
free_text: [proposal]
source: "Team-written request letter. No legal wording. Whether instalments are granted is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, le {{ date }}

Votre courrier du {{ letter_date }}, référence {{ reference }}, montant {{ amount }}

Madame, Monsieur,

{{ request_sentence }}

{{ proposal }}

Je vous remercie de m'indiquer par écrit si vous êtes d'accord.

Meilleures salutations

{{ signature_line }}
