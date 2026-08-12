from __future__ import annotations

from collections.abc import Callable
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.postgres.config import DatabaseConfig

logger = logging.getLogger(__name__)


def create_session_factory(config: DatabaseConfig):
    return sessionmaker(
        create_engine(
            config.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
    )


def create_database_readiness_probe(session_factory) -> Callable[[], bool]:
    def is_database_ready() -> bool:
        try:
            with session_factory() as session:
                return session.execute(text("SELECT 1")).scalar_one() == 1
        except Exception:
            logger.warning("database readiness probe failed", exc_info=True)
            return False

    return is_database_ready
