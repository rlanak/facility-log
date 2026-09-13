import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'facility_log.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# SQLite table columns added after the initial release, so existing local
# databases pick them up instead of failing with "no such column" — kept as a
# plain ALTER TABLE rather than a migration framework, per the project's
# priorize-simplicidade approach (see README).
_ADDED_COLUMNS = [
    ("resources", "farmable", "BOOLEAN DEFAULT 1"),
    ("resources", "resource_def_key", "VARCHAR(80)"),
    ("resources", "nickname", "VARCHAR(120)"),
    ("buildings", "building_type_key", "VARCHAR(80)"),
    ("buildings", "active_recipe_key", "VARCHAR(80)"),
    ("buildings", "queue_count", "INTEGER DEFAULT 0"),
    ("buildings", "production_slots", "TEXT DEFAULT '[]'"),
]


def apply_migrations() -> None:
    with engine.connect() as conn:
        for table, column, definition in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # One-time backfill: buildings still on the old single-recipe fields
        # (production_slots never written) get migrated into the new
        # multi-queue shape. Naturally idempotent — once backfilled,
        # production_slots is no longer '[]' so this no-ops on later startups.
        # Plain Python instead of SQLite's json_object() to not depend on the
        # JSON1 extension being compiled in.
        rows = conn.exec_driver_sql(
            """
            SELECT id, active_recipe_key, queue_count FROM buildings
            WHERE (production_slots IS NULL OR production_slots = '[]')
              AND active_recipe_key IS NOT NULL
              AND queue_count > 0
            """
        ).fetchall()
        for building_id, recipe_key, queue_count in rows:
            slots_json = json.dumps([{"recipe_key": recipe_key, "queue_count": queue_count}])
            conn.exec_driver_sql(
                "UPDATE buildings SET production_slots = ? WHERE id = ?", (slots_json, building_id)
            )
        conn.commit()
