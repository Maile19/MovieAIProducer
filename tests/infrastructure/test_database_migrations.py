import os
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_migration_lifecycle(tmp_path: Path):
    """Test full Alembic migration lifecycle: upgrade head -> verify -> downgrade base -> verify."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    alembic_ini_path = repo_root / "alembic.ini"
    db_file = tmp_path / "test_migration.db"
    async_db_url = f"sqlite+aiosqlite:///{db_file}"
    sync_db_url = f"sqlite:///{db_file}"

    # Configure Alembic Config
    cfg = Config(str(alembic_ini_path))
    cfg.set_main_option("sqlalchemy.url", async_db_url)
    cfg.set_main_option("script_location", str(repo_root / "migrations"))

    # 1. Upgrade to head
    command.upgrade(cfg, "head")

    # 2. Verify schema and table existence using sync sqlite engine
    sync_engine = create_engine(sync_db_url)
    try:
        with sync_engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()
            assert "alembic_version" in table_names
            assert "foundation_metadata" in table_names

            # Verify columns of foundation_metadata
            columns = {col["name"]: col for col in inspector.get_columns("foundation_metadata")}
            assert "key" in columns
            assert "value" in columns
            assert "created_at" in columns
            assert "updated_at" in columns
            assert columns["key"]["primary_key"] == 1

            # Insert and select test record
            conn.execute(
                text("INSERT INTO foundation_metadata (key, value, created_at, updated_at) VALUES (:k, :v, datetime('now'), datetime('now'))"),
                {"k": "schema_version", "v": "1.0.0"},
            )
            conn.commit()

            res = conn.execute(
                text("SELECT value FROM foundation_metadata WHERE key = :k"),
                {"k": "schema_version"},
            ).scalar_one()
            assert res == "1.0.0"
    finally:
        sync_engine.dispose()

    # 3. Downgrade to base
    command.downgrade(cfg, "base")

    # 4. Verify table dropped
    sync_engine = create_engine(sync_db_url)
    try:
        with sync_engine.connect() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()
            assert "foundation_metadata" not in table_names
            assert "alembic_version" in table_names
    finally:
        sync_engine.dispose()

    # 5. Re-upgrade to head to ensure re-applicability
    command.upgrade(cfg, "head")
    sync_engine = create_engine(sync_db_url)
    try:
        with sync_engine.connect() as conn:
            inspector = inspect(conn)
            assert "foundation_metadata" in inspector.get_table_names()
    finally:
        sync_engine.dispose()
