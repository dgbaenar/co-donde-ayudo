from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from backend.infrastructure.postgres.config import DatabaseConfig
from backend.infrastructure.postgres.database import (
    create_database_readiness_probe,
    create_session_factory,
)
from backend.infrastructure.postgres.orm_models import CommitmentRow, HelpPointRow, NeedCategoryRow, NeedRow


class DatabaseTests(unittest.TestCase):
    def test_creates_session_factory_without_connecting(self) -> None:
        config = DatabaseConfig(database_url="postgresql+psycopg://example")

        with patch("backend.infrastructure.postgres.database.create_engine") as create_engine:
            with patch("backend.infrastructure.postgres.database.sessionmaker") as sessionmaker:
                create_session_factory(config)

        create_engine.assert_called_once_with(
            "postgresql+psycopg://example",
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        sessionmaker.assert_called_once_with(create_engine.return_value)

    def test_database_readiness_probe_executes_select_one_and_returns_true(self) -> None:
        session = MagicMock()
        session.__enter__.return_value = session
        session.execute.return_value.scalar_one.return_value = 1
        probe = create_database_readiness_probe(lambda: session)

        result = probe()

        self.assertTrue(result)
        statement = session.execute.call_args.args[0]
        self.assertEqual(str(statement), "SELECT 1")
        session.execute.return_value.scalar_one.assert_called_once_with()

    def test_database_readiness_probe_contains_database_exceptions(self) -> None:
        session_factory = MagicMock(side_effect=RuntimeError("sensitive database detail"))
        probe = create_database_readiness_probe(session_factory)

        result = probe()

        self.assertFalse(result)

    def test_orm_models_keep_schema_timestamps_and_need_state_constraint(self) -> None:
        self.assertIn("created_at", HelpPointRow.__table__.c)
        self.assertIn("updated_at", HelpPointRow.__table__.c)
        self.assertIn("created_at", NeedCategoryRow.__table__.c)
        self.assertIn("created_at", NeedRow.__table__.c)
        self.assertIn("updated_at", NeedRow.__table__.c)
        self.assertIn("created_at", CommitmentRow.__table__.c)
        self.assertTrue(HelpPointRow.__table__.c.created_at.server_default)
        self.assertTrue(NeedRow.__table__.c.updated_at.server_default)
        self.assertTrue(HelpPointRow.__table__.c.updated_at.onupdate)
        self.assertTrue(NeedRow.__table__.c.updated_at.onupdate)
        constraints = " ".join(str(item.sqltext) for item in NeedRow.__table__.constraints if hasattr(item, "sqltext"))
        self.assertIn("NEEDS_HELP", constraints)
        self.assertIn("HELP_ON_THE_WAY", constraints)
        self.assertIn("COVERED", constraints)


if __name__ == "__main__":
    unittest.main()
