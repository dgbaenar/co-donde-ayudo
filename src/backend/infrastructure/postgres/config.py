from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    database_url: str = field(repr=False)

    @classmethod
    def from_url(cls, database_url: str) -> "DatabaseConfig":
        database_url = database_url.strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif not database_url.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL must use postgresql:// or postgresql+psycopg://"
            )
        return cls(database_url=database_url)
