---
id: instalment_request
lang: de
title: Gesuch um Ratenzahlung
applies_to: [tax_assessment, fine, invoice_qr, serafe_invoice, reminder]
required: [debtor_name, debtor_address, office_name, office_address, reference, amount, request_sentence, proposal, date, signature_line]
fixed:
  request_sentence: "Ich kann den Betrag nicht auf einmal bezahlen. Ich bitte Sie deshalb um Ratenzahlung."
free_text: [proposal]
source: "Team-written request letter. No legal wording. Whether instalments are granted is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Ihr Schreiben vom {{ letter_date }}, Referenz {{ reference }}, Betrag {{ amount }}

Sehr geehrte Damen und Herren

{{ request_sentence }}

{{ proposal }}

Bitte teilen Sie mir schriftlich mit, ob Sie einverstanden sind.

Freundliche Grüsse

{{ signature_line }}
