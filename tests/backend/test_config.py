from __future__ import annotations

import unittest

from backend.infrastructure.postgres.config import DatabaseConfig


class DatabaseConfigTests(unittest.TestCase):
    def test_normalizes_postgresql_url_for_psycopg(self) -> None:
        config = DatabaseConfig.from_url("postgresql://example")

        self.assertEqual(config.database_url, "postgresql+psycopg://example")

    def test_keeps_explicit_psycopg_driver_url(self) -> None:
        config = DatabaseConfig.from_url("postgresql+psycopg://example")

        self.assertEqual(config.database_url, "postgresql+psycopg://example")

    def test_rejects_blank_database_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            DatabaseConfig.from_url("   ")

    def test_rejects_non_postgresql_or_non_psycopg_urls(self) -> None:
        for database_url in (
            "sqlite:///synthetic.db",
            "postgresql+psycopg2://example",
        ):
            with self.subTest(database_url=database_url):
                with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
                    DatabaseConfig.from_url(database_url)

    def test_repr_does_not_expose_database_credentials(self) -> None:
        config = DatabaseConfig.from_url(
            "postgresql://synthetic:db-password@localhost/donde_ayudo"
        )

        self.assertNotIn("db-password", repr(config))


if __name__ == "__main__":
    unittest.main()
