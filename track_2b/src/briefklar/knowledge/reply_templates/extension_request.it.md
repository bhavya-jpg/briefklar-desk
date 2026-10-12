---
id: extension_request
lang: it
title: Richiesta di proroga del termine
applies_to: [tax_assessment, premium_reduction, fine, permit_renewal, school_notice, invoice_qr, serafe_invoice, reminder, rent_increase, unknown]
required: [debtor_name, debtor_address, office_name, office_address, reference, request_sentence, reason, date, signature_line]
fixed:
  request_sentence: "Vi prego di voler prorogare il termine in questa pratica."
free_text: [reason]
source: "Team-written request letter. No legal wording. Whether an extension is possible is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Vostra lettera del {{ letter_date }}, riferimento {{ reference }}

Gentili signore, egregi signori

{{ request_sentence }}

{{ reason }}

Vi prego di confermarmi il nuovo termine per iscritto.

Distinti saluti

{{ signature_line }}
