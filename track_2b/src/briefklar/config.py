"""Environment configuration. The three LLM_* variables are required by the Hack Apertus template."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent.parent  # track_2b/
KNOWLEDGE_DIR = PACKAGE_DIR / "knowledge"

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "vllm", "host.docker.internal"}

# A base URL with this scheme is answered in-process by bench.fixtures (no network, no model).
# It exists so the pipeline can be exercised before a GPU is available; see data/replay/MANIFEST.json.
FIXTURE_SCHEME = "fixture"


@dataclass(frozen=True)
class Settings:
    llm_name: str
    llm_base_url: str
    llm_api_key: str
    mode: str  # replay | live
    canton: str
    session_ttl_min: int
    max_parallel_letters: int
    data_dir: Path
    tmp_dir: Path
    static_dir: Path
    today_override: date | None

    @property
    def replay_dir(self) -> Path:
        # BRIEFKLAR_REPLAY_DIR keeps a second set of recorded responses next to the committed one
        override = os.environ.get("BRIEFKLAR_REPLAY_DIR")
        return Path(override) if override else self.data_dir / "replay"

    @property
    def llm_host(self) -> str:
        return urlparse(self.llm_base_url).hostname or ""

    @property
    def uses_fixture_backend(self) -> bool:
        return urlparse(self.llm_base_url).scheme == FIXTURE_SCHEME

    @property
    def offline(self) -> bool:
        """True when no request can leave this machine: replay mode, or a local model endpoint."""
        return self.mode == "replay" or self.uses_fixture_backend or self.llm_host in LOCAL_HOSTS

    def today(self) -> date:
        return self.today_override or date.today()


def _tmp_dir() -> Path:
    configured = os.environ.get("BRIEFKLAR_TMP")
    if configured:
        path = Path(configured)
        path.mkdir(parents=True, exist_ok=True)
        return path
    tmpfs = Path("/run/briefklar")  # tmpfs mount in docker-compose.yml
    if tmpfs.is_dir() and os.access(tmpfs, os.W_OK):
        return tmpfs
    return Path(tempfile.mkdtemp(prefix="briefklar-"))


@lru_cache
def get_settings() -> Settings:
    env = os.environ
    mode = env.get("BRIEFKLAR_MODE", "replay").strip().lower()
    if mode not in {"replay", "live"}:
        raise ValueError(f"BRIEFKLAR_MODE must be 'replay' or 'live', got {mode!r}")
    today = env.get("BRIEFKLAR_TODAY", "").strip()
    static = env.get("BRIEFKLAR_STATIC_DIR")
    if static:
        static_dir = Path(static)
    else:
        static_dir = next(
            (p for p in (PROJECT_DIR / "static", PROJECT_DIR / "frontend" / "build") if p.is_dir()),
            PROJECT_DIR / "static",
        )
    return Settings(
        llm_name=env.get("LLM_NAME", "apertus-8b"),
        llm_base_url=env.get("LLM_BASE_URL", "http://vllm:8000/v1"),
        llm_api_key=env.get("LLM_API_KEY", "not-needed-for-local"),
        mode=mode,
        canton=env.get("BRIEFKLAR_CANTON", "BE").strip().upper(),
        session_ttl_min=int(env.get("BRIEFKLAR_SESSION_TTL_MIN", "120")),
        max_parallel_letters=int(env.get("BRIEFKLAR_MAX_PARALLEL_LETTERS", "2")),
        data_dir=Path(env.get("BRIEFKLAR_DATA_DIR", PROJECT_DIR / "data")),
        tmp_dir=_tmp_dir(),
        static_dir=static_dir,
        today_override=date.fromisoformat(today) if today else None,
    )
