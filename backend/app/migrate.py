"""Migration command for local development."""

from __future__ import annotations

from app.config import Settings
from app.db import apply_migrations


def main() -> None:
    settings = Settings.from_env()
    applied = apply_migrations(settings.db_path)

    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No pending migrations.")


if __name__ == "__main__":
    main()
