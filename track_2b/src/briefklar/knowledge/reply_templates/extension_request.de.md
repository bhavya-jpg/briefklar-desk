---
id: extension_request
lang: de
title: Gesuch um Fristverlängerung
applies_to: [tax_assessment, premium_reduction, fine, permit_renewal, school_notice, invoice_qr, serafe_invoice, reminder, rent_increase, unknown]
required: [debtor_name, debtor_address, office_name, office_address, reference, request_sentence, reason, date, signature_line]
fixed:
  request_sentence: "Ich bitte Sie, die Frist in dieser Sache zu verlängern."
free_text: [reason]
source: "Team-written request letter. No legal wording. Whether an extension is possible is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Ihr Schreiben vom {{ letter_date }}, Referenz {{ reference }}

Sehr geehrte Damen und Herren

{{ request_sentence }}

{{ reason }}

Bitte bestätigen Sie mir die neue Frist schriftlich.

Freundliche Grüsse

{{ signature_line }}
