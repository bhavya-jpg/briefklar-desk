# Briefklar Desk — Build Specification

**Hack Apertus 2026 · Online Hackathon · Track 2B (Own Project)**
Spec version 1.0 · 11 Oct 2026 · Submission deadline **16 Oct 2026, 12:00 CEST (15:30 IST)**, via http://hackapertus.ch/online-hack/submissions (not Devpost)

> **One line:** Briefklar Desk turns the pile of Swiss official letters a client brings to a help desk into a deadline-ordered case plan, red-flag warnings, ready-to-sign replies, and an explanation in the client's own language. It runs on Apertus 1.5 8B on the help desk's own hardware, with no network at runtime.

---

## 0. How to use this file

This is the single source of truth for building the project. It is written so that a human team **or an AI coding assistant** can build from it section by section.

**Instructions for an AI coding assistant working from this file**

1. Build in the order of section 21 (day plan). Never start the UI before `make run` works end to end in replay mode (section 16).
2. Treat every item marked **MUST** as an acceptance criterion. Write the test first where a test is specified.
3. Never invent legal rules, deadlines, phone numbers, addresses or authority data. Where this spec says `SOURCE REQUIRED`, leave a clearly failing placeholder and a `TODO(source)` comment, so a human fills it from an official source.
4. All model calls go through one client module (`src/briefklar/llm/client.py`) that reads `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`, and supports replay mode.
5. Nothing at runtime may make a network request other than to `LLM_BASE_URL`. No CDN fonts, no analytics, no telemetry. A test enforces this (section 17).
6. Every UI decision must pass the design checklist in section 13.9 before merge.

**Glossary**

| Term | Meaning |
| --- | --- |
| Help desk | Schreibdienst, social service, debt-advice centre, integration office or NGO that helps residents with official mail |
| Counsellor | The trained staff member or volunteer using Briefklar |
| Client | The resident whose letters are processed |
| Case | All letters one client brings in one session |
| Thread | Letters in one case that belong together (e.g. reminder 1 → reminder 2 → payment order) |
| Zahlungsbefehl | Payment order in Swiss debt enforcement (SchKG) |
| Rechtsvorschlag | Objection to a payment order |
| SchKG | Swiss Federal Act on Debt Enforcement and Bankruptcy |

---

## 1. Product summary

### 1.1 Problem

- People bring help desks a bag of official letters they cannot read well. Zürich's Schreibdienst alone helps about 3,000 people a year.
- Some letters carry short, hard deadlines. A payment order must be opposed within **10 days** of delivery, or the creditor can continue to seizure or bankruptcy.
- Fake authority letters circulate. Fake SEM (State Secretariat for Migration) letters with letterhead, QR code and personnel number told foreign residents their residence would end and deportation would follow; SEM confirmed they were fake.
- Help-desk staff may not use public AI tools on this data. Basel-Stadt's AI directive forbids entering personal data or data under official secrecy into ChatGPT, Copilot, Gemini or DeepL.
- Consumer apps (Google Lens, Gemini, ChatGPT, Totoy, BriefEasy and others) explain one letter at a time, in the cloud, for an individual. None serves the help desk.

### 1.2 Solution

A web app that runs on one machine in the help desk (or on a canton's internal AI platform). The counsellor photographs every letter the client brought. Briefklar:

1. Reads each letter from the image (Apertus 1.5 vision), cross-checked with OCR.
2. Computes every deadline with deterministic Swiss rules (code, not the model).
3. Links letters into threads and orders the whole case by urgency.
4. Flags suspicious letters with specific, evidenced red flags.
5. Drafts replies (objection, extension request, instalment request) in formal DE/FR/IT from vetted templates.
6. Explains each letter and the whole case to the client in their language, with a simple-German twin for the counsellor.
7. Prints a one-page handout for the client and a German case note for the office file, then wipes the session.

### 1.3 Why it wins Track 2B (map every artefact to this)

| Judging criterion (0–5 each) | Our evidence |
| --- | --- |
| Purposeful use of AI | Vision, multilingual generation and tool calling are each necessary; deterministic code does what code does better (dates, checksums) |
| Technical rigour | Swiss Letters Bench: 150 synthetic letters + 20 case bundles, code-computed gold, 4 baselines incl. translation-only, 20% human-checked judge |
| Value, cost & scalability | One GPU per office or one shared instance per canton; measured seconds and CHF per case; no per-seat fees |
| Sovereign deployability | Air-gapped by default; weights baked in at build time; same image runs on-prem or on a Swiss cloud endpoint |
| Implementation feasibility | Small pipeline, `make run` in Docker, replay mode for judges without a GPU |

---

## 2. Hard constraints from the hackathon (do not violate)

| Constraint | Source | How we comply |
| --- | --- | --- |
| Project must be new, started within 1–16 Oct 2026 | Track 2B README | Fresh repo from the template; all commits in the window |
| Must be built with Apertus; other open-weight models only in support roles, declared in report | Track 2B README | All product inference uses Apertus 1.5 8B; Apertus 70B as judge; Tesseract is OCR, not a model substitute |
| Deployable a) on-prem, b) air-gapped, or c) sovereign Swiss cloud | Track 2B README | Primary: (b). Also (a) and (c) |
| Repo from `HackApertus/project-template`, work only in `track_2b/`, don't rename, delete other track folders, repo **PUBLIC** | Track 2B README | Section 6 |
| `make run` from repo root, in Docker, works on a clean checkout, end to end | Track 2B README | Section 16 |
| Env vars `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY` | Template root README | Section 7 |
| `data/` ≤ 100 MB | Track 2B README | Bench images at reduced resolution; full set on Hugging Face |
| Technical report: `technical_report.md` + `TeamName_Report.pdf`, max 6 pages | Track 2B README | Section 19 |
| Demo video max 2 minutes | Track 2B README | Section 20 (1:55) |
| Optional dataset on HF from `HackApertus/online_hack_template`: eval set, model responses, metadata with per-item licences; PUBLIC | Track 2B README | Section 14.6 |
| Open source per T&C section 6 (hackapertus.ch/terms-and-conditions) | Template README | Code Apache-2.0, dataset CDLA-Permissive-2.0, report CC-BY-4.0; **read T&C section 6 before submitting** |

---

## 3. Users and scope

### 3.1 Personas

- **Counsellor (primary user):** e.g. a social worker or trained volunteer. Reads German well, works under time pressure, accountable for what goes out. Needs speed, traceability, and confidence the tool is allowed.
- **Client (beneficiary):** resident with limited German/French/Italian, often stressed, may have low literacy. Needs a short, plain explanation in their language and a clear "what happens next".
- **Office lead / IT (buyer):** needs data to stay in the building, simple install, no licence fees, an audit-friendly open codebase.

### 3.2 In scope for the hackathon

- Letter types (12): payment order (Zahlungsbefehl), reminder (Mahnung, levels 1–3), tax assessment, health-insurance premium reduction decision, fine (Busse/Ordnungsbusse), Serafe invoice, rent increase on the official form, residence-permit renewal request, school notice, general invoice with QR-bill, debt-collection continuation notice, scam/fake authority letter.
- Source languages: German, French, Italian.
- Client languages (13): simple German, French, Italian, English, Albanian, Portuguese, Serbo-Croatian (BCS), Spanish, Tamil, Tigrinya, Arabic (RTL), Ukrainian, Turkish.
- Reply templates (3): objection to payment order (Rechtsvorschlag), deadline-extension request, instalment request.

### 3.3 Out of scope (say so in the report)

- Legal advice or recommendations on whether to pay or object.
- Sending anything electronically to authorities.
- Storing cases across sessions (a later version could encrypt and store; not now).
- Handwritten letters; Romansh source letters.

---

## 4. Features and acceptance criteria

Priority: **MUST** (demo and judging depend on it), **SHOULD**, **NICE**. Scope valve order (cut first → last): NICE items, Q&A, instalment template, extension template. Never cut: case board, deadline engine, red flags, objection draft, handout, replay mode.

| ID | Feature | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F1 | Batch capture | MUST | Add 1–20 images or PDFs per case; group pages into letters by drag or "same letter" button; auto crop + deskew; thumbnail strip |
| F2 | Per-letter extraction | MUST | Produces `LetterFacts` JSON (section 10) validating against schema; every field has a page span or `null` |
| F3 | OCR cross-check | MUST | For amount, IBAN, reference, dates: if Apertus value ≠ OCR value (normalised), field shows an amber "check" badge |
| F4 | Deadline engine | MUST | Computes `due_date` with rule trace; asks the counsellor for delivery date when the deadline runs from delivery; passes all tests in 17.2 |
| F5 | Case board | MUST | Timeline of all deadlines sorted by days left; threads grouped; open total per creditor; red-flag badges; updates live as letters finish |
| F6 | Thread linking | MUST | Links letters by reference number, creditor IBAN, sender; LLM proposes, deterministic matcher confirms; unconfirmed links shown dashed with "confirm?" |
| F7 | Red flags | MUST | Runs the five checks (section 9.3); each flag has evidence text + source span; never outputs "fake"/"real" verdict; always shows the directory contact if the claimed sender is known |
| F8 | Explanation | MUST | Per letter: What this is · What they want · Deadline · What you can do (only options stated in the letter) · Who to contact; in client language + simple German; each sentence links to ≥1 span or a cited explainer card |
| F9 | Back-translation check | MUST | Score per explanation; below threshold → language light amber for this letter + banner "Check with counsellor" |
| F10 | Reply drafts | MUST (objection), SHOULD (others) | Template filled from facts; all required elements present (17.3); editable; printable A4 |
| F11 | Client handout | MUST | One A4 page in client language: list of letters, what each is, what was done, next dates; correct RTL for Arabic; correct fonts for Tamil/Tigrinya |
| F12 | Case note | MUST | German summary for the office file, no client name unless entered |
| F13 | Session wipe | MUST | "End case" deletes images and results from memory and disk; automatic after 2 h idle |
| F14 | Offline badge | MUST | Header shows `Offline · Apertus 1.5 8B · this device` when `LLM_BASE_URL` is local; shows endpoint host otherwise |
| F15 | Language grid with quality lights | MUST | 13 languages, native names in native script, green/amber/red from `eval/language_lights.json` |
| F16 | Replay mode | MUST | `make run` without GPU serves cached model outputs for the bench + demo letters and says so in the header |
| F17 | Grounded Q&A | NICE | Chat that answers only from current case facts; refuses otherwise |
| F18 | Read-aloud | NICE | Local Piper TTS for supported languages |
| F19 | Calendar export | NICE | `.ics` per deadline |

---
## 5. System architecture

### 5.1 Components

```
┌──────────────────── Help-desk machine or office server · no network at runtime ────────────────────┐
│                                                                                                    │
│  Browser (SvelteKit SPA, served locally)                                                           │
│     capture · case board · letter view · reply editor · handout                                    │
│            │  HTTP (localhost) + Server-Sent Events for progress                                    │
│            ▼                                                                                       │
│  Orchestrator (FastAPI, Python 3.12)                                                               │
│     session store (in memory, tmpfs for images)                                                    │
│     pipeline: preprocess → extract → verify(tools) → explain → check → case pass → reply pass      │
│            │                         │                                   │                         │
│            ▼                         ▼                                   ▼                         │
│  Pre-processing              Deterministic tools                 Apertus 1.5 8B on vLLM            │
│   OpenCV, Tesseract,          deadline engine, IBAN,              (swiss-ai fork image)            │
│   zxing-cpp (QR)              QR-bill parser, authority           OpenAI-compatible API            │
│                               directory, scam patterns            tool parser: apertus             │
│                                      │                                                             │
│                                      ▼                                                             │
│                               Local data (YAML/JSON): holidays via `holidays` lib, authority       │
│                               directory, explainer cards, reply templates, language lights         │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
   Build time only: pip/npm installs, model weights download, font files. Runtime: no outbound traffic.
   Option (c): set LLM_BASE_URL to a Swiss-hosted Apertus endpoint; everything else unchanged.
```

### 5.2 Deployment modes

| Mode | How | Network at runtime |
| --- | --- | --- |
| (b) Air-gapped workstation — **primary** | `docker compose --profile gpu up` with weights baked into the vLLM image or mounted from a local volume | None |
| (a) On-prem office server | Same compose on a server; browsers on the office LAN | LAN only |
| (c) Sovereign Swiss cloud | `LLM_BASE_URL` → Swiss-hosted Apertus endpoint (e.g. a canton's internal AI platform or a Swiss provider) | Only to that endpoint |
| Judge mode | `make run` → replay mode, no GPU | None |

### 5.3 Request flow for one case

1. Counsellor creates a case, picks client language, uploads images.
2. For each letter, in parallel (max 2 concurrent on one 24 GB GPU): preprocess → Pass 1 extract → Pass 2 verify → Pass 3 explain → Pass 4 check. Progress streamed via SSE.
3. When all letters are done: Case pass (order + links) → deterministic link confirmation → case board final.
4. Counsellor opens a letter, chooses a reply → Reply pass → editor.
5. Counsellor prints handout + reply → "End case" → wipe.

---

## 6. Repository layout

Create the repo with **Use this template** on https://github.com/HackApertus/project-template, delete `track_1a/`, `track_1b/`, `track_2a/`, keep `track_2b/` exactly as named. Everything below lives inside `track_2b/` unless marked root.

```
<repo root>/
├── README.md                     # root: points to track_2b, quick start, licence
├── LICENSE                       # Apache-2.0 (from template)
├── Makefile                      # root: `make run` delegates to track_2b (section 16)
└── track_2b/
    ├── README.md                 # keep challenge text; add our Quick Execution for Judges at top
    ├── technical_report.md
    ├── TeamName_Report.pdf       # rename with real team name
    ├── Makefile
    ├── Dockerfile                # app image (orchestrator + built frontend)
    ├── docker-compose.yml        # services: app, vllm (profile gpu)
    ├── .env.example
    ├── pyproject.toml            # uv-managed
    ├── src/
    │   └── briefklar/
    │       ├── __init__.py
    │       ├── main.py                  # FastAPI app, static frontend mount
    │       ├── config.py                # env vars, modes
    │       ├── api/                     # routes: cases, letters, replies, handout, health
    │       ├── session/store.py         # in-memory store, tmpfs paths, wipe
    │       ├── preprocess/
    │       │   ├── image.py             # crop, deskew, resize (OpenCV)
    │       │   ├── ocr.py               # Tesseract with word boxes (deu, fra, ita)
    │       │   └── qr.py                # zxing-cpp decode
    │       ├── llm/
    │       │   ├── client.py            # OpenAI-compatible client + replay cache
    │       │   ├── prompts/             # *.md prompt files, versioned
    │       │   └── schemas.py           # JSON schemas for constrained output
    │       ├── pipeline/
    │       │   ├── extract.py           # Pass 1
    │       │   ├── verify.py            # Pass 2 (tool loop)
    │       │   ├── explain.py           # Pass 3
    │       │   ├── check.py             # Pass 4
    │       │   ├── case.py              # Case pass + deterministic linker
    │       │   └── reply.py             # Reply pass
    │       ├── tools/
    │       │   ├── deadline.py          # rule engine (section 9.1)
    │       │   ├── iban.py
    │       │   ├── qrbill.py            # parse Swiss QR-bill payload
    │       │   ├── authority.py         # directory lookup
    │       │   └── scam.py              # pattern checks
    │       ├── models.py                # Pydantic models (section 10)
    │       ├── render/
    │       │   ├── handout.py           # HTML → PDF (WeasyPrint)
    │       │   └── templates/           # Jinja2: handout, case note, replies
    │       └── knowledge/
    │           ├── authorities.yaml     # SOURCE REQUIRED per entry
    │           ├── explainers/          # one card per letter type × DE/FR/IT, cited
    │           ├── reply_templates/     # objection, extension, instalments × DE/FR/IT
    │           ├── scam_patterns.yaml
    │           └── language_lights.json # produced by eval
    ├── frontend/                 # SvelteKit + TypeScript, adapter-static
    │   ├── src/lib/design/       # tokens.css, components
    │   ├── src/routes/           # /, /case/[id], /case/[id]/letter/[lid], /case/[id]/reply/[rid]
    │   └── static/fonts/         # self-hosted OFL fonts (no CDN)
    ├── data/                     # ≤ 100 MB total
    │   ├── demo/                 # the 8-letter demo case used in the video
    │   ├── bench_small/          # reduced-resolution bench subset for judges
    │   └── replay/               # cached model responses (jsonl, keyed by request hash)
    ├── bench/
    │   ├── generator/            # synthetic letter + case generator (section 14)
    │   └── eval/                 # harness, baselines, metrics, judge (section 15)
    ├── tests/
    └── docs/
        ├── architecture.svg
        ├── screenshots/
        └── moodboard/            # Awwwards references + notes (section 13)
```

---

## 7. Model serving

### 7.1 Model

- Product model: `swiss-ai/Apertus-v1.5-8B` (gated on Hugging Face: log in and accept the conditions first). Inputs: image, audio, text; output: text. Context up to 262,144 tokens; we cap at 16,384 to save memory.
- Judge model (evaluation only): `swiss-ai/Apertus-v1.5-70B` via a hosted endpoint (e.g. Public AI platform or a Swiss provider). Declare in the report.
- Tool calling is **not supported in thinking mode**. Use thinking only in Pass 3.

### 7.2 Serving with vLLM (swiss-ai fork)

Upstream vLLM support is pending; use the swiss-ai image `ghcr.io/swiss-ai/vllm_apertus_1.5_release`. **Pin the digest** you pulled on day 1 in `docker-compose.yml`.

```bash
# development box (one 24 GB GPU, e.g. L4 / RTX 4090 / A10G)
docker run --gpus all -p 8000:8000 \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -e HF_TOKEN=$HF_TOKEN \
  ghcr.io/swiss-ai/vllm_apertus_1.5_release@sha256:<PINNED_DIGEST> \
  vllm serve swiss-ai/Apertus-v1.5-8B \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.85 \
    --enable-auto-tool-choice --tool-call-parser apertus \
    --reasoning-parser apertus \
    --served-model-name apertus-8b
```

- Thinking on per request: `extra_body={"chat_template_kwargs": {"enable_thinking": true}}`. Off is the default.
- Images: send as OpenAI-style content parts with base64 data URLs. **Verify this exact format in the Sunday gate test** (section 21); if the fork expects a different field, adapt `client.py` only.
- Memory estimate (verify): bf16 8B weights ≈ 16 GB; leave the rest for KV cache at 16k context. If OOM: lower `--max-model-len` to 8192 or use a community quantisation for development only (report the exact one used for numbers).
- Do not cast the model with `.half()`; the vision/audio tokenizers stay float32 (model card note). Not relevant to vLLM but relevant if you use Transformers fallback.

### 7.3 Environment variables (`.env.example`)

```dotenv
# Required by the Hack Apertus template
LLM_NAME=apertus-8b                       # model name as served
LLM_BASE_URL=http://vllm:8000/v1          # local vLLM; or a Swiss-hosted endpoint
LLM_API_KEY=not-needed-for-local

# Briefklar
BRIEFKLAR_MODE=replay                     # replay | live
BRIEFKLAR_CANTON=BE                       # default canton for holidays (ISO 3166-2:CH code)
BRIEFKLAR_SESSION_TTL_MIN=120
BRIEFKLAR_MAX_PARALLEL_LETTERS=2
JUDGE_BASE_URL=                           # eval only (Apertus 70B)
JUDGE_API_KEY=
JUDGE_MODEL=apertus-70b
```

### 7.4 LLM client contract (`llm/client.py`)

- `chat(messages, *, schema=None, tools=None, thinking=False, temperature=0.0, max_tokens=2048, seed=7) -> Response`
- Deterministic settings for all product calls: `temperature=0`, fixed `seed`.
- **Replay cache:** key = SHA-256 of canonical JSON of (model name, messages incl. image hashes, schema, tools, thinking, temperature, seed). In `live` mode, write every response to `data/replay/<key>.json`. In `replay` mode, read it; on miss, raise a clear error naming the letter.
- **Schema enforcement:** pass JSON schema via `response_format={"type": "json_schema", ...}` if the fork supports guided decoding (test on day 1); otherwise include the schema in the prompt, parse, validate with Pydantic, and retry once with the validation error appended. Log retries; count them in the eval.
- Timeouts: 120 s per call; one retry on transport error.
- Every call logs (to stdout, no content): pass name, letter id, tokens in/out, latency. Never log letter text or images.

---
## 8. The pipeline in detail

Four Apertus calls per letter plus two per case. Everything that can be computed is computed in code.

### 8.0 Pre-processing (no model)

1. Load image or rasterise PDF page at 200 dpi (pypdfium2).
2. Detect page quadrilateral (OpenCV contour on edge map), perspective-warp, deskew (Hough lines), normalise contrast (CLAHE). Keep the original for display.
3. Resize the long side to 1,600 px for the model (tune in the gate test: test 1,280 / 1,600 / 2,048 for accuracy vs latency).
4. Tesseract OCR with `deu+fra+ita`, PSM 3, output word boxes (`image_to_data`). Store words with bounding boxes and page index → used for grounding highlights and cross-checks.
5. zxing-cpp scan for QR codes. If a payload starts with `SPC`, it is a Swiss QR-bill: parse it (section 9.2).
6. Detect source language with a simple stopword count over OCR text (de/fr/it).

### 8.1 Pass 1 — Extract (vision, thinking off)

**Input:** all page images of one letter + OCR text as a secondary hint (clearly labelled as possibly wrong).
**Output:** `LetterFacts` JSON (section 10.2).

System prompt (`prompts/extract.md`):

```text
You read Swiss official letters and extract facts into JSON. You do not explain or advise.

Rules:
- Use only what is printed on the letter. If a field is not on the letter, return null. Never guess.
- Copy names, reference numbers, IBANs and amounts exactly as printed.
- Dates: return ISO format YYYY-MM-DD. If only a weekday or a relative period is printed, return null for the date and fill "deadline_text" with the exact sentence.
- "deadline_text": copy the full sentence that sets any period or deadline, in the original language.
- "evidence": for every non-null field, copy the shortest exact phrase from the letter that supports it.
- "letter_type": choose one value from the enum. Use "unknown" if unsure.
- "stated_options": list only actions the letter itself offers (for example: pay, object, request instalments, contact office). Copy the phrase for each.
- The OCR text below may contain errors. Prefer what you see in the image.

Return only JSON that matches the schema.
```

User message: images + `OCR (may contain errors):\n<ocr text>` + `Source language guess: de`.

### 8.2 Pass 2 — Verify (tool calling, thinking off)

**Input:** `LetterFacts` + QR payload (if any) + canton + delivery date (if known).
**Behaviour:** Apertus is offered the tools below and asked to verify the letter. The orchestrator executes each call and returns results. Max 6 tool calls per letter. If the model does not call a required tool, the orchestrator calls it anyway (required set: `compute_deadline` when a deadline exists; `validate_iban` when an IBAN exists; `lookup_authority` always; `match_scam_patterns` always). Record how often the orchestrator had to step in; report it.

Tool definitions (OpenAI function format):

```json
[
  {"type":"function","function":{"name":"compute_deadline",
    "description":"Compute the last day to act, using Swiss rules. Never compute dates yourself.",
    "parameters":{"type":"object","required":["rule_family","period_value","period_unit","start_event"],
      "properties":{
        "rule_family":{"type":"string","enum":["schkg","generic_admin","contract","none"]},
        "period_value":{"type":"integer"},
        "period_unit":{"type":"string","enum":["days","months"]},
        "start_event":{"type":"string","enum":["delivery","letter_date","fixed_date"]},
        "letter_date":{"type":["string","null"]},
        "fixed_date":{"type":["string","null"]},
        "canton":{"type":"string"}}}}},
  {"type":"function","function":{"name":"validate_iban",
    "description":"Check IBAN checksum and country.",
    "parameters":{"type":"object","required":["iban"],"properties":{"iban":{"type":"string"}}}}},
  {"type":"function","function":{"name":"decode_qr_bill",
    "description":"Return the parsed Swiss QR-bill found on the letter, if any.",
    "parameters":{"type":"object","properties":{}}}},
  {"type":"function","function":{"name":"lookup_authority",
    "description":"Look up the claimed sender in the local directory of Swiss authorities.",
    "parameters":{"type":"object","required":["sender_name"],
      "properties":{"sender_name":{"type":"string"},"sender_address":{"type":["string","null"]}}}}},
  {"type":"function","function":{"name":"match_scam_patterns",
    "description":"Check the letter text and facts against known scam patterns.",
    "parameters":{"type":"object","required":["letter_id"],"properties":{"letter_id":{"type":"string"}}}}}
]
```

**Output:** `Verification` (deadline result with trace, IBAN result, QR result, authority match, red flags).

**Delivery date:** when `start_event = delivery` and no delivery date is known, the deadline card shows "When did the client receive this letter?" with a date picker (default: today). The deadline is computed only after input; the case board shows "date needed" in the meantime. This is a feature; show it in the demo.

### 8.3 Pass 3 — Explain (thinking on, no tools)

**Input:** `LetterFacts` + `Verification` + the explainer card for this letter type in the source language (section 9.5) + target language + reading level.
**Output:** `Explanation` JSON: for each of the five sections, a list of sentences, each with `support` = list of evidence ids or explainer-card ids. Produced twice: target language and simple German (two calls; cache them).

System prompt (`prompts/explain.md`):

```text
You help a counsellor explain an official letter to a client. Write in {target_language}.

Write five short sections:
1. What this is (one sentence).
2. What they want.
3. Deadline: use exactly the date and weekday given in VERIFIED FACTS. Never change or compute a date.
4. What you can do: only the options the letter itself states. Do not recommend one.
5. Who to contact: use only the contact from VERIFIED FACTS (directory), never a phone number printed on a suspicious letter.

Rules:
- Short sentences (under 15 words). One idea per sentence. Numbers as digits. Dates with the weekday.
- Plain words. No legal advice. No guessing.
- Every sentence must cite its support ids from FACTS or CARD. A sentence without support is not allowed.
- If red flags exist, start section 1 with: "Be careful: this letter shows warning signs." (in {target_language}) and do not tell the client to pay or call numbers from the letter.

Return only JSON matching the schema.
```

### 8.4 Pass 4 — Check (no thinking)

1. Back-translate the target-language explanation into German (Apertus, temperature 0).
2. Compare to the simple-German explanation: chrF (sacrebleu) and a field check — the date string, amount and sender must appear unchanged.
3. If chrF < threshold for that language or any field check fails → flag `low_confidence`, show amber banner, and show the simple-German twin side by side by default.

Thresholds start at chrF 50 and are calibrated on day 5 from native-speaker spot checks (section 15.5). Record the final values in the report.

### 8.5 Case pass (once all letters are done)

**Input:** compact JSON of every letter's facts (no images): id, type, sender, reference numbers, IBAN, amounts, dates, due dates, red flags.
**Output:** proposed threads (groups of letter ids with reason) and a priority order with one-line reasons.

Then the deterministic linker confirms each proposed link if **any** holds: same normalised reference number; same creditor IBAN; same sender + same amount ± fees within 20%; payment order whose creditor matches a reminder's sender. Links the model proposes but the linker cannot confirm are shown dashed with a "confirm?" control. Links the linker finds but the model missed are added (log as "model miss").

Final ordering is deterministic: (1) red-flagged letters first (warn early), (2) by days left ascending, (3) letters needing a delivery date, (4) letters without deadline. The model's reasons are shown as tooltips only.

### 8.6 Reply pass

Templates (section 9.6) contain fixed legal wording plus slots. The model only fills slots from facts and, where a slot is free text (e.g. reason for an extension), drafts one or two neutral sentences that the counsellor must review (highlighted). Output language = letter's source language, formal register. Every filled slot keeps its source span for hover highlighting.

---

## 9. Deterministic engines and local knowledge

### 9.1 Deadline engine (`tools/deadline.py`)

**Verified rules implemented for `rule_family = "schkg"`** (debt enforcement):

| Rule | Source |
| --- | --- |
| Objection (Rechtsvorschlag) to a payment order: within **10 days** of delivery, orally or in writing, to the debt-collection office | Betreibungsamt Thurgau information sheet on the payment order |
| Day counting (SchKG Art. 31): the day the period starts is **not counted**; if the last day is a Saturday, Sunday or state-recognised public holiday, the period ends on the **next working day** | SchKG Art. 31 (via law.ch) |
| Month periods (Art. 31): end on the day with the same number; if that day does not exist, on the last day of the month | SchKG Art. 31 |
| Debt-enforcement holidays (SchKG Art. 56): seven days before and after Easter and Christmas, and 15–31 July | SchKG Art. 56 |
| Effect (SchKG Art. 63): holidays do not stop a period, but if it **ends** during them it is extended to the **third day after** they end; Saturdays, Sundays and public holidays are not counted in those three days | SchKG Art. 63 |
| Restoration of a missed deadline without fault: request within 10 days after the obstacle ends (Art. 33) | Betreibungsamt Thurgau information sheet |

Implementation:

```python
def compute_deadline(rule_family, period_value, period_unit, start_event,
                     start_date, canton) -> DeadlineResult:
    # 1. start_date = delivery / letter_date / fixed_date (must be provided)
    # 2. raw_end = start_date + period (days: not counting start day; months: same day number, clamp to month end)
    # 3. if rule_family == "schkg" and raw_end in betreibungsferien(raw_end.year, raw_end.year±1):
    #        end = third working day after the holiday window ends  (Art. 63)
    # 4. while end is Saturday, Sunday or holiday(canton): end += 1 day     (Art. 31)
    # 5. return DeadlineResult(due_date=end, trace=[each step as text with the rule cited])
```

- Public holidays: `holidays.Switzerland(subdiv=<canton>)` (library `holidays`, tested: supports all 26 cantons). Note it lists cantonal holidays; confirm the set against the canton's official list for the demo canton and record the source.
- Betreibungsferien windows: Easter Sunday ± 7 days; 25 Dec ± 7 days (18 Dec – 1 Jan); 15–31 July. The exact interpretation of "seven days before and after" (inclusive bounds) must be confirmed against an official source; encode as a constant with `TODO(source)` and test both edges.
- `generic_admin` (tax, permits, fines, insurance decisions): **do not hardcode periods.** Use the period stated in the letter's own instructions on appeal or objection (`deadline_text`). Apply "start day not counted" and "weekend/holiday roll-over" only after confirming with the relevant procedural law for the demo canton (`SOURCE REQUIRED`). Until confirmed, show the computed date with an amber "rule unverified" note.
- `contract` (rent increase, invoices): use the stated due date or period; no roll-over unless sourced.
- The trace is shown to the counsellor on tap ("Delivered Thu 8 Oct → +10 days → Sun 18 Oct → Sunday, moved to Mon 19 Oct (SchKG Art. 31)").

### 9.2 IBAN and QR-bill (`tools/iban.py`, `tools/qrbill.py`)

- IBAN: `stdnum.iban.is_valid`, country = first two letters; flag non-CH/LI IBANs on letters that claim a Swiss authority sender.
- QR-bill: parse the `SPC` payload line by line per the Swiss Payment Standards QR-bill implementation guidelines (`SOURCE REQUIRED`: cite the version you implement). Extract creditor IBAN/QR-IBAN, creditor name/address, amount, currency, reference type and reference. Compare with printed values from Pass 1; mismatches are red flags.
- Generator side (section 14) uses the `qrbill` library (PyPI `qrbill` 1.2.0) to create valid QR-bills.

### 9.3 Red-flag checks (`tools/scam.py`)

Each returns zero or more `RedFlag(code, severity, evidence, span_ids)`. Never output a "fake" verdict.

| Code | Check |
| --- | --- |
| `SENDER_NOT_IN_DIRECTORY` | Claimed authority not found in `authorities.yaml` (fuzzy match ≥ 90) |
| `CONTACT_MISMATCH` | Phone, email or web address on letter differs from directory entry |
| `FOREIGN_IBAN_FOR_AUTHORITY` | Claimed Swiss authority, IBAN not CH/LI |
| `QR_MISMATCH` | QR-bill creditor/amount differs from printed text |
| `URGENCY_PAYMENT_UNUSUAL_CHANNEL` | Demands payment via gift cards, crypto, or cash transfer services |
| `LEGAL_BASIS_INCONSISTENT` | Letter cites a legal basis listed in `scam_patterns.yaml` as not applicable to the stated situation (seeded from the reported fake SEM letters: they cited the bilateral "valve clause" to end the residence of people already living in Switzerland; reports note it applies only to immigration, and had not been applied since Dec 2021). Each pattern entry must carry its source URL |
| `NO_LEGAL_REMEDY_NOTICE` | An official decision with no instructions on appeal (only for letter types where these are expected; `SOURCE REQUIRED` per type) |

### 9.4 Authority directory (`knowledge/authorities.yaml`)

```yaml
- id: sem
  names: ["Staatssekretariat für Migration", "Secrétariat d'Etat aux migrations", "Segreteria di Stato della migrazione", "SEM"]
  level: federal
  phone: null        # SOURCE REQUIRED: copy from the official sem.admin.ch contact page
  web: null          # SOURCE REQUIRED
  source_url: null   # page the entry was copied from
  retrieved: null    # date
```

Populate only authorities used in the demo and bench (~25 entries: SEM, cantonal migration offices for the demo cantons, debt-collection offices for 3 districts, cantonal tax offices for 3 cantons, Serafe, 2 health insurers' premium-reduction offices). Every phone number and address must be copied from the official website with `source_url` and `retrieved`.

### 9.5 Explainer cards (`knowledge/explainers/<type>.<lang>.md`)

Short cards (≤ 150 words) per letter type × DE/FR/IT: what this letter is, what usually happens next, typical options, where to get help. Written by the team **from official information sheets**, each with source links in front matter. They are the only background knowledge Pass 3 may use besides the letter.

```markdown
---
type: payment_order
lang: de
sources:
  - https://betreibungsamt.tg.ch/public/upload/assets/92744/Informationsblatt%20zum%20Zahlungsbefehl%20de.pdf
---
Ein Zahlungsbefehl ist ... (≤150 Wörter)
```

### 9.6 Reply templates (`knowledge/reply_templates/`)

Jinja2 templates with fixed wording and slots. Required elements are listed in the front matter and checked by tests.

```markdown
---
id: objection_payment_order
lang: de
required: [debtor_name, debtor_address, office_name, office_address, enforcement_number, objection_sentence, date, signature_line]
source: SOURCE REQUIRED (official guidance on how to file a Rechtsvorschlag)
---
{{ debtor_name }}
{{ debtor_address }}

{{ office_name }}
{{ office_address }}

{{ place }}, {{ date }}

Betreibung Nr. {{ enforcement_number }}

{{ objection_sentence }}

Freundliche Grüsse

{{ signature_line }}
```

`objection_sentence` is fixed text per language, taken from official guidance (`SOURCE REQUIRED`), not generated.

---

## 10. Data models (`models.py`, Pydantic v2)

### 10.1 Session

```python
class Case(BaseModel):
    id: str                        # random, not tied to client identity
    created_at: datetime
    client_language: LangCode      # e.g. "sq", "pt", "ta", "ti", "ar"
    canton: CantonCode
    letters: list["Letter"]
    threads: list["Thread"] = []
    status: Literal["capturing", "processing", "ready", "closed"]
```

### 10.2 Letter facts (Pass 1 output schema)

```python
class Evidence(BaseModel):
    id: str                 # "e1", "e2", ...
    text: str               # exact phrase from the letter
    page: int
    bbox: tuple[float, float, float, float] | None   # filled by aligning text to OCR word boxes

class Money(BaseModel):
    amount: Decimal
    currency: Literal["CHF", "EUR"]

class LetterFacts(BaseModel):
    letter_type: Literal["payment_order","reminder","tax_assessment","premium_reduction",
                         "fine","serafe_invoice","rent_increase","permit_renewal",
                         "school_notice","invoice_qr","continuation_notice","unknown"]
    source_language: Literal["de","fr","it"]
    sender_name: str | None
    sender_address: str | None
    sender_contact: str | None
    recipient_name: str | None
    letter_date: date | None
    reference_numbers: list[str] = []
    amounts: list[Money] = []
    iban: str | None
    demanded_action: str | None
    deadline_text: str | None
    deadline_period_value: int | None
    deadline_period_unit: Literal["days","months"] | None
    deadline_start_event: Literal["delivery","letter_date","fixed_date"] | None
    deadline_fixed_date: date | None
    stated_options: list[str] = []
    evidence: dict[str, list[str]]  # field name -> evidence ids
    evidence_items: list[Evidence]
```

### 10.3 Verification, explanation, thread, reply

```python
class DeadlineResult(BaseModel):
    due_date: date | None
    days_left: int | None
    needs_delivery_date: bool
    rule_family: str
    trace: list[str]           # human-readable steps with rule citations
    verified_rule: bool        # False → amber "rule unverified"

class RedFlag(BaseModel):
    code: str
    severity: Literal["warn","high"]
    evidence: str
    span_ids: list[str]

class Verification(BaseModel):
    deadline: DeadlineResult | None
    iban_valid: bool | None
    iban_country: str | None
    qr: dict | None
    authority_id: str | None
    authority_contact: dict | None
    red_flags: list[RedFlag]
    field_checks: dict[str, Literal["match","mismatch","ocr_missing"]]
    orchestrator_forced_tools: list[str]

class Sentence(BaseModel):
    text: str
    support: list[str]         # evidence ids or "card:<id>"

class Explanation(BaseModel):
    language: LangCode
    what_this_is: list[Sentence]
    what_they_want: list[Sentence]
    deadline: list[Sentence]
    what_you_can_do: list[Sentence]
    who_to_contact: list[Sentence]
    low_confidence: bool = False
    backtranslation_chrf: float | None = None

class Thread(BaseModel):
    id: str
    letter_ids: list[str]
    reason: str
    confirmed: bool            # deterministic linker agreed

class ReplyDraft(BaseModel):
    template_id: str
    language: Literal["de","fr","it"]
    slots: dict[str, str]
    slot_sources: dict[str, list[str]]
    needs_review: list[str]    # slots drafted by the model
    rendered_text: str
```

---

## 11. API (FastAPI)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | mode (replay/live), model name, endpoint host, offline flag |
| POST | `/api/cases` | create case `{client_language, canton}` → `{case_id}` |
| POST | `/api/cases/{id}/pages` | multipart upload of images/PDFs → page ids |
| POST | `/api/cases/{id}/letters` | group pages `{page_ids}` → letter id |
| POST | `/api/cases/{id}/process` | start pipeline for all letters |
| GET | `/api/cases/{id}/events` | SSE stream: `letter.stage`, `letter.done`, `case.done`, `error` |
| GET | `/api/cases/{id}` | full case state |
| POST | `/api/letters/{lid}/delivery-date` | `{date}` → recompute deadline |
| POST | `/api/threads/{tid}/confirm` | counsellor confirms or rejects a dashed link |
| POST | `/api/letters/{lid}/replies` | `{template_id}` → ReplyDraft |
| PUT | `/api/replies/{rid}` | save counsellor edits |
| GET | `/api/replies/{rid}.pdf` | printable reply |
| GET | `/api/cases/{id}/handout.pdf` | client handout |
| GET | `/api/cases/{id}/case-note.pdf` | German case note |
| DELETE | `/api/cases/{id}` | wipe |

Images are stored under a tmpfs mount (`/run/briefklar`) and deleted on wipe and on TTL expiry. No database.

---

## 12. Frontend screens

Stack: SvelteKit + TypeScript, `adapter-static`, served by FastAPI. Motion with the Web Animations API and CSS; no heavy animation libraries in the tool itself. PDF rendering of uploaded PDFs with pdf.js (bundled locally). All fonts self-hosted.

| Route | Screen | Key elements |
| --- | --- | --- |
| `/` | Home | Offline badge; "New case" primary button; recent cases this session; small "How it works" strip |
| `/case/new` | Start case | Language grid (13 tiles, native names, quality light); canton select; "Start" |
| `/case/[id]/capture` | Capture | Drop zone / camera; thumbnail strip; group-into-letter; "Read letters" |
| `/case/[id]` | **Case board** | Left: deadline timeline (days-left scale); right: threads as stacked cards; top: totals per creditor; red-flag letters pinned top with red rule |
| `/case/[id]/letter/[lid]` | Letter view | 7/5 split: page image with highlight layer ↔ five explanation cards; language toggle (client ↔ simple German); deadline chip with trace popover; red-flag card; reply buttons |
| `/case/[id]/reply/[rid]` | Reply editor | Formal letter preview (A4 proportion); slots highlighted; model-drafted slots in amber "review"; hover slot → source span on page; Print |
| `/case/[id]/handout` | Handout preview | Client-language A4 preview; Print; "End case" |

States every screen must design: empty, loading (per-letter stage list), partial (some letters done), error (letter failed → "Retry" / "Skip"), low confidence (amber), replay mode (header ribbon).

---
## 13. UI/UX design — Awwwards-informed

### 13.1 The rule

**All frontend UI/UX decisions take their inspiration from Awwwards (awwwards.com): Sites of the Day, Sites of the Year, Developer Awards and the Inspiration collections.** We borrow principles (grid, type hierarchy, pacing, restraint, motion quality), never assets, layouts wholesale, or brand elements. Every screen is reviewed against Awwwards' own judging weights before merge (13.9).

Two registers, deliberately different:

| Register | Where | Awwwards influence |
| --- | --- | --- |
| **Tool** (calm, editorial, fast) | Everything a counsellor uses: case board, letter view, reply editor, handout | Typography-led, clean, generous white space, quiet colour, one accent; motion only to explain state |
| **Showcase** (expressive) | Landing page (`/about` + README hero), demo video, report figures | Scroll-paced reveals, kinetic type, bold large numerals, cinematic transitions |

Never mix: no WebGL, parallax or decorative motion inside the tool. A stressed client and a busy counsellor need calm.

**Never imitate a government identity** (no Swiss cross, no federal red, no Frutiger-like federal type, no coats of arms). The product warns people about fake authority letters; it must not look like one.

### 13.2 Awwwards inspiration protocol (Day 1, 90 minutes, design owner)

1. On awwwards.com → Websites, filter by **Clean**, **Typography** and **Web Interactive**, sorted by recent **Site of the Day**. Also review **Sites of the Year** and the Inspiration section.
2. Pick 12 references: 6 for the Tool register, 6 for the Showcase register.
3. For each, save one screenshot to `docs/moodboard/` and write three lines in `docs/moodboard/README.md`:
   - What we borrow (one principle, e.g. "headline set at 64 px with tight tracking, body at 17 px, nothing in between").
   - Where we apply it (screen + component).
   - What we deliberately do not borrow.
4. Extract tokens from the board (13.4), then lock them. No new colours or type sizes after Day 2 without a moodboard note.

### 13.3 Starting references (verified on 11 Oct 2026; confirm by visiting before use)

| Reference | Award (as listed on Awwwards) | Study it for | Register |
| --- | --- | --- | --- |
| [twks](https://twks.ch/en) — Geneva creative agency (clients include EPFL, Etat de Vaud) | Site of the Day + Developer Award, 7 Oct 2026 (Typography) | Swiss editorial confidence; bilingual EN/FR switching; type-led hierarchy | Tool + Showcase |
| [Odyssée Clinic](https://www.odysseeclinic.com.au/) by Studio NIGHTJAR | Site of the Day + Developer Award, 8 Oct 2026 (Clean) | Calm, reassuring tone; warm off-white ground (theme colour `#FFFCF8`); short spaced statements; numbered sections | Tool |
| [Golden Suisse typographic composition](https://www.awwwards.com/inspiration/typography-design-composition-golden-suisse) by Wemakefab | Awwwards Inspiration item | Minimal black-and-white typographic composition | Tool (headings), Showcase |
| [LPAS](https://lpas.com/) by Studio Naam | Site of the Day + Developer Award, 10 Oct 2026 (Web Interactive) | Interaction quality and pacing | Showcase |
| [Maria Vasilyeva Portfolio](https://www.mariavasilyeva.com/) | Site of the Day + Developer Award, 9 Oct 2026 (Typography) | Typographic rhythm | Showcase |
| [Opal Tadpole](https://www.opalcamera.com/opal-tadpole) by Claudio Guglieri | Site of the Year 2024 | Revealing one product step by step on scroll; precision of product shots | Showcase (landing page structure) |
| [Messenger](https://messenger.abeto.co) by abeto | Site of the Year 2025 | Storytelling pace; memorable single idea | Showcase (video) |
| [Lando Norris](https://landonorris.com/) by OFF+BRAND | Site of the Year 2025 | Energy and confident motion in transitions | Video only |

The design owner replaces or extends this list during the protocol; keep at least 8 with notes.

### 13.4 Design tokens (`frontend/src/lib/design/tokens.css`)

```css
:root {
  /* Ground and ink — warm, calm (Clean/Odyssée-like ground; editorial ink) */
  --bk-paper: #F6F4EF;        /* app background */
  --bk-surface: #FFFFFF;      /* cards, letter preview */
  --bk-ink: #14161A;          /* primary text */
  --bk-ink-2: #4A4F57;        /* secondary text */
  --bk-rule: #E2DED6;         /* hairlines */

  /* One accent + three meanings */
  --bk-teal: #0F6E6A;         /* brand / primary action / "clear" */
  --bk-teal-wash: rgba(15,110,106,.15);  /* grounding highlight */
  --bk-amber: #8F5D00;        /* deadline soon, needs check (text-safe amber: 5.1:1 on paper) */
  --bk-amber-wash: rgba(232,163,23,.18);
  --bk-red: #C8372D;          /* red flags ONLY */
  --bk-red-wash: rgba(200,55,45,.10);
  --bk-green: #2F7D4A;        /* language light green */

  /* Type */
  --bk-font-ui: "Inter Tight", "Noto Sans", system-ui, sans-serif;
  --bk-font-mono: "JetBrains Mono", ui-monospace, monospace;  /* IBANs, references */
  --bk-size-display: clamp(40px, 6vw, 72px);
  --bk-size-h1: 32px; --bk-size-h2: 24px; --bk-size-body: 17px;
  --bk-size-small: 14px; --bk-size-numeral: 56px;  /* days-left counter */
  --bk-leading-tight: 1.1; --bk-leading-body: 1.5;
  --bk-tracking-display: -0.02em;

  /* Space (8-pt), radius, motion */
  --bk-s1: 4px; --bk-s2: 8px; --bk-s3: 16px; --bk-s4: 24px; --bk-s5: 32px; --bk-s6: 48px; --bk-s7: 72px;
  --bk-radius: 10px; --bk-radius-chip: 999px;
  --bk-ease: cubic-bezier(.2,.7,.1,1);
  --bk-fast: 140ms; --bk-base: 240ms; --bk-slow: 420ms;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bk-paper: #121417; --bk-surface: #1A1D21; --bk-ink: #F2F0EB; --bk-ink-2: #A9AEB6;
    --bk-rule: #2A2E34; --bk-teal: #3FB8B0; --bk-teal-wash: rgba(63,184,176,.18);
    --bk-amber: #F0B43C; --bk-red: #FF6B5E; --bk-green: #5CC489;
  }
}
@media (prefers-reduced-motion: reduce) {
  :root { --bk-fast: 0ms; --bk-base: 0ms; --bk-slow: 0ms; }
}
```

Fonts (all SIL Open Font Licence, self-hosted in `static/fonts/`, subset per script): Inter Tight; JetBrains Mono; Noto Sans Arabic, Noto Sans Ethiopic (Tigrinya), Noto Sans Tamil, Noto Sans (Latin/Cyrillic extended for Albanian, BCS, Ukrainian, Turkish). Check each licence file into the repo.

Contrast: verify every text/background pair ≥ 4.5:1 (≥ 3:1 for 24 px+) in both themes with a script in `tests/test_contrast.py`. Checked for these tokens on `--bk-paper`: ink 16.5, ink-2 7.5, teal 5.5, amber 5.1, red 4.7, green 4.6; dark theme pairs all ≥ 6.0. Amber is the usual offender: a brighter amber such as `#B87A00` only reaches 3.3:1, so text uses the darker `--bk-amber` and fills use `--bk-amber-wash`.

### 13.5 Layout

- 12-column grid, 72 px outer margin on desktop, 24 px gutters; 16 px side gutter on phones.
- Letter view: columns 1–7 page image, 8–12 cards. On < 960 px: stacked, page thumbnail sticky on top (30% height), cards scroll beneath.
- Case board: columns 1–5 deadline timeline (vertical, days-left scale), 6–12 thread stacks.
- Max line length 68 characters for explanation text.
- One primary action per screen, bottom-right on desktop, full-width bottom bar on phone.

### 13.6 Signature interactions (with timings)

| Interaction | Behaviour | Timing |
| --- | --- | --- |
| **Two-way grounding** | Hover/focus a sentence → its source spans glow teal on the page (wash + 1 px outline) and the page auto-scrolls them into view; click a highlighted span on the page → the card sentence pulses | fade in `--bk-fast`; scroll `--bk-base` |
| **Reading progress** | Per letter: five steps ("Reading the page", "Finding the sender", "Checking dates", "Checking warning signs", "Writing in Shqip") tick one by one in the client's language; a thin scan line passes over the thumbnail once per stage | step tick `--bk-base`; scan line 900 ms linear, disabled under reduced motion |
| **Case board assembles** | As letters finish, cards slide into their thread stack; linked letters draw a 1 px connector; timeline dots drop into place by days left (FLIP animation) | `--bk-slow` with `--bk-ease`, 60 ms stagger |
| **Days-left numeral** | Large numeral (56 px) counts down from the period length to days left on first reveal | 600 ms, ease-out; static under reduced motion |
| **Deadline trace** | Tap the chip → popover with the computed steps and rule citations | `--bk-base` |
| **Red-flag reveal** | The flagged letter lifts out of the timeline to the top with a red left rule; flag card expands listing evidence lines one by one | `--bk-slow`; lines 80 ms stagger |
| **Language toggle** | Client language ↔ simple German swap with a 120 ms cross-fade; RTL flips layout using CSS logical properties | `--bk-fast` |
| **Reply slot hover** | Hover a filled slot in the reply → same grounding glow on the page | `--bk-fast` |

All motion runs at 60 fps on a mid-range laptop (Chrome performance panel check). Animate only `transform` and `opacity`.

### 13.7 Content and microcopy rules

- Explanations: < 15 words per sentence, one action per sentence, numbers as digits, dates with weekday ("Monday 19 October").
- Never "fake" or "scam" as a verdict. Red-flag heading: "Warning signs" (client language) / "Warnsignale".
- Every result footer: "Briefklar explains letters. It does not give legal advice. Check with the counsellor." in both languages.
- Offline badge copy: "Offline · Apertus 1.5 8B · this device".
- Errors say what happened and what to do: "This page is too blurry to read. Take the photo again in more light."

### 13.8 Accessibility (MUST)

- WCAG 2.2 AA: contrast, focus visible (2 px teal outline + 2 px offset), full keyboard path through capture → board → letter → reply → print.
- `lang` attribute on every text block in a non-UI language; `dir="rtl"` for Arabic blocks; logical CSS properties (`margin-inline-start`, etc.) everywhere.
- Minimum body text 17 px; touch targets ≥ 44 × 44 px.
- `prefers-reduced-motion` respected (tokens above).
- Screen-reader labels for highlights ("Source: line 4 on page 1").
- Handout: printable black-and-white, ≥ 12 pt, no information carried by colour alone.

### 13.9 Design review checklist (Awwwards weights as our internal bar)

Awwwards juries score Design 40%, Usability 30%, Creativity 20%, Content 10% (per published guides on their judging). Score each screen 1–10 per category with two reviewers; merge only if the weighted score ≥ 8.

| Category (weight) | Questions for our screens |
| --- | --- |
| Design (40%) | Is there one clear typographic hierarchy? One accent only? Grid respected? Does it look calm next to the twks / Odyssée references? |
| Usability (30%) | Can a counsellor go from photos to printed objection in under 3 minutes? Keyboard-only path works? Reduced motion works? Loads in < 2 s locally? |
| Creativity (20%) | Is two-way grounding and the case-board assembly memorable and useful, not decorative? |
| Content (10%) | Are all strings plain, short, translated, and free of legal advice? |

### 13.10 Landing page (`/about` and README hero) — Showcase register

1. **Hero:** 8-second muted loop of the case board assembling from a pile of photos; headline "Every letter. Every deadline. In their language." Sub-line: "The letter co-pilot Swiss help desks are allowed to use." Buttons: "Run it in your office" (→ quick start) and "See the numbers".
2. **The problem in three numbers** (large numerals, Opal-style one-idea-per-screen pacing): 10 days to object; 13 client languages; 0 bytes leave the building.
3. **How it works:** Photograph → Order → Act, each step a short looping clip.
4. **Warning signs:** the fake-letter reveal as a scroll-driven sequence.
5. **Measured, not claimed:** benchmark table and language-light grid (static, from `eval/results/`).
6. **Sovereign by design:** simple drawing of the box with no arrows leaving it; the three deployment modes.
7. **Open:** repo, Hugging Face dataset, report PDF, licences, team.

Scroll-driven animation allowed here (CSS scroll-timeline with JS fallback), still respecting reduced motion.

---
## 14. Synthetic data: Swiss Letters Bench v0

### 14.1 Why synthetic

Real client letters contain sensitive personal data and cannot be published. Synthetic letters give exact, code-computed gold labels, can be shared under CDLA-Permissive-2.0, and contain no personal data. Say this plainly in the report and name a real help-desk pilot as the next step.

### 14.2 Responsible generation rules (MUST)

- All people, addresses, reference numbers and companies are fictional (Faker with `de_CH`, `fr_CH`, `it_CH` locales; fixed seed).
- IBANs: generate checksum-valid Swiss IBANs in a reserved test range or from documented test IBANs; never real accounts.
- **No real logos, coats of arms or signatures.** Letterheads are text only.
- Every rendered page carries a small footer: `SYNTHETIC TEST LETTER · Swiss Letters Bench v0 · not a real document`.
- Scam letters claim real authority names (that is the realistic threat) but carry the same footer and no real visual identity.
- Wording is written by the team from public information sheets and sample forms; record the source URL per template in metadata. Do not copy copyrighted text beyond short legal formulas.

### 14.3 Letter templates

`bench/generator/templates/<type>.<lang>.html.j2` — 12 types × 3 languages (36 templates; scam letters in DE/FR only is acceptable). Each template declares its slots and the gold fields it produces:

```yaml
# bench/generator/templates/payment_order.de.yaml
type: payment_order
lang: de
rule_family: schkg
period: {value: 10, unit: days, start_event: delivery}
source: https://betreibungsamt.tg.ch/public/upload/assets/92744/Informationsblatt%20zum%20Zahlungsbefehl%20de.pdf
slots: [office_name, office_address, debtor, creditor, enforcement_number, amount, interest, costs, letter_date]
stated_options: [pay, object]
```

Periods for non-SchKG types come from the sample forms or info sheets the team uses (`SOURCE REQUIRED` per template). The generator never invents a legal period.

### 14.4 Rendering and capture degradations

1. Render HTML → PDF (WeasyPrint) → PNG at 200 dpi.
2. Three capture qualities per letter (Augraphy or OpenCV):
   - `clean`: scanner-like.
   - `phone`: perspective warp ±8°, mild blur, uneven lighting, JPEG q=75.
   - `bad`: stronger warp, shadow band, crumple texture, JPEG q=55, 1,200 px long side.
3. For the judge-facing subset in `data/bench_small/`, store `phone` quality only, resized to keep `data/` < 100 MB. Full set goes to Hugging Face.

### 14.5 Cases and gold

- 150 letters = 12 types × ~11 letters + 15 scam variants (+ remainder distributed).
- 20 case bundles of 5–10 letters: each bundle has 1–2 reminder chains that escalate into a payment order (same creditor, rising fees, same reference), plus unrelated letters, plus a scam letter in 6 of 20 bundles.
- Each case has a fictional "delivered on" date per letter for deadline gold.

Gold JSON per letter (`gold/<letter_id>.json`) = full `LetterFacts` + `gold_due_date` + `gold_next_step` (enum: object, pay, apply, reply, contact_office, no_action, beware) + `gold_red_flags` + `gold_thread_id`. Gold per case: `gold_order` (letter ids by urgency per section 8.5 rules) and `gold_threads`.

`gold_due_date` is computed by the **same deadline engine** used in the product, so add an independent check: 30 hand-computed deadlines in `tests/data/deadline_cases.csv`, worked out by a team member on paper from the rules in 9.1, must all match.

### 14.6 Hugging Face dataset (from `HackApertus/online_hack_template`)

```
swiss-letters-bench-v0/
├── README.md                 # dataset card: purpose, generation, licences, limitations, no PII statement
├── eval/                     # evaluation dataset (test cases)
│   ├── letters.jsonl         # id, type, lang, quality, image paths, gold fields
│   ├── cases.jsonl           # case id, letter ids, gold order, gold threads
│   └── images/<quality>/<id>_p<n>.jpg
├── responses/                # model response dataset
│   ├── briefklar_apertus8b.jsonl
│   ├── b1_translation_only.jsonl
│   ├── b2_ocr_text.jsonl
│   └── b3_vision_no_tools.jsonl
└── metadata/
    └── metadata.jsonl        # per item: generator version, template source URL, licence (CDLA-Permissive-2.0), seed
```

Set access to PUBLIC. Licence: CDLA-Permissive-2.0.

---

## 15. Evaluation harness (`bench/eval/`)

### 15.1 Systems compared

| ID | System | Isolates |
| --- | --- | --- |
| B0 | Tesseract + regex rules (dates, IBAN, amounts, "innert X Tagen") | Non-AI floor |
| B1 | OCR → Apertus 8B **plain translation** into the client language, nothing else | What a Google-Lens-style tool gives a reader |
| B2 | OCR text → Apertus 8B explanation (Pass 3 prompt, no vision, no tools) | Value of vision |
| B3 | Apertus 8B vision, extraction + explanation, **no tools, letter by letter**, model computes dates itself | Value of tools and case-level reasoning |
| BK | Briefklar full pipeline | Full system |

### 15.2 Metrics

| Metric | Definition | Systems |
| --- | --- | --- |
| **Action correctness** (headline) | Share of letters where the output lets a reader get both the correct due date (exact) and the correct next-step category. For B1/B2/B3 text outputs, a "reader" model (Apertus 70B) answers two fixed questions using only the output text; 20% human-checked | all |
| Deadline exact-date accuracy | `due_date == gold_due_date` | B0, B3, BK |
| Letter-type accuracy | exact | B0 (rules), B3, BK |
| Field F1 | per field, after normalisation (whitespace, case, date format, CHF amounts to cents) | B0, B3, BK |
| Red-flag precision / recall | at letter level (any flag vs gold scam) and code level | B3 (asked), BK |
| Triage order | Kendall's τ between predicted and gold order per case, averaged | B3 (asked to order), BK |
| Thread-linking F1 | pairwise same-thread decisions | B3, BK |
| Open total accuracy | per creditor, exact to the cent | BK |
| Reply completeness | share of required template elements present and correct | BK |
| Faithfulness | share of explanation sentences supported by the letter or the cited card, judged by Apertus 70B; 20% human-checked; report Cohen's κ | B2, B3, BK |
| Language quality | back-translation chrF per language + native-speaker spot checks (≥ 2 languages, ≥ 10 letters each, 1–5 adequacy) | BK |
| Latency and cost | seconds per letter and per case on one 24 GB GPU; CHF per case = GPU hourly price × time (state the price used) | BK |

### 15.3 LLM-judge prompts (Apertus 70B)

Reader prompt (for action correctness):

```text
You are a resident who only has the text below. Do not use outside knowledge.
Q1: By which exact date must you act? Answer YYYY-MM-DD or "unknown".
Q2: What should you do next? Choose one: object, pay, apply, reply, contact_office, no_action, beware, unknown.
Return JSON {"date": ..., "next_step": ...}.
TEXT:
<<<output under test>>>
```

Faithfulness prompt: given the letter's OCR text, the explainer card and one sentence, answer `supported` / `not_supported` / `partially` with the supporting phrase. Temperature 0.

Human check: random 20% of judge items (seeded), two team members label independently, report agreement and κ with the judge.

### 15.4 Outputs

- `bench/eval/results/summary.json`, `per_letter.csv`, `per_language.csv`, `per_case.csv`.
- `bench/eval/results/figures/*.svg` for the report (deadline accuracy by system; action correctness B1 vs BK; language lights grid; latency box plot).
- `make eval` reproduces everything from `data/replay/` without a GPU; `make eval-live` re-runs models.

### 15.5 Language lights (`knowledge/language_lights.json`)

Per language: green if median back-translation chrF ≥ T_green **and** native check mean ≥ 4; amber if chrF ≥ T_amber or native check 3–4; red otherwise. Start with T_green = 60, T_amber = 45 and calibrate on day 5 against native checks; state the final thresholds and which languages had no native check (those cannot be green).

---

## 16. Build, run and Docker

### 16.1 Root `Makefile`

```make
.PHONY: run
run:
	$(MAKE) -C track_2b run
```

### 16.2 `track_2b/Makefile`

```make
SHELL := /bin/bash
COMPOSE := docker compose -f docker-compose.yml

.PHONY: run run-live gpu-up verify eval eval-live bench test down clean

run:            ## Judges: build, verify replay outputs, start the app on http://localhost:8080
	@test -f .env || cp .env.example .env
	$(COMPOSE) build app
	$(COMPOSE) run --rm app python -m briefklar.verify --replay data/replay --bench data/bench_small
	$(COMPOSE) up app

run-live:       ## Use a live endpoint: LLM_BASE_URL must be set in .env
	BRIEFKLAR_MODE=live $(COMPOSE) up app

gpu-up:         ## Air-gapped/on-prem: start local vLLM + app (needs NVIDIA GPU)
	BRIEFKLAR_MODE=live $(COMPOSE) --profile gpu up

eval:           ## Recompute all metrics from cached responses (no GPU)
	$(COMPOSE) run --rm app python -m bench.eval.run --mode replay

eval-live:      ## Re-run all systems against LLM_BASE_URL / JUDGE_BASE_URL
	$(COMPOSE) run --rm app python -m bench.eval.run --mode live

bench:          ## Regenerate the synthetic letters and gold
	$(COMPOSE) run --rm app python -m bench.generator.build --seed 7

test:
	$(COMPOSE) run --rm app pytest -q

down:
	$(COMPOSE) down -v
```

`briefklar.verify` re-runs the deterministic parts (tools, case linker, scoring) on cached model outputs for `bench_small`, checks they reproduce `bench/eval/results/summary_small.json` exactly, prints a short table, and exits non-zero on mismatch.

### 16.3 `docker-compose.yml`

```yaml
services:
  app:
    build: .
    env_file: .env
    ports: ["8080:8080"]
    tmpfs: ["/run/briefklar:size=512m", "/tmp"]
    read_only: true                       # container FS read-only; data/ is a mount
    volumes: ["./data:/app/data"]         # rw so live mode can write data/replay
  vllm:
    profiles: ["gpu"]
    image: ghcr.io/swiss-ai/vllm_apertus_1.5_release@sha256:<PINNED_DIGEST>
    command: >
      vllm serve swiss-ai/Apertus-v1.5-8B --served-model-name apertus-8b
      --max-model-len 16384 --gpu-memory-utilization 0.85
      --enable-auto-tool-choice --tool-call-parser apertus --reasoning-parser apertus
    volumes: ["${HF_HOME:-~/.cache/huggingface}:/root/.cache/huggingface"]
    environment: ["HF_HUB_OFFLINE=1"]     # air-gapped: weights must already be in the cache
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
```

With profile `gpu`, set `LLM_BASE_URL=http://vllm:8000/v1` in `.env`. For a strictly air-gapped run, add an internal-only network (`internal: true`) to both services and document it.

### 16.4 `Dockerfile` (app)

```dockerfile
# --- frontend build ---
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- app ---
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fontconfig \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY src/ src/
COPY bench/ bench/
COPY --from=web /web/build /app/static
COPY frontend/static/fonts/ /usr/share/fonts/briefklar/
RUN fc-cache -f
ENV PYTHONPATH=/app/src:/app PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["uvicorn", "briefklar.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Python dependencies (pin exact versions in `uv.lock`): fastapi, uvicorn, pydantic, openai, opencv-python-headless, pytesseract, zxing-cpp, pypdfium2, python-stdnum, holidays, weasyprint, jinja2, sacrebleu, rapidfuzz, faker, qrbill, augraphy (bench only), pytest. Versions current on 11 Oct 2026 include fastapi 0.143.0, holidays 0.106, zxing-cpp 3.1.1, python-stdnum 2.2, qrbill 1.2.0, weasyprint 70.0.

---

## 17. Tests (MUST pass before submission)

### 17.1 Network isolation

`tests/test_no_network.py`: run the app in replay mode with all outbound sockets blocked except `LLM_BASE_URL` host (monkeypatch `socket.create_connection`); process the demo case; assert no blocked connection was attempted. Frontend: build, then grep the bundle for `http://` / `https://` origins other than relative paths; fail if any (fonts, analytics, CDNs).

### 17.2 Deadline engine

`tests/test_deadline.py`, parametrised from `tests/data/deadline_cases.csv` (30 hand-computed rows). Must include:

- 10 days from a Thursday delivery ending on a Sunday → next Monday.
- Period ending on a cantonal holiday (demo canton) → next working day.
- Period ending on a holiday that exists in one canton but not another → different results per canton.
- Period ending inside Christmas Betreibungsferien → third working day after the window (both window edges tested).
- Period ending inside 15–31 July → third working day after 31 July, skipping a weekend.
- Month period from 31 January → end of February (leap and non-leap year).
- Missing delivery date → `needs_delivery_date=True`, no date.

### 17.3 Tools and templates

- IBAN: valid CH, valid foreign, invalid checksum.
- QR-bill: parse 10 generated bills (from `qrbill`), compare every field.
- Reply templates: render each with complete facts, assert every `required` element present; render with a missing slot → raises.
- Scam checks: one positive and one negative fixture per code.

### 17.4 Pipeline (replay)

- Golden test: the 8-letter demo case produces the same `Case` JSON as `tests/data/demo_case_expected.json`.
- Schema test: every cached Pass 1 output validates against `LetterFacts`.

### 17.5 Frontend

- Playwright: capture → process → board → letter → objection → print preview → end case, in replay mode, with keyboard only.
- Axe accessibility scan on each route: zero serious/critical issues.
- Visual check in RTL (Arabic) and in Tigrinya script.

---

## 18. Privacy, safety and legal framing

- No persistence: images in tmpfs, results in memory; wipe on "End case" and after TTL. Container `read_only: true`.
- No logging of content; only stage, timings and token counts.
- No telemetry, no external fonts or scripts.
- The product states facts from the letter, computed dates with their rule trace, options stated in the letter, and official contacts from the directory. It never recommends paying or objecting.
- Red flags are evidence lists, never verdicts.
- Footer disclaimer on every result and printout (13.7).
- Report section "Limitations and misuse": wrong extraction, unverified rule families, low-resource languages, synthetic-only evaluation, and the safeguard of counsellor review.

---

## 19. Technical report (max 6 pages; `technical_report.md` → `TeamName_Report.pdf`)

Follow the template's headings; map each to a judging criterion.

| Template section | Content | Criterion | Length |
| --- | --- | --- | --- |
| 1. Summary | Problem (help desks, 10-day deadlines, fake letters, ban on public AI tools), approach, headline numbers (action correctness BK vs B1; deadline accuracy; triage τ) | all | ½ page |
| 2. Architecture + Target architecture | Diagram; passes; tools; deployment modes (b) primary, (a), (c); build vs runtime dependencies | Sovereign deployability | 1 page |
| 3. Use of Apertus | Model, serving stack and flags, prompts summary, thinking/tool split, image format, judge model role | Purposeful use of AI | ½ page |
| 4. Data | Synthetic bench design, sources of templates, no PII, licences, HF link | Technical rigour | ½ page |
| 5. Evaluation | Results table (B0–B3, BK), language lights figure, judge–human agreement, latency/cost | Technical rigour, Value | 1½ pages |
| 6. Limitations | Honest list (section 18) | Rigour | ½ page |
| 7. Reproducibility | `make run`, `make eval`, hardware, seeds, commit hash, pinned image digest | Feasibility | ¼ page |
| 8. Next steps | Pilot with a Swiss help desk; more letter types; Romansh; canton platform integration; cost per case at scale | Value & scalability | ¼ page |

Figures: export SVG from the eval; one accent colour (teal) on Briefklar's bars, grey for baselines; label values directly.

---

## 20. Demo video (1:55; limit 2:00)

Record real UI output in live mode at 1080p, 60 fps. Narration with an ElevenLabs voice (sponsor; narration text only, never letter content). Edit with Edit with Ava (sponsor) or any editor. Music: calm, low. Burn in captions.

| Time | Picture | Voiceover |
| --- | --- | --- |
| 0:00–0:08 | A plastic bag of unopened letters tipped onto a help-desk table | "Every week, people bring Swiss help desks a bag of letters they can't read. Some of them give you ten days." |
| 0:08–0:18 | Split screen: phone showing a plain translation of a payment order ("10 days to file a legal proposal"), no date; caption: *The office may not upload this anyway* | "A translation gives you words. It doesn't give you the date, or what to do. And this office isn't allowed to put it in the cloud." |
| 0:18–0:26 | Desk laptop: `Offline · Apertus 1.5 8B · this device`, Wi-Fi off; New case; Albanian (green light); 8 letters photographed in quick cuts | "Briefklar runs here, on this machine." |
| 0:26–0:42 | Case board assembles: reminders snap to the payment order; timeline sorts; top card "Payment order · CHF 1,240 · 9 days left, Mon 19 Oct" | "It reads the whole pile, links the reminders to the payment order they became, and puts every deadline in order." |
| 0:42–0:58 | Fake SEM letter lifts out with a red rule; warning-signs card lists evidence and the real contact from the directory | "This one looks official. It isn't. Briefklar shows exactly why." |
| 0:58–1:12 | Counsellor clicks Objection; formal German reply fills; hover shows each field's source | "The objection is drafted in formal German, every detail traced to the letter. She checks it; the client signs." |
| 1:12–1:22 | Handout prints in Albanian; quick cuts: Tamil, Tigrinya, Arabic RTL | "The client leaves knowing what each letter means and what happens next, in their own language." |
| 1:22–1:42 | Results: B1 vs Briefklar action correctness; triage; language lights incl. ambers/reds; seconds per case | "On 150 letters and 20 cases, here's what each piece adds, and where Apertus still struggles." |
| 1:42–1:52 | Terminal `make run`; Docker up; network icon crossed out | "One GPU. No cloud. Open source. Any commune can run it tomorrow." |
| 1:52–1:55 | Logo "Briefklar · built on Apertus" | (end) |

Rules: the numbers on screen must be the measured ones from `summary.json`; show weak numbers too. The "9 days left" line must match the demo case's computed date on recording day (adjust the fictional delivery date accordingly).

---

## 21. Day-by-day plan (IST; deadline Fri 16 Oct 15:30 IST)

Roles for 3–4 people: **A** model + pipeline, **B** bench + eval, **C** frontend + design, **D** knowledge base, report, video, landing. Solo or duo: follow the order of the MUST items and use the scope valve.

| When | A (model/pipeline) | B (bench/eval) | C (frontend/design) | D (knowledge/report/video) |
| --- | --- | --- | --- | --- |
| **Sun 11, now → 22:00** | Accept HF licences; rent 24 GB GPU; run vLLM image; **gate test** (below) | Repo from template; delete other tracks; root Makefile; CI skeleton | Awwwards protocol (13.2); moodboard | Draft authorities.yaml for demo cantons with sources |
| Sun 11 night | Client with replay cache; Pass 1 prompt v1 | Generator skeleton; 3 templates | Tokens + fonts self-hosted | Explainer cards for payment order + reminder |
| **Mon 12** | Pass 1 schema enforcement; preprocess + OCR + QR; Pass 2 tool loop | All 12 templates (DE first); degradations; gold JSON | App shell, capture screen | Deadline rule sources; test CSV of 30 cases (by hand) |
| **Tue 13** | Deadline engine + tests; Pass 3, Pass 4; case pass + linker; `make run` end to end in replay | 20 case bundles; FR/IT templates; B0 baseline | Case board + letter view with grounding | Reply templates + required elements; scam patterns with sources |
| **Wed 14** | Reply pass; handout + case note PDFs; perf tuning | Run B1–B3 + BK on full bench; judge; human 20% labels | Reply editor; handout preview; language grid; states; a11y pass | Record video rough cut from Wed build; report sections 1–4 |
| **Thu 15** | Bug fixes only; pin image digest; clean-checkout test on a fresh machine | Native-speaker checks; language lights; figures; HF dataset upload | Landing page; design review checklist (13.9) | Final video with real numbers; report 5–8; PDF ≤ 6 pages |
| **Thu 15, 22:00** | **Submit** (all four items) | | | |
| Fri 16 until 15:30 | Buffer only; no new features | | | |

**Gate test tonight (Sun 11, by 22:00 IST)**

1. Make 10 test letters (5 types, DE/FR), print them, photograph them with a phone.
2. Run Pass 1 v0 on each image through the vLLM server.
3. Score by hand: letter type, sender, amount, reference, deadline sentence.
4. **≥ 70% of fields correct** → vision path confirmed.
   **< 70%** → switch Pass 1 to OCR text + image as secondary (or OCR-only); keep vision as an ablation in the eval. The product, case features and demo stay the same.
5. Also confirm: image content-part format accepted; tool calls parsed with `--tool-call-parser apertus`; JSON schema / guided decoding works or needs the retry path.

**Kill / pivot:** if both vision and tool calling fail by Mon 12 noon IST, keep the product but run Pass 1 on OCR text and call tools from the orchestrator; report it honestly. Do not change project at this point.

---

## 22. Submission checklist (via hackapertus.ch/online-hack/submissions)

- [ ] Repo created from `HackApertus/project-template`; only `track_2b/` kept, not renamed; repo **PUBLIC**
- [ ] `make run` works from the repo root on a clean machine with only Docker installed (replay mode)
- [ ] `track_2b/README.md` has "Quick Execution for Judges" at the top (one command, expected output, URL)
- [ ] `technical_report.md` complete; `TeamName_Report.pdf` ≤ 6 pages, in `track_2b/`
- [ ] Demo video ≤ 2:00, public or unlisted link that works logged-out
- [ ] Hugging Face dataset from the HackApertus template, card complete, licence CDLA-Permissive-2.0, PUBLIC
- [ ] Role of every non-Apertus model declared in the report (70B is Apertus; Tesseract is OCR)
- [ ] Licences: code Apache-2.0, report CC-BY-4.0, dataset CDLA-Permissive-2.0; font licences included; T&C section 6 read
- [ ] `data/` ≤ 100 MB (`du -sh track_2b/data`)
- [ ] No secrets in repo (`.env` ignored; `git log -p | grep -i key` clean)
- [ ] All numbers in README, report and video match `bench/eval/results/summary.json`
- [ ] Commit hash in report = submitted commit
- [ ] Submitted by Thu 15 Oct 22:00 IST; confirmation saved

---

## 23. Risks and fallbacks

| Risk | Likelihood | Fallback |
| --- | --- | --- |
| Apertus vision weak on phone photos | Medium | Gate test; OCR-first Pass 1; capture guidance in UI |
| Tool calling unreliable in the fork | Medium | Orchestrator calls required tools itself (already designed in) |
| Guided JSON decoding unsupported | Medium | Prompted schema + Pydantic validation + one retry |
| Low-resource language quality poor | High for some | Language lights; simple-German fallback; counsellor review |
| GPU unavailable to judges | High | Replay mode default; live mode documented |
| Legal rule wrong | Medium | Only SchKG rules marked verified; others amber "rule unverified" until sourced |
| Judges see "another letter explainer" | Medium | Lead everything with help desks, case piles, B1 baseline and the institutional AI ban |
| Scope overrun | Medium | Scope valve (section 4) |
| vLLM image changes | Low–medium | Pinned digest |

---

## 24. Sources (opened 10–11 Oct 2026)

Hackathon
- Hack Apertus Devpost: https://hackapertus.devpost.com/ · resources: https://hackapertus.devpost.com/resources · rules: https://hackapertus.devpost.com/rules
- Official template and Track 2B README: https://github.com/HackApertus/project-template
- Hack Apertus on Hugging Face: https://huggingface.co/HackApertus

Model
- Apertus v1.5 8B model card: https://huggingface.co/swiss-ai/Apertus-v1.5-8B
- Public AI, Apertus 1.5 release: https://publicai.co/stories/apertus-1-5
- Liip, six ways to try Apertus 1.5: https://www.liip.ch/en/blog/apertus-1-5-6-ways-to-try-out-switzerland-s-updated-ai-model

Problem and rules
- Payment order information sheet (10-day objection, Art. 33 restoration): https://betreibungsamt.tg.ch/public/upload/assets/92744/Informationsblatt%20zum%20Zahlungsbefehl%20de.pdf?fp=1
- SchKG Art. 31, 56, 63 (deadline computation, debt-enforcement holidays): https://law.ch/lawinfo/fristen/schuldbetreibungs-und-konkursrecht-schkg/gesetzliche-grundlagen/
- Fake SEM deportation letters: https://www.iamexpat.ch/expat-info/swiss-news/fake-deportation-letters-being-sent-expats-switzerland-sem-warns
- Languages spoken in Switzerland (FSO 2022 via IamExpat): https://www.iamexpat.ch/expat-info/swiss-news/what-are-most-commonly-spoken-languages-switzerland
- Basel-Stadt AI directive for staff: https://www.bs.ch/schwerpunkte/daten/databs/schwerpunkte/kuenstliche-intelligenz/ki-richtlinie
- Zürich Schreibdienst (SRF, 2019): https://www.srf.ch/news/zuercher-schreibdienst-endlich-hilft-mir-jemand
- Zürich Schreibdienst and Infodona: https://www.stadt-zuerich.ch/de/aktuell/medienmitteilungen/2024/01/neu-in-der-selnau-schreibdienst-und-infodona-ziehen-um.html

Competition
- Totoy: https://www.trendingtopics.eu/wiener-ki-app-totoy-erklaert-behoerdenbriefe-in-der-muttersprache/
- BriefEasy: https://briefeasy.app/
- HelvetEasy: https://blink.new/p/helveteasy-app-ivd1n63r
- Google AI Mode with Lens: https://techcrunch.com/2025/04/07/googles-ai-mode-now-lets-users-ask-complex-questions-about-images

Design
- Awwwards Sites of the Year: https://www.awwwards.com/websites/sites_of_the_year/
- Awwwards Clean / Typography / Web Interactive listings: https://www.awwwards.com/websites/clean/ · https://www.awwwards.com/websites/typography/ · https://www.awwwards.com/websites/web-interactive/
- Golden Suisse typographic composition (Awwwards Inspiration): https://www.awwwards.com/inspiration/typography-design-composition-golden-suisse
- Awwwards judging weights explained: https://www.hontran.dev/blog/awwwards-judging-criteria

Libraries (PyPI versions checked 11 Oct 2026): fastapi 0.143.0, holidays 0.106 (Swiss cantons supported, tested), zxing-cpp 3.1.1, python-stdnum 2.2 (IBAN validation tested), qrbill 1.2.0, weasyprint 70.0, opencv-python-headless 5.0.0.93, pytesseract 0.3.13.
