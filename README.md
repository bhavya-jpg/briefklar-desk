# Briefklar Desk

Hack Apertus 2026 · Online Hackathon · Track 2B (Own Project)

Briefklar Desk turns the pile of Swiss official letters a client brings to a help desk into a
deadline-ordered case plan, warning signs, ready-to-sign replies, and an explanation in the client's own
language. It runs on Apertus 1.5 8B on the help desk's own hardware, with no network at runtime.

Everything lives in [`track_2b/`](track_2b/). Start with [`track_2b/README.md`](track_2b/README.md).

## Run it

```bash
make run        # Docker only. Replay mode, no GPU. Then open http://localhost:8080
```

Environment variables, as the template requires: `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`
(see [`track_2b/.env.example`](track_2b/.env.example)).

## Licence

Code: Apache-2.0 ([LICENSE](LICENSE)). Dataset: CDLA-Permissive-2.0. Technical report: CC-BY-4.0.
Fonts: SIL Open Font Licence 1.1 (texts in `track_2b/frontend/static/fonts/licenses/`).
All Hack Apertus projects are open-sourced, see section 6 of https://hackapertus.ch/terms-and-conditions.
