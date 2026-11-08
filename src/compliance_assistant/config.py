"""Project settings and secrets.

Everything tunable lives in one frozen dataclass so the notebook, the scripts, the
Streamlit app and the tests all see the same numbers. Environment variables (or a
local `.env`) override the defaults; the API key is *only* ever read from the
environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MissingApiKeyError(RuntimeError):
    """Raised when no Gemini API key is available in the environment."""


@dataclass(frozen=True)
class Settings:
    # --- paths ---------------------------------------------------------------
    project_root: Path = PROJECT_ROOT
    kb_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "kb")
    chroma_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "chroma")
    golden_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "eval" / "golden.jsonl"
    )

    # --- models ----------------------------------------------------------------
    # The class default (gemini-2.5-flash-lite) returns 404 for API keys created after the
    # 3.x rollout, so the project default is the 3.5 lite tier. Gemini 3.x models use fixed
    # sampling defaults and ignore `temperature`; it is only passed to 2.x models.
    llm_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.0
    # Multimodal, multilingual embedding model used in class. gemini-embedding-001 is the
    # text-only fallback; the manifest records whichever one built the cache.
    embedding_model: str = "gemini-embedding-2"
    # 768 keeps the versioned cache small (~4x smaller than the 3072 default) with no
    # measurable loss on a corpus this size.
    embedding_dim: int = 768
    embedding_batch_size: int = 50

    # --- chunking (class defaults; see docs/decisions.md before changing) ---------
    chunk_size: int = 500
    chunk_overlap: int = 50

    # --- retrieval -------------------------------------------------------------------
    k: int = 6
    fetch_k: int = 24
    mmr_lambda: float = 0.6
    # Gemini cosine relevance scores are compressed into a narrow band, so a fixed
    # a-priori threshold is meaningless. `None` means "use the value calibrated on the
    # in-domain vs out-of-domain queries" stored in data/kb/calibration.json.
    score_threshold: float | None = None

    # --- conversation ----------------------------------------------------------------
    # 10 messages = 5 turns. The memory demo (Q1 -> referential Q2 -> "summarise what
    # you told me") must fit inside the window; tests pin that.
    history_window: int = 10
    prompt_version: str = "v3"
    collection_name: str = "clinical_compliance"

    # Derived paths
    @property
    def raw_dir(self) -> Path:
        return self.kb_dir / "raw"

    @property
    def cache_dir(self) -> Path:
        return self.kb_dir / "embeddings"

    @property
    def manifest_path(self) -> Path:
        return self.kb_dir / "manifest.json"

    @property
    def sources_path(self) -> Path:
        return self.kb_dir / "sources.yaml"

    @property
    def calibration_path(self) -> Path:
        return self.kb_dir / "calibration.json"

    @property
    def query_cache_path(self) -> Path:
        return self.kb_dir / "query_cache.jsonl.gz"

    def resolved_threshold(self) -> float | None:
        """The relevance gate: explicit setting, else the calibrated value, else None."""
        if self.score_threshold is not None:
            return self.score_threshold
        if self.calibration_path.exists():
            data = json.loads(self.calibration_path.read_text())
            value = data.get("score_threshold")
            return float(value) if value is not None else None
        return None


def load_settings(**overrides: object) -> Settings:
    """Settings with `.env`/environment overrides applied, then explicit overrides."""
    load_dotenv(PROJECT_ROOT / ".env")
    env: dict[str, object] = {}
    if v := os.environ.get("LLM_MODEL"):
        env["llm_model"] = v
    if v := os.environ.get("EMBEDDING_MODEL"):
        env["embedding_model"] = v
    if v := os.environ.get("SCORE_THRESHOLD"):
        env["score_threshold"] = float(v)
    if v := os.environ.get("PROMPT_VERSION"):
        env["prompt_version"] = v
    return replace(Settings(), **env, **overrides)  # type: ignore[arg-type]


def load_api_key() -> str:
    """Return the Gemini key from the environment, never from source code.

    Accepts GEMINI_API_KEY (course convention) or GOOGLE_API_KEY (what the Google SDK
    reads by default). The key is never logged; callers may print its length.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise MissingApiKeyError(
            "No Gemini API key found. Create one at https://aistudio.google.com/apikey, "
            "then put GEMINI_API_KEY=... in a .env file at the project root "
            "(or in Streamlit Cloud secrets / Colab userdata)."
        )
    return key
