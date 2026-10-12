---
license: cdla-permissive-2.0
language: [de, fr, it]
pretty_name: Swiss Letters Bench v0
task_categories: [image-to-text, visual-question-answering]
tags: [synthetic, switzerland, official-letters, deadlines]
---

# Swiss Letters Bench v0

150 synthetic Swiss official letters in 20 case bundles, with gold labels computed by code. Built for
Briefklar Desk (Hack Apertus 2026, Track 2B) to measure whether a system lets a reader find the right
deadline and the right next step, link letters that belong together, and notice warning signs.

## Why synthetic

Real letters that clients bring to a help desk contain sensitive personal data and cannot be published.
Synthetic letters give exact gold labels and contain no personal data. The next step is a pilot with a
real help desk; this set does not replace it.

## Contents

- `eval/letters.jsonl`: id, type, language, canton, image paths per capture quality, gold facts, gold due
  date, gold next step, gold red flags, gold thread.
- `eval/cases.jsonl`: case id, letter ids, gold urgency order, gold threads, client language.
- `eval/images/<clean|phone|bad>/<id>_p1.jpg`: scanner-like, phone photo, poor phone photo.
- `responses/`: model responses per system. **Empty until the systems have been run against Apertus.**
- `metadata/metadata.jsonl`: per item generator version, seed, template, template source, licence.

## How it was made

- People, addresses, companies, references and amounts are fictional (Faker, fixed seed 7).
- IBANs are checksum-valid test numbers under institution id 99999. Letterheads are text only: no logos,
  coats of arms or signatures. Every page carries the footer
  `SYNTHETIC TEST LETTER · Swiss Letters Bench v0 · not a real document`.
- Letters with warning signs name real authorities as their claimed sender, because that is the threat,
  but carry the same footer and no real visual identity.
- Gold due dates are computed by the product's deadline engine, which is itself checked against 36
  hand-computed cases.

## Limitations

- Templates exist for 13 kinds in German, 5 in French, 3 in Italian. No Romansh, no handwriting.
- Only the payment order carries a sourced legal period (10 days, SchKG). Letters of other types print a
  date only, because their legal appeal periods have not yet been taken from official sample forms.
- Layout variety is low: one page layout, one font.
- Amounts on Serafe letters are synthetic and do not state the real fee.

## Licence

CDLA-Permissive-2.0 for every item (see `metadata/metadata.jsonl`). No personal data.
