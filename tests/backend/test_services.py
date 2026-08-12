from __future__ import annotations

import dataclasses
import unittest
from uuid import uuid4

from backend.application.services import HelpPointService
from backend.domain.emergency_scope import AFFECTED_DEPARTMENTS, list_affected_departments
from backend.domain.models import CreateHelpPoint, NeedStatus


class FakeRepository:
    def __init__(self) -> None:
        self.created = None
        self.updated = None
        self.categories = {}
        self.active_points = ()
        self.managed_point = None
        self.custom_category_id = uuid4()
        self.custom_category_name = None

    def create_help_point(self, point):
        self.created = point
        return point

    def update_help_point(self, point):
        self.updated = point
        return point

    def list_active_categories(self):
        return self.categories

    def list_active_help_points(self):
        return self.active_points

    def get_help_point_by_admin_token(self, admin_token):
        return self.managed_point

    def create_custom_category(self, name):
        self.custom_category_name = name
        return self.custom_category_id


class FakeLocationCatalog:
    def __init__(self) -> None:
        self.localities = {
            "Antioquia": ("Medellín",),
            "Valle del Cauca": ("Cali", "Roldanillo"),
        }

    def list_localities(self, department: str) -> tuple[str, ...]:
        return self.localities.get(department, ())


class HelpPointServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.location_catalog = FakeLocationCatalog()
        self.service = HelpPointService(self.repository, self.location_catalog)
        self.categories = (uuid4(), uuid4())

    def command(self, **changes):
        values = {
            "name": "Parque Central",
            "description": "Familias evacuadas reciben apoyo.",
            "city": "Cali",
            "department": "Valle del Cauca",
            "address": "Calle 5 # 10-20",
            "affected_city": "Roldanillo",
            "affected_department": "Valle del Cauca",
            "latitude": 3.4516,
            "longitude": -76.5320,
            "coordinator_name": "Ana",
            "coordinator_contact": "Contacto local",
            "category_ids": self.categories,
        }
        values.update(changes)
        return CreateHelpPoint(**values)

    def test_emergency_scope_is_immutable_and_explicit(self) -> None:
        self.assertEqual(
            AFFECTED_DEPARTMENTS,
            ("Caldas", "Chocó", "Quindío", "Risaralda", "Valle del Cauca"),
        )
        self.assertIs(list_affected_departments(), AFFECTED_DEPARTMENTS)

    def test_create_command_rejects_empty_location_fields(self) -> None:
        for field in ("address", "affected_city", "affected_department"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.command(**{field: "   "})

    def test_create_rejects_destination_outside_active_scope(self) -> None:
        invalid = self.command(
            affected_department="Antioquia",
            affected_city="Medellín",
        )

        with self.assertRaisesRegex(ValueError, "affected department"):
            self.service.create_help_point(invalid)

    def test_create_rejects_municipality_outside_selected_department(self) -> None:
        invalid_affected = self.command(affected_city="Medellín")
        invalid_physical = self.command(city="Medellín")

        with self.assertRaisesRegex(ValueError, "affected city"):
            self.service.create_help_point(invalid_affected)
        with self.assertRaisesRegex(ValueError, "city"):
            self.service.create_help_point(invalid_physical)

    def test_create_keeps_physical_and_affected_locations_separate(self) -> None:
        created = self.service.create_help_point(self.command()).point

        self.assertEqual((created.city, created.department), ("Cali", "Valle del Cauca"))
        self.assertEqual(created.address, "Calle 5 # 10-20")
        self.assertEqual(
            (created.affected_city, created.affected_department),
            ("Roldanillo", "Valle del Cauca"),
        )

    def test_public_view_exposes_physical_and_affected_locations(self) -> None:
        point = self.service.create_help_point(self.command()).point

        public = self.service.to_public(point)

        self.assertEqual(public.address, "Calle 5 # 10-20")
        self.assertEqual(public.affected_city, "Roldanillo")
        self.assertEqual(public.affected_department, "Valle del Cauca")

    def test_create_point_generates_token_and_multiple_needs(self) -> None:
        result = self.service.create_help_point(self.command())

        self.assertGreaterEqual(len(result.admin_token), 40)
        self.assertEqual(len(self.repository.created.needs), 2)
        self.assertTrue(
            all(need.status is NeedStatus.NEEDS_HELP for need in self.repository.created.needs)
        )
        self.assertTrue(self.service.verify_admin_token(result.admin_token, result.admin_token))
        self.assertFalse(self.service.verify_admin_token(result.admin_token, "incorrect"))

    def test_public_view_never_contains_admin_token(self) -> None:
        result = self.service.create_help_point(self.command())
        public = self.service.to_public(result.point)

        self.assertNotIn("admin_token", {field.name for field in dataclasses.fields(public)})
        self.assertNotIn(result.admin_token, repr(public))

    def test_rejects_invalid_coordinates_and_missing_categories(self) -> None:
        with self.assertRaisesRegex(ValueError, "latitude"):
            self.command(latitude=91)
        with self.assertRaisesRegex(ValueError, "category"):
            self.command(category_ids=())

    def test_add_need_persists_an_immutable_point_with_needs_help(self) -> None:
        created = self.service.create_help_point(self.command()).point
        category_id = uuid4()

        updated = self.service.add_need(created, created.admin_token, category_id)

        self.assertIsNot(updated, created)
        self.assertEqual(self.repository.updated, updated)
        self.assertEqual(updated.needs[-1].category_id, category_id)
        self.assertIs(updated.needs[-1].status, NeedStatus.NEEDS_HELP)

    def test_add_need_rejects_an_existing_category(self) -> None:
        created = self.service.create_help_point(self.command()).point

        with self.assertRaisesRegex(ValueError, "category already exists"):
            self.service.add_need(created, created.admin_token, created.needs[0].category_id)

    def test_remove_need_rejects_incorrect_token_and_unknown_need(self) -> None:
        created = self.service.create_help_point(self.command()).point

        with self.assertRaisesRegex(PermissionError, "admin token"):
            self.service.remove_need(created, "incorrect", created.needs[0].id)
        with self.assertRaisesRegex(ValueError, "need does not exist"):
            self.service.remove_need(created, created.admin_token, uuid4())

    def test_remove_need_persists_updated_point(self) -> None:
        created = self.service.create_help_point(self.command()).point

        updated = self.service.remove_need(created, created.admin_token, created.needs[0].id)

        self.assertEqual(len(updated.needs), 1)
        self.assertEqual(self.repository.updated, updated)

    def test_change_need_status_persists_each_supported_status(self) -> None:
        created = self.service.create_help_point(self.command()).point
        need_id = created.needs[0].id

        for status in NeedStatus:
            created = self.service.change_need_status(created, created.admin_token, need_id, status)
            self.assertEqual(created.needs[0].status, status)

        self.assertEqual(self.repository.updated, created)

    def test_deactivate_point_persists_inactive_point(self) -> None:
        created = self.service.create_help_point(self.command()).point

        updated = self.service.deactivate_help_point(created, created.admin_token)

        self.assertFalse(updated.active)
        self.assertEqual(self.repository.updated, updated)

    def test_lists_active_categories_from_repository(self) -> None:
        categories = {"Agua": uuid4()}
        self.repository.categories = categories

        result = self.service.list_active_categories()

        self.assertEqual(result, categories)

    def test_lists_public_active_points_without_admin_tokens(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.active_points = (point,)

        result = self.service.list_active_help_points()

        self.assertEqual(len(result), 1)
        self.assertNotIn("admin_token", {field.name for field in dataclasses.fields(result[0])})
        self.assertNotIn(point.admin_token, repr(result[0]))

    def test_gets_public_active_point_by_id_without_administrative_data(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.active_points = (point,)

        result = self.service.get_public_help_point(point.id)

        self.assertEqual(result.id, point.id)
        self.assertEqual(result.name, "Parque Central")
        public_fields = {field.name for field in dataclasses.fields(result)}
        self.assertNotIn("coordinator_name", public_fields)
        self.assertNotIn("coordinator_contact", public_fields)
        self.assertNotIn("admin_token", public_fields)

    def test_returns_none_when_public_help_point_is_missing_or_inactive(self) -> None:
        point = self.service.create_help_point(self.command()).point
        inactive_point = self.service.deactivate_help_point(point, point.admin_token)
        self.repository.active_points = (inactive_point,)

        self.assertIsNone(self.service.get_public_help_point(uuid4()))
        self.assertIsNone(self.service.get_public_help_point(inactive_point.id))

    def test_gets_managed_point_only_when_token_identifies_a_point(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.managed_point = point

        self.assertIs(self.service.get_managed_help_point(point.admin_token), point)
        with self.assertRaisesRegex(PermissionError, "admin token"):
            self.service.get_managed_help_point("")
        self.repository.managed_point = None
        with self.assertRaisesRegex(PermissionError, "admin token"):
            self.service.get_managed_help_point("not-found")

    def test_creates_trimmed_custom_category_and_rejects_invalid_name(self) -> None:
        category_id = self.service.create_custom_category("  Medicinas  ")

        self.assertEqual(category_id, self.repository.custom_category_id)
        self.assertEqual(self.repository.custom_category_name, "Medicinas")
        with self.assertRaisesRegex(ValueError, "name"):
            self.service.create_custom_category(" ")

    def test_updates_info_with_valid_admin_token_and_validated_fields(self) -> None:
        point = self.service.create_help_point(self.command()).point

        updated = self.service.update_help_point_info(
            point, point.admin_token, "  Nueva descripción  ", "  Nuevo contacto  "
        )

        self.assertEqual(updated.description, "Nueva descripción")
        self.assertEqual(updated.coordinator_contact, "Nuevo contacto")
        self.assertEqual(self.repository.updated, updated)
        with self.assertRaisesRegex(PermissionError, "admin token"):
            self.service.update_help_point_info(point, "incorrect", "Descripción", "Contacto")
        with self.assertRaisesRegex(ValueError, "description"):
            self.service.update_help_point_info(point, point.admin_token, " ", "Contacto")


if __name__ == "__main__":
    unittest.main()
