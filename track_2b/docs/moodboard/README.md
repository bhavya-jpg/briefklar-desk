# Moodboard: Awwwards references

The design owner runs the protocol in spec 13.2: visit each reference, save one screenshot here, and
confirm or replace the three lines below. **No screenshots have been saved yet and the references have
not been visited for this build**; the notes are the starting list from the spec (13.3), written as what we
intend to borrow. We borrow principles only: never assets, layouts or brand elements.

| Reference | Register | What we borrow | Where we apply it | What we do not borrow |
| --- | --- | --- | --- | --- |
| twks (twks.ch) | Tool + Showcase | Type-led hierarchy: one display size, one body size, little in between | Case board and letter view headings; landing hero | Agency tone, bilingual switcher pattern |
| Odyssée Clinic | Tool | Calm warm off-white ground, short spaced statements | `--bk-paper` ground, explanation cards with one idea each | Imagery, numbered section chrome |
| Golden Suisse composition | Tool, Showcase | Black-and-white typographic composition | Days-left numerals, landing "three numbers" | Decorative type effects |
| LPAS | Showcase | Interaction pacing | Landing reveal timing | Any 3D or pointer-driven motion |
| Maria Vasilyeva portfolio | Showcase | Typographic rhythm | Landing section headings | Portfolio layout |
| Opal Tadpole | Showcase | One idea per screen, revealed on scroll | Landing "10 / 13 / 0" section | Product-shot treatment |
| Messenger (abeto) | Showcase | One memorable idea, told at a steady pace | Demo video structure | Game-like interaction |
| Lando Norris (OFF+BRAND) | Video only | Confident transitions | Video cuts | Everything inside the tool |

Rules that came out of the board and are enforced in code:

- Two registers, never mixed: no WebGL, parallax or decorative motion inside the tool.
- One accent (teal). Amber means "check", red means warning signs only.
- Never imitate a government identity: no Swiss cross, no federal red, no federal typeface, no coats of arms.
- Tokens are locked in `frontend/src/lib/design/tokens.css`; contrast is tested in `tests/test_contrast.py`.

## Design review (spec 13.9)

Each screen is scored 1 to 10 by two reviewers on Design (40%), Usability (30%), Creativity (20%) and
Content (10%); merge at a weighted score of 8 or more. **Not done yet for this build.**
