from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.entities import Base

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_contact_profile_picture_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_contact_profile_picture_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    required_columns = {
        "profile_picture_url": "VARCHAR(2048)",
        "profile_picture_source_url": "VARCHAR(2048)",
        "profile_picture_confidence": "FLOAT DEFAULT 0.0",
        "profile_picture_evidence": "JSON DEFAULT '[]'",
        "has_profile_picture": "BOOLEAN DEFAULT 0",
    }

    with engine.begin() as connection:
        rows = list(connection.exec_driver_sql("PRAGMA table_info(contacts)"))
        if not rows:
            return
        existing_columns = {str(row[1]) for row in rows}
        for column_name, column_sql in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(f"ALTER TABLE contacts ADD COLUMN {column_name} {column_sql}")
