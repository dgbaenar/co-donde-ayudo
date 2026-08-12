from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.infrastructure.postgres.config import DatabaseConfig
from backend.infrastructure.postgres.database import create_session_factory
from backend.infrastructure.postgres.orm_models import CommitmentRow, HelpPointRow, NeedCategoryRow, NeedRow


class DatabaseTests(unittest.TestCase):
    def test_creates_session_factory_without_connecting(self) -> None:
        config = DatabaseConfig(database_url="postgresql+psycopg://example")

        with patch("backend.infrastructure.postgres.database.create_engine") as create_engine:
            with patch("backend.infrastructure.postgres.database.sessionmaker") as sessionmaker:
                create_session_factory(config)

        create_engine.assert_called_once_with("postgresql+psycopg://example")
        sessionmaker.assert_called_once_with(create_engine.return_value)

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
