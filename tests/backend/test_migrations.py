from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import call, patch
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
ALEMBIC_ROOT = SOURCE_ROOT / "alembic"
MIGRATION = ALEMBIC_ROOT / "versions/0001_initial_schema.py"
LOCATION_MIGRATION = ALEMBIC_ROOT / "versions/0002_help_point_locations.py"
ADDITIONAL_AREAS_MIGRATION = ALEMBIC_ROOT / "versions/0003_help_point_additional_areas.py"
EXPECTED_TABLES = {"help_points", "need_categories", "needs", "commitments"}


def load_migration():
    specification = importlib.util.spec_from_file_location("initial_migration", MIGRATION)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_location_migration():
    specification = importlib.util.spec_from_file_location(
        "help_point_locations_migration", LOCATION_MIGRATION
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_additional_areas_migration():
    specification = importlib.util.spec_from_file_location(
        "help_point_additional_areas_migration", ADDITIONAL_AREAS_MIGRATION
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class MigrationTests(unittest.TestCase):
    def test_alembic_loads_database_url_from_env_file_without_web_secrets(self) -> None:
        environment = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_directory = Path(temporary_directory)
            (working_directory / ".env").write_text(
                "DATABASE_URL=postgresql://test:test@localhost/donde_ayudo\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    str(ALEMBIC_ROOT / "alembic.ini"),
                    "upgrade",
                    "head",
                    "--sql",
                ],
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CREATE TABLE help_points", result.stdout)
        self.assertIn("INSERT INTO need_categories", result.stdout)

    def test_initial_migration_creates_exactly_four_application_tables(self) -> None:
        self.assertTrue(MIGRATION.is_file())
        tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
        tables = {
            call.args[0].value
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "op"
            and call.func.attr == "create_table"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        }
        self.assertEqual(tables, EXPECTED_TABLES)

    def test_location_migration_follows_initial_revision_without_new_tables(self) -> None:
        self.assertTrue(LOCATION_MIGRATION.is_file())
        migration = load_location_migration()
        tree = ast.parse(LOCATION_MIGRATION.read_text(encoding="utf-8"))
        create_table_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_table"
        ]

        self.assertEqual(migration.revision, "0002_help_point_locations")
        self.assertEqual(migration.down_revision, "0001_initial_schema")
        self.assertEqual(create_table_calls, [])

    def test_location_migration_adds_backfills_and_constrains_three_columns(self) -> None:
        migration = load_location_migration()

        with patch.object(migration, "op") as operations:
            migration.upgrade()

        added_columns = [item.args[1] for item in operations.add_column.call_args_list]
        self.assertEqual(
            [(column.name, column.type.length, column.nullable) for column in added_columns],
            [
                ("direccion", 240, True),
                ("ciudad_afectada", 120, True),
                ("departamento_afectado", 120, True),
            ],
        )
        update_sql = str(operations.execute.call_args_list[0].args[0])
        self.assertIn("ciudad_afectada = ciudad", update_sql)
        self.assertIn("departamento_afectado = departamento", update_sql)
        self.assertEqual(
            operations.alter_column.call_args_list,
            [
                call("help_points", "ciudad_afectada", nullable=False),
                call("help_points", "departamento_afectado", nullable=False),
            ],
        )
        constraint_names = {
            item.args[0] for item in operations.create_check_constraint.call_args_list
        }
        self.assertEqual(
            constraint_names,
            {
                "help_points_direccion_check",
                "help_points_ciudad_afectada_check",
                "help_points_departamento_afectado_check",
            },
        )

    def test_location_migration_upserts_categories_without_replacing_existing_ids(self) -> None:
        migration = load_location_migration()
        expected_categories = [
            {
                "id": uuid5(
                    NAMESPACE_URL,
                    "donde-ayudo/category/Remoción de escombros",
                ),
                "nombre": "Remoción de escombros",
                "grupo": "Apoyo",
                "es_global": True,
                "activo": True,
            },
            {
                "id": uuid5(
                    NAMESPACE_URL,
                    "donde-ayudo/category/Maquinaria pesada",
                ),
                "nombre": "Maquinaria pesada",
                "grupo": "Apoyo",
                "es_global": True,
                "activo": True,
            },
        ]

        with patch.object(migration, "op") as operations:
            migration.upgrade()

        self.assertFalse(operations.bulk_insert.called)
        upsert_sql = " ".join(
            str(operations.execute.call_args_list[1].args[0]).split()
        )
        self.assertIn("INSERT INTO need_categories", upsert_sql)
        self.assertIn("ON CONFLICT (nombre) DO UPDATE", upsert_sql)
        self.assertIn("grupo = EXCLUDED.grupo", upsert_sql)
        self.assertIn("es_global = TRUE", upsert_sql)
        self.assertIn("activo = TRUE", upsert_sql)
        update_clause = upsert_sql.split("DO UPDATE SET", 1)[1]
        self.assertNotIn("id =", update_clause)
        for category in expected_categories:
            self.assertIn(str(category["id"]), upsert_sql)
            self.assertIn(category["nombre"], upsert_sql)

    def test_location_migration_downgrade_preserves_collisions_and_references(self) -> None:
        migration = load_location_migration()
        expected_ids = [
            uuid5(
                NAMESPACE_URL,
                "donde-ayudo/category/Remoción de escombros",
            ),
            uuid5(
                NAMESPACE_URL,
                "donde-ayudo/category/Maquinaria pesada",
            ),
        ]

        with patch.object(migration, "op") as operations:
            migration.downgrade()
        delete_sql = " ".join(str(operations.execute.call_args.args[0]).split())
        self.assertIn("DELETE FROM need_categories AS category", delete_sql)
        self.assertIn("category.id IN", delete_sql)
        self.assertIn("NOT EXISTS", delete_sql)
        self.assertIn("FROM needs", delete_sql)
        self.assertIn("needs.category_id = category.id", delete_sql)
        for category_id in expected_ids:
            self.assertIn(str(category_id), delete_sql)
        self.assertNotIn("Remoción de escombros", delete_sql)
        self.assertNotIn("Maquinaria pesada", delete_sql)
        self.assertEqual(
            [item.args[1] for item in operations.drop_column.call_args_list],
            ["departamento_afectado", "ciudad_afectada", "direccion"],
        )

    def test_initial_migration_uses_bulk_seed_and_required_need_states(self) -> None:
        self.assertTrue(MIGRATION.is_file())
        migration = load_migration()
        self.assertEqual(len(migration.INITIAL_CATEGORIES), 23)
        self.assertEqual(len({category["nombre"] for category in migration.INITIAL_CATEGORIES}), 23)
        self.assertEqual(
            migration.NEED_STATUSES,
            ("NEEDS_HELP", "HELP_ON_THE_WAY", "COVERED"),
        )
        self.assertIn("op.bulk_insert", MIGRATION.read_text(encoding="utf-8"))

    def test_postgres_infrastructure_has_no_manual_sql_files(self) -> None:
        self.assertEqual(list(SOURCE_ROOT.rglob("*.sql")), [])

    def test_initial_migration_preserves_length_constraints(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        expected_constraints = {
            "help_points_nombre_check",
            "help_points_descripcion_check",
            "help_points_ciudad_check",
            "help_points_departamento_check",
            "help_points_nombre_coordinador_check",
            "help_points_contacto_coordinador_check",
            "help_points_admin_token_check",
            "need_categories_nombre_check",
            "need_categories_grupo_check",
            "commitments_nombre_check",
            "commitments_nota_check",
        }
        for constraint in expected_constraints:
            with self.subTest(constraint=constraint):
                self.assertIn(constraint, source)

    def test_additional_areas_migration_follows_location_revision_without_new_tables(self) -> None:
        self.assertTrue(ADDITIONAL_AREAS_MIGRATION.is_file())
        migration = load_additional_areas_migration()
        tree = ast.parse(ADDITIONAL_AREAS_MIGRATION.read_text(encoding="utf-8"))
        create_table_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_table"
        ]

        self.assertEqual(migration.revision, "0003_help_point_additional_areas")
        self.assertEqual(migration.down_revision, "0002_help_point_locations")
        self.assertEqual(create_table_calls, [])

    def test_additional_areas_migration_adds_nullable_column_with_length_constraint(self) -> None:
        migration = load_additional_areas_migration()

        with patch.object(migration, "op") as operations:
            migration.upgrade()

        added_columns = [item.args[1] for item in operations.add_column.call_args_list]
        self.assertEqual(
            [(column.name, column.type.length, column.nullable) for column in added_columns],
            [("zonas_adicionales", 500, True)],
        )
        constraint_names = {
            item.args[0] for item in operations.create_check_constraint.call_args_list
        }
        self.assertEqual(constraint_names, {"help_points_zonas_adicionales_check"})

    def test_additional_areas_migration_downgrade_drops_constraint_and_column(self) -> None:
        migration = load_additional_areas_migration()

        with patch.object(migration, "op") as operations:
            migration.downgrade()

        self.assertEqual(
            [item.args[0] for item in operations.drop_constraint.call_args_list],
            ["help_points_zonas_adicionales_check"],
        )
        self.assertEqual(
            [item.args[1] for item in operations.drop_column.call_args_list],
            ["zonas_adicionales"],
        )

    def test_additional_areas_migration_is_the_single_alembic_head(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_ROOT / "alembic.ini"), "heads"],
            cwd=ALEMBIC_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        heads = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(heads, ["0003_help_point_additional_areas"])

    def test_commitment_note_constraint_belongs_only_to_commitments(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        categories = source.split('op.create_table(\n        "need_categories",', 1)[1].split(
            'op.create_table(\n        "needs",', 1
        )[0]
        commitments = source.split('op.create_table(\n        "commitments",', 1)[1].split(
            'op.create_index(', 1
        )[0]

        self.assertNotIn("commitments_nota_check", categories)
        self.assertIn("commitments_nota_check", commitments)


if __name__ == "__main__":
    unittest.main()
