"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


_TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_environment(env_file: Path | None = None) -> None:
    """Load environment values from backend .env file if present."""
    target_file = env_file or DEFAULT_ENV_FILE
    load_dotenv(dotenv_path=target_file, override=False)


@dataclass(frozen=True)
class Settings:
    data_root: Path
    db_path: Path
    enrichment_enabled: bool
    enrichment_budget_usd: float = 0.25
    enrichment_model: str = "local-heuristic-v1"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_environment(env_file=env_file)
        data_root = Path(
            os.getenv("CLAWMON_DATA_ROOT", str(Path.home() / ".openclaw" / "agents"))
        ).expanduser()
        db_path = Path(os.getenv("CLAWMON_DB_PATH", "./data/clawmon.db")).expanduser()
        enrichment_enabled = _parse_bool(os.getenv("CLAWMON_ENRICHMENT_ENABLED"), False)
        enrichment_budget_usd = _parse_float(
            os.getenv("CLAWMON_ENRICHMENT_BUDGET_USD"),
            default=0.25,
        )
        enrichment_model = os.getenv("CLAWMON_ENRICHMENT_MODEL", "local-heuristic-v1")
        return cls(
            data_root=data_root,
            db_path=db_path,
            enrichment_enabled=enrichment_enabled,
            enrichment_budget_usd=enrichment_budget_usd,
            enrichment_model=enrichment_model,
        )
