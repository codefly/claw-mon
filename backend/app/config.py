"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    data_root: Path
    db_path: Path
    enrichment_enabled: bool


    @classmethod
    def from_env(cls) -> "Settings":
        data_root = Path(
            os.getenv("CLAWMON_DATA_ROOT", str(Path.home() / ".openclaw" / "agents"))
        ).expanduser()
        db_path = Path(os.getenv("CLAWMON_DB_PATH", "./data/clawmon.db")).expanduser()
        enrichment_enabled = _parse_bool(os.getenv("CLAWMON_ENRICHMENT_ENABLED"), False)
        return cls(
            data_root=data_root,
            db_path=db_path,
            enrichment_enabled=enrichment_enabled,
        )
