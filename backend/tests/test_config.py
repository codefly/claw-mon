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
                "CLAWMON_ENRICHMENT_BUDGET_USD=1.75",
                "CLAWMON_ENRICHMENT_PROVIDER=openai",
                "CLAWMON_ENRICHMENT_MODEL=test-model",
                "CLAWMON_OPENAI_API_KEY=test-openai-key",
                "CLAWMON_OPENAI_BASE_URL=https://proxy.example.com/v1",
                "CLAWMON_ENRICHMENT_TIMEOUT_SECONDS=12.5",
                "CLAWMON_ENRICHMENT_INPUT_COST_PER_1M_USD=0.4",
                "CLAWMON_ENRICHMENT_OUTPUT_COST_PER_1M_USD=1.2",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("CLAWMON_DATA_ROOT", raising=False)
    monkeypatch.delenv("CLAWMON_DB_PATH", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_ENABLED", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_BUDGET_USD", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_PROVIDER", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_MODEL", raising=False)
    monkeypatch.delenv("CLAWMON_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CLAWMON_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_INPUT_COST_PER_1M_USD", raising=False)
    monkeypatch.delenv("CLAWMON_ENRICHMENT_OUTPUT_COST_PER_1M_USD", raising=False)

    settings = Settings.from_env(env_file=env_file)

    assert settings.data_root == Path("/tmp/custom-agents")
    assert settings.db_path == Path("/tmp/custom-clawmon.db")
    assert settings.enrichment_enabled is True
    assert settings.enrichment_budget_usd == 1.75
    assert settings.enrichment_provider == "openai"
    assert settings.enrichment_model == "test-model"
    assert settings.enrichment_openai_api_key == "test-openai-key"
    assert settings.enrichment_openai_base_url == "https://proxy.example.com/v1"
    assert settings.enrichment_timeout_seconds == 12.5
    assert settings.enrichment_input_cost_per_1m_usd == 0.4
    assert settings.enrichment_output_cost_per_1m_usd == 1.2


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
