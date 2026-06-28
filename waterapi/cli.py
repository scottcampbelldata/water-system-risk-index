"""Command-line entry points for database setup and seeding.

python -m waterapi.cli init-db   # create tables + indexes (idempotent)
python -m waterapi.cli load      # load data/processed/app_data.json into Postgres
python -m waterapi.cli serve     # run the API with uvicorn (dev convenience)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from waterapi.config import settings
from waterapi.db.engine import get_engine

SCHEMA_PATH = Path(__file__).resolve().parent / "db" / "schema.sql"
SCHEMA_TRGM_PATH = Path(__file__).resolve().parent / "db" / "schema_trgm.sql"


def init_db() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_PATH.read_text(encoding="utf-8")))
    print(f"Applied schema from {SCHEMA_PATH}")

    # Trigram indexes are an optimization; skip gracefully if pg_trgm is absent.
    try:
        with engine.begin() as conn:
            conn.execute(text(SCHEMA_TRGM_PATH.read_text(encoding="utf-8")))
        print(f"Applied trigram indexes from {SCHEMA_TRGM_PATH}")
    except Exception as exc:  # noqa: BLE001 - best-effort optimization
        print(f"Skipped trigram indexes (pg_trgm unavailable): {exc.__class__.__name__}")


def serve() -> None:
    import uvicorn

    uvicorn.run(
        "waterapi.api.main:app",
        host="127.0.0.1",
        port=settings.water_api_port,
        log_level=settings.water_log_level.lower(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Water risk API admin commands.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create tables and indexes (idempotent).")
    sub.add_parser("load", help="Load the seed JSON into Postgres.")
    sub.add_parser("serve", help="Run the API locally with uvicorn.")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
    elif args.command == "load":
        from waterapi.load import load

        load()
    elif args.command == "serve":
        serve()


if __name__ == "__main__":
    main()
