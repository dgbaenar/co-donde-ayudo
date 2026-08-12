from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.postgres.config import DatabaseConfig


def create_session_factory(config: DatabaseConfig):
    return sessionmaker(create_engine(config.database_url))
