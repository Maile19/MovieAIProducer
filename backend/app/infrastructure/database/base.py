from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic naming conventions for cross-database constraint consistency (SQLite & PostgreSQL)
POSTGRES_SQLITE_NAMING_CONVENTIONS = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=POSTGRES_SQLITE_NAMING_CONVENTIONS)


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""
    metadata = metadata
