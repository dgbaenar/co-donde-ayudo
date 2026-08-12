from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from backend.application.services import HelpPointService
from backend.domain.emergency_scope import AFFECTED_DEPARTMENTS, list_affected_departments
from backend.domain.models import Commitment, CreateHelpPoint, NeedStatus


class FakeRepository:
    def __init__(self) -> None:
        self.created = None
        self.updated = None
        self.categories = {}
        self.active_points = ()
        self.managed_point = None
        self.custom_category_id = uuid4()
        self.custom_category_name = None
        self.point_by_need_id = None
        self.created_commitment_args = None
        self.commitment_to_return = None

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

    def get_help_point_by_need_id(self, need_id):
        return self.point_by_need_id

    def create_custom_category(self, name):
        self.custom_category_name = name
        return self.custom_category_id

    def create_commitment(self, need_id, name, note):
        point = self.point_by_need_id
        need = next((n for n in point.needs if n.id == need_id), None) if point else None
        if need is None:
            raise KeyError(need_id)
        if need.status is NeedStatus.COVERED:
            raise ValueError("need is already covered")
        self.created_commitment_args = (need_id, name, note)
        commitment = self.commitment_to_return or Commitment(
            id=uuid4(),
            need_id=need_id,
            name=name,
            note=note,
            active=True,
            created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        commitments = (*need.commitments, commitment)
        updated_need = dataclasses.replace(
            need,
            commitments=commitments,
            active_commitment_count=sum(1 for c in commitments if c.active),
        )
        transitioned = need.status is NeedStatus.NEEDS_HELP
        if transitioned:
            updated_need = dataclasses.replace(
                updated_need, status=NeedStatus.HELP_ON_THE_WAY
            )
        updated_point = dataclasses.replace(
            point,
            needs=tuple(updated_need if n.id == need_id else n for n in point.needs),
        )
        self.point_by_need_id = updated_point
        if transitioned:
            self.updated = updated_point
        return commitment


class FakeLocationCatalog:
    def __init__(self) -> None:
        self.localities = {
            "Antioquia": ("Medellín",),
            "Valle del Cauca": ("Cali", "Roldanillo"),
        }
        self.queried_departments: list[str] = []

    def list_localities(self, department: str) -> tuple[str, ...]:
        self.queried_departments.append(department)
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

    def test_create_command_accepts_missing_or_valid_additional_affected_areas(self) -> None:
        without_extra = self.command()
        self.assertIsNone(without_extra.additional_affected_areas)

        with_extra = self.command(additional_affected_areas="Roldanillo y La Unión")
        self.assertEqual(with_extra.additional_affected_areas, "Roldanillo y La Unión")

    def test_create_command_rejects_additional_affected_areas_over_500_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "additional_affected_areas"):
            self.command(additional_affected_areas="a" * 501)

    def test_create_command_accepts_missing_or_valid_important_links(self) -> None:
        without_links = self.command()
        self.assertEqual(without_links.important_links, ())

        with_links = self.command(
            important_links=("https://example.com/ayuda", "http://otro.example.co")
        )
        self.assertEqual(
            with_links.important_links,
            ("https://example.com/ayuda", "http://otro.example.co"),
        )

    def test_create_command_rejects_important_link_with_disallowed_scheme(self) -> None:
        with self.assertRaisesRegex(ValueError, "important_links"):
            self.command(important_links=("javascript:alert(1)",))

    def test_create_command_rejects_important_link_blank_after_strip(self) -> None:
        with self.assertRaisesRegex(ValueError, "important_links"):
            self.command(important_links=("   ",))

    def test_create_command_rejects_important_link_over_500_characters(self) -> None:
        overly_long = "https://example.com/" + ("a" * 490)
        with self.assertRaisesRegex(ValueError, "important_links"):
            self.command(important_links=(overly_long,))

    def test_create_command_rejects_empty_location_fields(self) -> None:
        for field in ("address", "affected_city", "affected_department"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.command(**{field: "   "})

    def test_create_command_accepts_missing_affected_city(self) -> None:
        command = self.command(affected_city=None)

        self.assertIsNone(command.affected_city)

    def test_create_command_rejects_blank_affected_city(self) -> None:
        with self.assertRaisesRegex(ValueError, "affected_city"):
            self.command(affected_city="   ")

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

    def test_create_accepts_missing_affected_city_without_membership_validation(self) -> None:
        created = self.service.create_help_point(self.command(affected_city=None)).point

        self.assertIsNone(created.affected_city)
        self.assertEqual(created.affected_department, "Valle del Cauca")
        # "Valle del Cauca" is queried once for the physical city/department check; the
        # affected-city membership check must be skipped entirely when affected_city is None,
        # even though city == affected_department in this fixture.
        self.assertEqual(
            self.location_catalog.queried_departments.count("Valle del Cauca"),
            1,
        )

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

    def test_create_propagates_important_links_to_persisted_point(self) -> None:
        created = self.service.create_help_point(
            self.command(important_links=("https://example.com/ayuda",))
        ).point

        self.assertEqual(created.important_links, ("https://example.com/ayuda",))
        self.assertEqual(
            self.repository.created.important_links, ("https://example.com/ayuda",)
        )

    def test_to_public_exposes_important_links(self) -> None:
        point = self.service.create_help_point(
            self.command(important_links=("https://example.com/ayuda",))
        ).point

        public = self.service.to_public(point)

        self.assertEqual(public.important_links, ("https://example.com/ayuda",))

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
        self.assertEqual(result.coordinator_name, point.coordinator_name)
        self.assertEqual(result.coordinator_contact, point.coordinator_contact)
        public_fields = {field.name for field in dataclasses.fields(result)}
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
            point,
            point.admin_token,
            "  Nuevo nombre  ",
            "  Nueva descripción  ",
            "  Nuevo contacto  ",
        )

        self.assertEqual(updated.name, "Nuevo nombre")
        self.assertEqual(updated.description, "Nueva descripción")
        self.assertEqual(updated.coordinator_contact, "Nuevo contacto")
        self.assertIsNone(updated.additional_affected_areas)
        self.assertEqual(self.repository.updated, updated)
        with self.assertRaisesRegex(PermissionError, "admin token"):
            self.service.update_help_point_info(
                point, "incorrect", "Nombre", "Descripción", "Contacto"
            )
        with self.assertRaisesRegex(ValueError, "description"):
            self.service.update_help_point_info(
                point, point.admin_token, "Nombre", " ", "Contacto"
            )

    def test_updates_info_with_additional_affected_areas_provided(self) -> None:
        point = self.service.create_help_point(self.command()).point

        updated = self.service.update_help_point_info(
            point,
            point.admin_token,
            "Nombre",
            "Descripción",
            "Contacto",
            "  Roldanillo y La Unión  ",
        )

        self.assertEqual(updated.additional_affected_areas, "Roldanillo y La Unión")
        self.assertEqual(self.repository.updated, updated)

    def test_updates_info_normalizes_blank_additional_affected_areas_to_none(self) -> None:
        point = self.service.create_help_point(self.command()).point
        with_extra = self.service.update_help_point_info(
            point, point.admin_token, "Nombre", "Descripción", "Contacto", "Roldanillo"
        )

        cleared = self.service.update_help_point_info(
            with_extra, point.admin_token, "Nombre", "Descripción", "Contacto", "   "
        )

        self.assertIsNone(cleared.additional_affected_areas)
        self.assertEqual(self.repository.updated, cleared)

    def test_updates_info_rejects_additional_affected_areas_over_500_characters(self) -> None:
        point = self.service.create_help_point(self.command()).point

        with self.assertRaisesRegex(ValueError, "additional_affected_areas"):
            self.service.update_help_point_info(
                point, point.admin_token, "Nombre", "Descripción", "Contacto", "a" * 501
            )

    def test_create_commitment_persists_trimmed_name_and_note_for_a_needs_help_need(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id

        result = self.service.create_commitment(need_id, "  Ana  ", "  Voy para allá.  ")

        self.assertEqual(self.repository.created_commitment_args, (need_id, "Ana", "Voy para allá."))
        self.assertEqual(result.id, need_id)
        self.assertEqual(len(result.commitments), 1)
        commitment = result.commitments[0]
        self.assertEqual(commitment.need_id, need_id)
        self.assertEqual(commitment.name, "Ana")
        self.assertEqual(commitment.note, "Voy para allá.")
        self.assertTrue(commitment.active)

    def test_create_commitment_increments_active_commitment_count_from_zero(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id
        self.assertEqual(point.needs[0].active_commitment_count, 0)

        result = self.service.create_commitment(need_id, "Ana", None)

        self.assertEqual(result.active_commitment_count, 1)

    def test_create_commitment_increments_active_commitment_count_from_existing_value(
        self,
    ) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id
        first_commitment = self.service.create_commitment(need_id, "Ana", None)
        self.assertEqual(first_commitment.active_commitment_count, 1)
        point_with_one_commitment = dataclasses.replace(
            point,
            needs=(first_commitment, *point.needs[1:]),
        )
        self.repository.point_by_need_id = point_with_one_commitment

        second_commitment = self.service.create_commitment(need_id, "Luis", None)

        self.assertEqual(second_commitment.active_commitment_count, 2)
        self.assertEqual(len(second_commitment.commitments), 2)

    def test_create_commitment_on_needs_help_need_transitions_to_help_on_the_way_and_persists(
        self,
    ) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id
        self.assertEqual(point.needs[0].status, NeedStatus.NEEDS_HELP)

        result = self.service.create_commitment(need_id, "Ana", None)

        self.assertEqual(result.status, NeedStatus.HELP_ON_THE_WAY)
        self.assertIsNotNone(self.repository.updated)
        persisted_need = next(need for need in self.repository.updated.needs if need.id == need_id)
        self.assertEqual(persisted_need.status, NeedStatus.HELP_ON_THE_WAY)
        self.assertEqual(len(persisted_need.commitments), 1)

    def test_create_commitment_accepts_missing_note_and_normalizes_blank_note_to_none(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id

        self.service.create_commitment(need_id, "Ana", None)
        self.assertEqual(self.repository.created_commitment_args, (need_id, "Ana", None))

        self.service.create_commitment(need_id, "Ana", "   ")
        self.assertEqual(self.repository.created_commitment_args, (need_id, "Ana", None))

    def test_create_commitment_rejects_covered_need(self) -> None:
        point = self.service.create_help_point(self.command()).point
        need_id = point.needs[0].id
        covered = self.service.change_need_status(
            point, point.admin_token, need_id, NeedStatus.COVERED
        )
        self.repository.point_by_need_id = covered
        updated_after_status_change = self.repository.updated

        with self.assertRaisesRegex(ValueError, "covered"):
            self.service.create_commitment(need_id, "Ana", None)

        self.assertIsNone(self.repository.created_commitment_args)
        self.assertIs(self.repository.updated, updated_after_status_change)

    def test_create_commitment_on_help_on_the_way_need_keeps_status_and_skips_persistence(
        self,
    ) -> None:
        point = self.service.create_help_point(self.command()).point
        need_id = point.needs[0].id
        in_progress = self.service.change_need_status(
            point, point.admin_token, need_id, NeedStatus.HELP_ON_THE_WAY
        )
        self.repository.point_by_need_id = in_progress
        updated_after_status_change = self.repository.updated

        result = self.service.create_commitment(need_id, "Ana", None)

        self.assertEqual(self.repository.created_commitment_args, (need_id, "Ana", None))
        self.assertEqual(result.status, NeedStatus.HELP_ON_THE_WAY)
        self.assertEqual(len(result.commitments), 1)
        self.assertIs(self.repository.updated, updated_after_status_change)

    def test_create_commitment_rejects_unknown_need_id(self) -> None:
        self.repository.point_by_need_id = None

        with self.assertRaisesRegex(ValueError, "need not found"):
            self.service.create_commitment(uuid4(), "Ana", None)

    def test_create_commitment_rejects_need_belonging_to_an_inactive_point(self) -> None:
        point = self.service.create_help_point(self.command()).point
        need_id = point.needs[0].id
        inactive_point = self.service.deactivate_help_point(point, point.admin_token)
        self.repository.point_by_need_id = inactive_point

        with self.assertRaisesRegex(ValueError, "need not found"):
            self.service.create_commitment(need_id, "Ana", None)

    def test_create_commitment_rejects_need_id_missing_from_returned_point(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point

        with self.assertRaisesRegex(ValueError, "need not found"):
            self.service.create_commitment(uuid4(), "Ana", None)

    def test_create_commitment_requires_a_name_and_enforces_max_lengths(self) -> None:
        point = self.service.create_help_point(self.command()).point
        self.repository.point_by_need_id = point
        need_id = point.needs[0].id

        with self.assertRaisesRegex(ValueError, "name"):
            self.service.create_commitment(need_id, "   ", None)
        with self.assertRaisesRegex(ValueError, "name"):
            self.service.create_commitment(need_id, "a" * 121, None)
        with self.assertRaisesRegex(ValueError, "note"):
            self.service.create_commitment(need_id, "Ana", "a" * 501)

    def test_to_public_never_exposes_commitments_even_when_need_has_some(self) -> None:
        point = self.service.create_help_point(self.command()).point
        commitment = Commitment(
            id=uuid4(),
            need_id=point.needs[0].id,
            name="Ana",
            note="Voy para allá.",
            active=True,
            created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        point_with_commitment = dataclasses.replace(
            point,
            needs=(dataclasses.replace(point.needs[0], commitments=(commitment,)),),
        )

        public = self.service.to_public(point_with_commitment)

        self.assertEqual(public.needs[0].commitments, ())
        public_fields = {field.name for field in dataclasses.fields(public.needs[0])}
        self.assertIn("commitments", public_fields)

    def test_to_public_keeps_active_commitment_count_while_hiding_commitments(self) -> None:
        point = self.service.create_help_point(self.command()).point
        point_with_count = dataclasses.replace(
            point,
            needs=(
                dataclasses.replace(point.needs[0], active_commitment_count=3),
            ),
        )

        public = self.service.to_public(point_with_count)

        self.assertEqual(public.needs[0].commitments, ())
        self.assertEqual(public.needs[0].active_commitment_count, 3)


if __name__ == "__main__":
    unittest.main()
