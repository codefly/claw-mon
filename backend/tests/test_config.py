from pathlib import Path

import app.config as config
from app.config import Settings


def test_from_env_loads_values_from_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "CLAWMON_DATA_ROOT=/tmp/custom-agents",
                "CLAWMON_DB_PATH=/tmp/custom-clawmon.db",
                "CLAWMON_ENRICHMENT_ENABLED=true",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("CLAWMON_DATA_ROOT", raising=False)
    monkeypatch.delenv("CLAWMON_DB_PATH", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_ENABLED", raising=False)

    settings = Settings.from_env(env_file=env_file)

    assert settings.data_root == Path("/tmp/custom-agents")
    assert settings.db_path == Path("/tmp/custom-clawmon.db")
    assert settings.enrichment_enabled is True


def test_process_env_overrides_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CLAWMON_DB_PATH=/tmp/from-file.db\n", encoding="utf-8")

    monkeypatch.setenv("CLAWMON_DB_PATH", "/tmp/from-process-env.db")

    settings = Settings.from_env(env_file=env_file)

    assert settings.db_path == Path("/tmp/from-process-env.db")


def test_from_env_uses_default_env_file_when_not_provided(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CLAWMON_ENRICHMENT_ENABLED=true\n", encoding="utf-8")

    monkeypatch.setattr(config, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.enrichment_enabled is True
