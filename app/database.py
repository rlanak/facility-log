import json
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.paths import APP_DIR

# FACILITY_LOG_DATA_DIR: Docker puts the user's data on a volume outside the
# image — mounting it over /app/data would hide the bundled catalog in
# data/foxhole. Locally (and in the .exe) it stays APP_DIR/data.
DATA_DIR = Path(os.environ.get("FACILITY_LOG_DATA_DIR") or APP_DIR / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'facility_log.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    # Overwritten/deleted data is zeroed, not left in free pages (secrets, see app/crypto.py).
    dbapi_conn.execute("PRAGMA secure_delete = ON")
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
    ("stock_entries", "storage", "VARCHAR(10) DEFAULT 'normal'"),
    ("resources", "imported", "BOOLEAN DEFAULT 0"),
    ("reports", "discord_content", "TEXT DEFAULT ''"),
    ("reports", "lang", "VARCHAR(10) DEFAULT 'pt-BR'"),
    ("buildings", "save_pin_key", "VARCHAR(160)"),
    ("stock_entries", "created_by_id", "INTEGER REFERENCES users(id)"),
    ("reports", "created_by_id", "INTEGER REFERENCES users(id)"),
    ("resources", "unlimited", "BOOLEAN DEFAULT 0"),
    ("buildings", "upgrade", "VARCHAR(80)"),
    ("buildings", "location", "VARCHAR(120)"),
    ("facility_webhooks", "thread_id", "VARCHAR(40)"),
    ("facilities", "owner_id", "INTEGER REFERENCES users(id)"),
    ("facilities", "private", "BOOLEAN DEFAULT 0"),
]


# Secret columns (models use app.crypto.EncryptedText): values written
# before encryption existed are plain text — encrypt them once.
_ENCRYPTED_COLUMNS = [
    ("facility_webhooks", "facility_id", "url"),
    ("users", "id", "access_token"),
    ("users", "id", "refresh_token"),
    ("app_settings", "key", "value"),
]


def _encrypt_plain_secrets(conn) -> int:
    from app import crypto

    count = 0
    for table, pk, column in _ENCRYPTED_COLUMNS:
        rows = conn.exec_driver_sql(
            f"SELECT {pk}, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' "
            f"AND {column} NOT LIKE '{crypto.PREFIX}%'"
        ).fetchall()
        for key, value in rows:
            conn.exec_driver_sql(f"UPDATE {table} SET {column} = ? WHERE {pk} = ?", (crypto.encrypt(value), key))
            count += 1
    return count


def apply_migrations() -> None:
    with engine.connect() as conn:
        encrypted_now = _encrypt_plain_secrets(conn)
        for table, column, definition in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                if (table, column) == ("resources", "unlimited"):
                    # Existing resources get the catalog's default once
                    # (Water), same default a newly created one gets.
                    from app.services import foxhole_data

                    keys = [k for k, d in foxhole_data.get_resource_defs().items() if d.get("unlimited")]
                    for key in keys:
                        conn.exec_driver_sql("UPDATE resources SET unlimited = 1 WHERE resource_def_key = ?", (key,))
        # Global Metas (resources.target_max) became per facility: copy each
        # one into every facility, then clear it so this runs only once.
        legacy = conn.exec_driver_sql(
            "SELECT id, target_max FROM resources WHERE target_max IS NOT NULL AND target_max > 0"
        ).fetchall()
        if legacy:
            facility_ids = [row[0] for row in conn.exec_driver_sql("SELECT id FROM facilities")]
            for resource_id, target in legacy:
                for facility_id in facility_ids:
                    conn.exec_driver_sql(
                        "INSERT OR IGNORE INTO facility_targets (facility_id, resource_id, target_max) VALUES (?, ?, ?)",
                        (facility_id, resource_id, target),
                    )
            conn.exec_driver_sql("UPDATE resources SET target_max = NULL")
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
    if encrypted_now:
        # The plain values would still sit in free pages of the file: rewrite it once.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("VACUUM")
