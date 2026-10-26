#!/usr/bin/env python3
"""Database initialization script for Satyavani AI.

Checks PostgreSQL connectivity, prints clear troubleshooting guidance if unreachable,
and applies Alembic migrations up to head.
"""
import sys
import os
from sqlalchemy import text
from alembic.config import Config
from alembic import command

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import settings
from backend.db.session import engine


def check_connection() -> bool:
    """Attempt a simple connection and query on PostgreSQL."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1;"))
            result.fetchone()
            print(f"[OK] Successfully connected to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
            return True
    except Exception as exc:
        print("\n" + "=" * 70)
        print("[ERROR] DATABASE UNREACHABLE:")
        print(f"Could not connect to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
        print(f"User: {settings.POSTGRES_USER}")
        print(f"Details: {exc}")
        print("-" * 70)
        print("Troubleshooting steps:")
        print(" 1. Ensure Docker / PostgreSQL service is started: `docker compose up -d db`")
        print(" 2. Check for port 5432 conflicts if local Postgres is already installed.")
        print(" 3. Verify POSTGRES_PASSWORD in .env has only letters and numbers (no special characters).")
        print(" 4. To reset a corrupted volume: `docker compose down -v` then `docker compose up -d db`.")
        print("=" * 70 + "\n")
        return False


def run_migrations() -> None:
    """Run Alembic migrations to apply initial schema and vector extension."""
    print("[INFO] Running database migrations...")
    try:
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        alembic_cfg = Config(alembic_ini_path)
        command.upgrade(alembic_cfg, "head")
        print("[OK] Alembic migrations applied successfully!")
    except Exception as exc:
        print(f"[ERROR] Failed applying migrations: {exc}")
        sys.exit(1)


def main() -> None:
    print("=== Satyavani AI - Database Initialization ===")
    if not check_connection():
        sys.exit(1)
    run_migrations()
    print("=== Database ready for use! ===")


if __name__ == "__main__":
    main()
