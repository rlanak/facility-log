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
]


def apply_migrations() -> None:
    with engine.connect() as conn:
        for table, column, definition in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
