---
id: instalment_request
lang: it
title: Richiesta di pagamento rateale
applies_to: [tax_assessment, fine, invoice_qr, serafe_invoice, reminder]
required: [debtor_name, debtor_address, office_name, office_address, reference, amount, request_sentence, proposal, date, signature_line]
fixed:
  request_sentence: "Non posso pagare l'importo in una sola volta. Vi prego quindi di concedermi un pagamento rateale."
free_text: [proposal]
source: "Team-written request letter. No legal wording. Whether instalments are granted is decided by the recipient."
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Vostra lettera del {{ letter_date }}, riferimento {{ reference }}, importo {{ amount }}

Gentili signore, egregi signori

{{ request_sentence }}

{{ proposal }}

Vi prego di comunicarmi per iscritto se siete d'accordo.

Distinti saluti

{{ signature_line }}
