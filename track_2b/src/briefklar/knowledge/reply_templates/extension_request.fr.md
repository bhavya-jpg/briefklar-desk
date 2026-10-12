---
id: extension_request
lang: fr
title: Demande de prolongation de délai
applies_to: [tax_assessment, premium_reduction, fine, permit_renewal, school_notice, invoice_qr, serafe_invoice, reminder, rent_increase, unknown]
required: [debtor_name, debtor_address, office_name, office_address, reference, request_sentence, reason, date, signature_line]
fixed:
  request_sentence: "Je vous prie de bien vouloir prolonger le délai dans cette affaire."
free_text: [reason]
source: "Team-written request letter. No legal wording. Whether an extension is possible is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, le {{ date }}

Votre courrier du {{ letter_date }}, référence {{ reference }}

Madame, Monsieur,

{{ request_sentence }}

{{ reason }}

Je vous remercie de me confirmer le nouveau délai par écrit.

Meilleures salutations

{{ signature_line }}
