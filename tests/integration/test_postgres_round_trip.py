from __future__ import annotations

import os
import unittest
from uuid import UUID

from sqlalchemy import make_url

from backend.application.services import HelpPointService
from backend.domain.models import CreateHelpPoint, NeedStatus
from backend.infrastructure.postgres.config import DatabaseConfig
from backend.infrastructure.postgres.database import create_session_factory
from backend.infrastructure.locations.catalog import ColombiaLocationCatalog
from backend.infrastructure.postgres.orm_models import HelpPointRow
from backend.infrastructure.postgres.repository import PostgresHelpPointRepository


def local_test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not database_url:
        raise unittest.SkipTest("TEST_DATABASE_URL is required for the local PostgreSQL round trip")

    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        raise unittest.SkipTest("TEST_DATABASE_URL must use a PostgreSQL backend")
    if parsed_url.host not in {"localhost", "127.0.0.1"}:
        raise unittest.SkipTest("TEST_DATABASE_URL must target localhost or 127.0.0.1")
    return database_url


class PostgresRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        database_url = local_test_database_url()
        config = DatabaseConfig.from_url(database_url)
        self.session_factory = create_session_factory(config)
        self.service = HelpPointService(
            PostgresHelpPointRepository(self.session_factory),
            ColombiaLocationCatalog.from_package_data(),
        )

    def test_local_postgres_round_trip_through_the_help_point_service(self) -> None:
        categories = self.service.list_active_categories()
        self.assertIn("Agua", categories)
        self.assertIn("Alimentos", categories)
        water_category_id = categories["Agua"]
        food_category_id = categories["Alimentos"]
        self.assertNotEqual(water_category_id, food_category_id)

        created_point_id: UUID | None = None
        try:
            created = self.service.create_help_point(
                CreateHelpPoint(
                    name="Punto de prueba PostgreSQL",
                    description="Registro sintético para verificar el recorrido local.",
                    city="Cali",
                    department="Valle del Cauca",
                    address="Calle 5 # 10-20",
                    affected_city="Roldanillo",
                    affected_department="Valle del Cauca",
                    latitude=3.4516,
                    longitude=-76.5320,
                    coordinator_name="Coordinación de prueba",
                    coordinator_contact="contacto-sintetico@example.test",
                    category_ids=(water_category_id,),
                )
            )
            created_point_id = created.point.id

            public_after_create = self._public_help_point(created_point_id)
            self.assertEqual(public_after_create.name, "Punto de prueba PostgreSQL")
            self.assertEqual(public_after_create.address, "Calle 5 # 10-20")
            self.assertEqual(public_after_create.affected_city, "Roldanillo")
            self.assertEqual(
                public_after_create.affected_department,
                "Valle del Cauca",
            )
            self.assertEqual(
                tuple((need.category_id, need.status) for need in public_after_create.needs),
                ((water_category_id, NeedStatus.NEEDS_HELP),),
            )
            managed_after_create = self.service.get_managed_help_point(created.admin_token)
            self.assertEqual(managed_after_create.id, created_point_id)
            self.assertEqual(managed_after_create.address, "Calle 5 # 10-20")
            self.assertEqual(managed_after_create.affected_city, "Roldanillo")
            self.assertEqual(
                managed_after_create.affected_department,
                "Valle del Cauca",
            )
            self.assertEqual(managed_after_create.needs, created.point.needs)

            self.service.add_need(managed_after_create, created.admin_token, food_category_id)
            managed_after_add = self.service.get_managed_help_point(created.admin_token)
            self.assertEqual(
                {(need.category_id, need.status) for need in managed_after_add.needs},
                {
                    (water_category_id, NeedStatus.NEEDS_HELP),
                    (food_category_id, NeedStatus.NEEDS_HELP),
                },
            )

            water_need_id = self._need_id(managed_after_add, water_category_id)
            self.service.change_need_status(
                managed_after_add,
                created.admin_token,
                water_need_id,
                NeedStatus.COVERED,
            )
            public_after_status_change = self._public_help_point(created_point_id)
            self.assertEqual(
                self._need_status(public_after_status_change, water_category_id),
                NeedStatus.COVERED,
            )

            managed_after_status_change = self.service.get_managed_help_point(created.admin_token)
            food_need_id = self._need_id(managed_after_status_change, food_category_id)
            self.service.remove_need(managed_after_status_change, created.admin_token, food_need_id)
            managed_after_remove = self.service.get_managed_help_point(created.admin_token)
            self.assertEqual(
                {(need.category_id, need.status) for need in managed_after_remove.needs},
                {(water_category_id, NeedStatus.COVERED)},
            )

            self.service.deactivate_help_point(managed_after_remove, created.admin_token)
            public_after_deactivation = self.service.list_active_help_points()
            self.assertNotIn(created_point_id, {point.id for point in public_after_deactivation})
            managed_after_deactivation = self.service.get_managed_help_point(created.admin_token)
            self.assertFalse(managed_after_deactivation.active)
        finally:
            if created_point_id is not None:
                with self.session_factory() as session:
                    with session.begin():
                        point_row = session.get(HelpPointRow, created_point_id)
                        if point_row is not None:
                            session.delete(point_row)

    def _public_help_point(self, point_id: UUID):
        return next(
            point for point in self.service.list_active_help_points() if point.id == point_id
        )

    @staticmethod
    def _need_id(point, category_id: UUID) -> UUID:
        return next(need.id for need in point.needs if need.category_id == category_id)

    @staticmethod
    def _need_status(point, category_id: UUID) -> NeedStatus:
        return next(need.status for need in point.needs if need.category_id == category_id)
