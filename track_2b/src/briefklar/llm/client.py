"""The single entry point for model calls (spec section 7.4).

Reads LLM_NAME, LLM_BASE_URL, LLM_API_KEY. Supports:

- live mode: OpenAI-compatible HTTP to LLM_BASE_URL (vLLM serving Apertus 1.5 8B);
- replay mode: responses are read from data/replay/<key>.json, no network at all;
- recording (BRIEFKLAR_RECORD=1, live mode): every response is also written to data/replay/.
  Recording is opt-in because a help desk running live on real letters must not persist anything.

Nothing in this module logs letter text or images: only pass name, letter id, tokens and latency.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from briefklar.config import Settings, get_settings

log = logging.getLogger("briefklar.llm")

TIMEOUT_S = 120
T = TypeVar("T", bound=BaseModel)


class ReplayMiss(RuntimeError):
    """Replay mode has no cached response for this request."""


class SchemaError(RuntimeError):
    """The model did not return JSON matching the schema, even after one retry."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Response:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cached: bool = False
    key: str = ""
    backend: str = ""


def image_part(path: Path | str, sha256: str) -> dict:
    """An image content part. `sha256` (of the uploaded bytes) identifies it in the replay key."""
    return {"type": "image", "path": str(path), "sha256": sha256}


def _for_key(messages: list[dict]) -> list[dict]:
    out = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            content = [
                {"type": "image", "sha256": part["sha256"]} if part.get("type") == "image" else part
                for part in content
            ]
        out.append({**message, "content": content})
    return out


def _for_wire(messages: list[dict]) -> list[dict]:
    """OpenAI-style content parts with base64 data URLs (verify against the fork in the gate test)."""
    out = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "image":
                    data = base64.b64encode(Path(part["path"]).read_bytes()).decode("ascii")
                    parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}})
                else:
                    parts.append(part)
            content = parts
        out.append({**message, "content": content})
    return out


def request_key(model: str, messages: list[dict], schema: dict | None, tools: list | None,
                thinking: bool, temperature: float, seed: int) -> str:
    canonical = json.dumps(
        {"model": model, "messages": _for_key(messages), "schema": schema, "tools": tools,
         "thinking": thinking, "temperature": temperature, "seed": seed},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_json(text: str) -> Any:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the model output")
    return json.loads(text[start : end + 1])


class LLMClient:
    def __init__(self, settings: Settings | None = None, backend: Any = None):
        self.settings = settings or get_settings()
        self.record = os.environ.get("BRIEFKLAR_RECORD", "0") == "1"
        self.guided_json = os.environ.get("BRIEFKLAR_GUIDED_JSON", "1") == "1"
        self.stats = {"calls": 0, "cached": 0, "schema_retries": 0, "tokens_in": 0, "tokens_out": 0}
        self._backend = backend
        self._openai = None

    # -- storage ---------------------------------------------------------------------------------

    def _path(self, key: str) -> Path:
        return self.settings.replay_dir / f"{key}.json"

    def _read(self, key: str) -> Response | None:
        path = self._path(key)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        r = data["response"]
        return Response(
            content=r.get("content"),
            tool_calls=[ToolCall(**c) for c in r.get("tool_calls", [])],
            tokens_in=r.get("tokens_in", 0), tokens_out=r.get("tokens_out", 0),
            latency_s=r.get("latency_s", 0.0), cached=True, key=key, backend=data.get("backend", ""),
        )

    def _write(self, key: str, pass_name: str, response: Response) -> None:
        self.settings.replay_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": key, "pass": pass_name, "model": self.settings.llm_name, "backend": response.backend,
            "response": {
                "content": response.content,
                "tool_calls": [c.__dict__ for c in response.tool_calls],
                "tokens_in": response.tokens_in, "tokens_out": response.tokens_out,
                "latency_s": round(response.latency_s, 3),
            },
        }
        self._path(key).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # -- backends --------------------------------------------------------------------------------

    def _call_backend(self, messages, schema, tools, thinking, temperature, max_tokens, seed, meta) -> Response:
        if self._backend is None and self.settings.uses_fixture_backend:
            from bench.fixtures.model import FixtureBackend  # not a model: see bench/fixtures/README.md

            self._backend = FixtureBackend()
        if self._backend is not None:
            out = self._backend.complete(messages=messages, schema=schema, tools=tools, thinking=thinking, meta=meta)
            return Response(
                content=out.get("content"),
                tool_calls=[ToolCall(**c) for c in out.get("tool_calls", [])],
                backend=getattr(self._backend, "name", "custom"),
            )
        return self._call_http(messages, schema, tools, thinking, temperature, max_tokens, seed)

    def _call_http(self, messages, schema, tools, thinking, temperature, max_tokens, seed) -> Response:
        if self._openai is None:
            from openai import OpenAI

            self._openai = OpenAI(
                base_url=self.settings.llm_base_url, api_key=self.settings.llm_api_key,
                timeout=TIMEOUT_S, max_retries=1,  # one retry on transport error
            )
        kwargs: dict[str, Any] = dict(
            model=self.settings.llm_name, messages=_for_wire(messages),
            temperature=temperature, max_tokens=max_tokens, seed=seed,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if schema and self.guided_json and not tools:
            kwargs["response_format"] = {
                "type": "json_schema", "json_schema": {"name": "output", "schema": schema, "strict": True},
            }
        if thinking:  # tool calling is not supported in thinking mode
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
        completion = self._openai.chat.completions.create(**kwargs)
        message = completion.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        usage = completion.usage
        return Response(
            content=message.content, tool_calls=calls,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            backend="http",
        )

    # -- public API ------------------------------------------------------------------------------

    def chat(self, messages: list[dict], *, schema: dict | None = None, tools: list | None = None,
             thinking: bool = False, temperature: float = 0.0, max_tokens: int = 2048, seed: int = 7,
             pass_name: str = "", letter_id: str = "", label: str = "") -> Response:
        key = request_key(self.settings.llm_name, messages, schema, tools, thinking, temperature, seed)
        self.stats["calls"] += 1
        started = time.perf_counter()

        if self.settings.mode == "replay":
            response = self._read(key)
            if response is None:
                raise ReplayMiss(
                    f"Replay mode has no cached model response for {label or letter_id or 'this letter'} "
                    f"(pass: {pass_name}). Replay mode only serves the demo and bench letters. "
                    "To read new letters, set BRIEFKLAR_MODE=live and point LLM_BASE_URL at an Apertus endpoint."
                )
            self.stats["cached"] += 1
        else:
            response = self._call_backend(
                messages, schema, tools, thinking, temperature, max_tokens, seed,
                {"pass": pass_name, "letter_id": letter_id},
            )
            response.key = key
            response.latency_s = time.perf_counter() - started
            if self.record:
                self._write(key, pass_name, response)

        self.stats["tokens_in"] += response.tokens_in
        self.stats["tokens_out"] += response.tokens_out
        log.info(
            "llm pass=%s letter=%s tokens_in=%d tokens_out=%d latency_s=%.2f cached=%s",
            pass_name, letter_id, response.tokens_in, response.tokens_out, response.latency_s, response.cached,
        )
        return response

    def chat_json(self, messages: list[dict], model: type[T], **kwargs) -> T:
        """Call with a JSON schema, validate with Pydantic, retry once with the validation error."""
        schema = model.model_json_schema()
        response = self.chat(messages, schema=schema, **kwargs)
        try:
            return model.model_validate(extract_json(response.content or ""))
        except (ValueError, ValidationError) as first_error:
            self.stats["schema_retries"] += 1
            log.info("llm schema retry pass=%s letter=%s", kwargs.get("pass_name", ""), kwargs.get("letter_id", ""))
            retry = [
                *messages,
                {"role": "assistant", "content": response.content or ""},
                {"role": "user", "content": "Your answer did not match the schema. Fix it and return only JSON.\n"
                                            f"Validation error:\n{str(first_error)[:1500]}"},
            ]
            response = self.chat(retry, schema=schema, **kwargs)
            try:
                return model.model_validate(extract_json(response.content or ""))
            except (ValueError, ValidationError) as second_error:
                raise SchemaError(f"model output does not match {model.__name__}: {second_error}") from second_error


def replay_manifest(settings: Settings | None = None) -> dict:
    """Where the cached responses came from. Shown in the header so nobody mistakes fixtures for Apertus."""
    path = (settings or get_settings()).replay_dir / "MANIFEST.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"backend": "unknown", "note": "data/replay/MANIFEST.json is missing"}
