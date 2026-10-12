# Fixture backend

`model.py` is a deterministic stand-in for the language model. It is **not a model and not Apertus**.

It exists because the spec requires `make run` to work end to end in replay mode, and no GPU or Apertus
endpoint was available when this was built. It answers each pass from the generator's gold data and from
the hand-written sentences in `phrases.yaml`, so its answers are near-perfect by construction.

- `python -m bench.fixtures.record` runs the real pipeline with this backend and writes `data/replay/`.
  Every record carries `"backend": "fixture"`; `data/replay/MANIFEST.json`, the app header and the eval
  summary repeat it.
- `python -m bench.fixtures.record --live` (or `make record-live`) does the same against `LLM_BASE_URL`
  and replaces every record with real model output.

Nothing recorded from the fixture backend may be reported as a result. The sentences in `phrases.yaml`
were written by the build assistant and have not been reviewed by native speakers.
