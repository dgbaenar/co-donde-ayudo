from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.domain.models import Commitment, HelpPoint, Need, NeedStatus
from backend.infrastructure.postgres.orm_models import CommitmentRow, HelpPointRow, NeedRow
from backend.infrastructure.postgres.repository import PostgresHelpPointRepository

FIXED_UPDATED_AT = datetime(2026, 8, 12, tzinfo=UTC)


class Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.rows: dict[UUID, HelpPointRow] = {}
        self.need_rows: dict[UUID, NeedRow] = {}
        self.locked_for_update: dict[UUID, bool] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def begin(self):
        return self

    def add(self, row: object) -> None:
        self.added.append(row)

    def delete(self, row: object) -> None:
        self.deleted.append(row)

    def flush(self) -> None:
        for row in self.added:
            if isinstance(row, HelpPointRow):
                row.updated_at = FIXED_UPDATED_AT
        for row in self.rows.values():
            if isinstance(row, HelpPointRow):
                row.updated_at = FIXED_UPDATED_AT

    def get(self, model, key, with_for_update=False):
        if model is NeedRow:
            self.locked_for_update[key] = with_for_update
            return self.need_rows.get(key)
        return self.rows.get(key)


class Factory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def point(
    additional_affected_areas: str | None = None,
    affected_city: str | None = "Roldanillo",
    important_links: tuple[str, ...] = (),
) -> HelpPoint:
    return HelpPoint(
        id=UUID("00000000-0000-0000-0000-000000000001"), name="Parque", description="Ayuda",
        city="Cali", department="Valle del Cauca", address="Calle 5 # 10-20",
        affected_city=affected_city, affected_department="Valle del Cauca",
        latitude=3.4, longitude=-76.5, coordinator_name="Ana",
        coordinator_contact="Contacto", admin_token="x" * 40, active=True,
        needs=(Need(UUID("00000000-0000-0000-0000-000000000010"), UUID("00000000-0000-0000-0000-000000000100"), NeedStatus.NEEDS_HELP),),
        updated_at=FIXED_UPDATED_AT,
        additional_affected_areas=additional_affected_areas,
        important_links=important_links,
    )


class RepositoryTests(unittest.TestCase):
    def test_create_adds_orm_point_with_needs_in_session_transaction(self) -> None:
        session = Session()
        result = PostgresHelpPointRepository(Factory(session)).create_help_point(point())

        self.assertEqual(result, point())
        self.assertIsInstance(session.added[0], HelpPointRow)
        self.assertEqual(len(session.added[0].needs), 1)
        self.assertEqual(session.added[0].direccion, "Calle 5 # 10-20")
        self.assertEqual(session.added[0].ciudad_afectada, "Roldanillo")
        self.assertEqual(session.added[0].departamento_afectado, "Valle del Cauca")
        restored = PostgresHelpPointRepository._point_from_row(session.added[0])
        self.assertEqual(restored.address, point().address)
        self.assertEqual(restored.affected_city, point().affected_city)
        self.assertEqual(restored.affected_department, point().affected_department)

    def test_create_round_trips_additional_affected_areas_when_present(self) -> None:
        session = Session()
        source = point(additional_affected_areas="Roldanillo y La Unión")
        PostgresHelpPointRepository(Factory(session)).create_help_point(source)

        row = session.added[0]
        self.assertEqual(row.zonas_adicionales, "Roldanillo y La Unión")
        restored = PostgresHelpPointRepository._point_from_row(row)
        self.assertEqual(restored.additional_affected_areas, "Roldanillo y La Unión")

    def test_create_round_trips_additional_affected_areas_when_none(self) -> None:
        session = Session()
        source = point(additional_affected_areas=None)
        PostgresHelpPointRepository(Factory(session)).create_help_point(source)

        row = session.added[0]
        self.assertIsNone(row.zonas_adicionales)
        restored = PostgresHelpPointRepository._point_from_row(row)
        self.assertIsNone(restored.additional_affected_areas)

    def test_create_round_trips_important_links_when_present(self) -> None:
        session = Session()
        source = point(important_links=("https://example.com/ayuda", "http://otro.example.co"))
        PostgresHelpPointRepository(Factory(session)).create_help_point(source)

        row = session.added[0]
        self.assertEqual(
            row.enlaces_importantes,
            ["https://example.com/ayuda", "http://otro.example.co"],
        )
        restored = PostgresHelpPointRepository._point_from_row(row)
        self.assertEqual(
            restored.important_links,
            ("https://example.com/ayuda", "http://otro.example.co"),
        )

    def test_create_round_trips_important_links_when_empty(self) -> None:
        session = Session()
        source = point(important_links=())
        PostgresHelpPointRepository(Factory(session)).create_help_point(source)

        row = session.added[0]
        self.assertEqual(row.enlaces_importantes, [])
        restored = PostgresHelpPointRepository._point_from_row(row)
        self.assertEqual(restored.important_links, ())

    def test_create_round_trips_affected_city_when_none(self) -> None:
        session = Session()
        source = point(affected_city=None)
        PostgresHelpPointRepository(Factory(session)).create_help_point(source)

        row = session.added[0]
        self.assertIsNone(row.ciudad_afectada)
        restored = PostgresHelpPointRepository._point_from_row(row)
        self.assertIsNone(restored.affected_city)
        self.assertEqual(restored.affected_department, "Valle del Cauca")

    def test_update_changes_existing_need_without_deleting_it(self) -> None:
        original = point()
        existing = PostgresHelpPointRepository._row_from_point(original)
        existing_need = existing.needs[0]
        session = Session()
        session.rows[original.id] = existing
        updated = replace(
            original,
            needs=(replace(original.needs[0], status=NeedStatus.COVERED),),
        )

        result = PostgresHelpPointRepository(Factory(session)).update_help_point(updated)

        self.assertEqual(result, updated)
        self.assertIs(existing.needs[0], existing_need)
        self.assertEqual(existing_need.estado, NeedStatus.COVERED.value)
        self.assertEqual(session.deleted, [])

    def test_point_from_row_maps_commitments_onto_their_need(self) -> None:
        original = point()
        row = PostgresHelpPointRepository._row_from_point(original)
        commitment_row = CommitmentRow(
            id=uuid4(),
            need_id=row.needs[0].id,
            nombre="Ana",
            nota="Voy para allá.",
            activo=True,
            created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        row.needs[0].commitments = [commitment_row]

        restored = PostgresHelpPointRepository._point_from_row(row)

        self.assertEqual(len(restored.needs[0].commitments), 1)
        commitment = restored.needs[0].commitments[0]
        self.assertEqual(commitment.id, commitment_row.id)
        self.assertEqual(commitment.need_id, row.needs[0].id)
        self.assertEqual(commitment.name, "Ana")
        self.assertEqual(commitment.note, "Voy para allá.")
        self.assertTrue(commitment.active)
        self.assertEqual(commitment.created_at, commitment_row.created_at)

    def test_point_from_row_defaults_to_no_commitments(self) -> None:
        row = PostgresHelpPointRepository._row_from_point(point())

        restored = PostgresHelpPointRepository._point_from_row(row)

        self.assertEqual(restored.needs[0].commitments, ())
        self.assertEqual(restored.needs[0].active_commitment_count, 0)

    def test_point_from_row_counts_only_active_commitments(self) -> None:
        original = point()
        row = PostgresHelpPointRepository._row_from_point(original)
        active_one = CommitmentRow(
            id=uuid4(), need_id=row.needs[0].id, nombre="Ana", nota=None,
            activo=True, created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        active_two = CommitmentRow(
            id=uuid4(), need_id=row.needs[0].id, nombre="Luis", nota=None,
            activo=True, created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        inactive = CommitmentRow(
            id=uuid4(), need_id=row.needs[0].id, nombre="Carlos", nota=None,
            activo=False, created_at=datetime(2026, 8, 11, tzinfo=UTC),
        )
        row.needs[0].commitments = [active_one, active_two, inactive]

        restored = PostgresHelpPointRepository._point_from_row(row)

        self.assertEqual(len(restored.needs[0].commitments), 3)
        self.assertEqual(restored.needs[0].active_commitment_count, 2)

    def test_get_help_point_by_need_id_returns_full_point_when_need_exists(self) -> None:
        original = point()
        row = PostgresHelpPointRepository._row_from_point(original)
        row.updated_at = FIXED_UPDATED_AT
        session = Session()
        session.need_rows[row.needs[0].id] = row.needs[0]
        row.needs[0].help_point = row

        result = PostgresHelpPointRepository(Factory(session)).get_help_point_by_need_id(
            row.needs[0].id
        )

        self.assertEqual(result, original)

    def test_get_help_point_by_need_id_returns_none_when_need_is_missing(self) -> None:
        session = Session()

        result = PostgresHelpPointRepository(Factory(session)).get_help_point_by_need_id(uuid4())

        self.assertIsNone(result)

    def test_create_commitment_inserts_row_and_returns_domain_commitment(self) -> None:
        session = Session()
        need_id = uuid4()
        session.need_rows[need_id] = NeedRow(
            id=need_id, help_point_id=uuid4(), category_id=uuid4(), estado="NEEDS_HELP"
        )

        result = PostgresHelpPointRepository(Factory(session)).create_commitment(
            need_id, "Ana", "Voy para allá."
        )

        self.assertEqual(len(session.added), 1)
        row = session.added[0]
        self.assertIsInstance(row, CommitmentRow)
        self.assertEqual(row.need_id, need_id)
        self.assertEqual(row.nombre, "Ana")
        self.assertEqual(row.nota, "Voy para allá.")
        self.assertTrue(row.activo)
        self.assertEqual(result, Commitment(
            id=row.id,
            need_id=need_id,
            name="Ana",
            note="Voy para allá.",
            active=True,
            created_at=row.created_at,
        ))

    def test_create_commitment_accepts_missing_note(self) -> None:
        session = Session()
        need_id = uuid4()
        session.need_rows[need_id] = NeedRow(
            id=need_id, help_point_id=uuid4(), category_id=uuid4(), estado="NEEDS_HELP"
        )

        result = PostgresHelpPointRepository(Factory(session)).create_commitment(
            need_id, "Ana", None
        )

        self.assertIsNone(result.note)
        self.assertIsNone(session.added[0].nota)

    def test_create_commitment_rejects_unknown_need(self) -> None:
        session = Session()
        need_id = uuid4()

        with self.assertRaises(KeyError):
            PostgresHelpPointRepository(Factory(session)).create_commitment(
                need_id, "Ana", None
            )

        self.assertEqual(session.added, [])

    def test_create_commitment_rejects_covered_need_atomically(self) -> None:
        session = Session()
        need_id = uuid4()
        session.need_rows[need_id] = NeedRow(
            id=need_id, help_point_id=uuid4(), category_id=uuid4(), estado="COVERED"
        )

        with self.assertRaisesRegex(ValueError, "covered"):
            PostgresHelpPointRepository(Factory(session)).create_commitment(
                need_id, "Ana", None
            )

        self.assertEqual(session.added, [])

    def test_create_commitment_on_needs_help_row_locks_and_advances_status(self) -> None:
        session = Session()
        need_id = uuid4()
        need_row = NeedRow(
            id=need_id, help_point_id=uuid4(), category_id=uuid4(), estado="NEEDS_HELP"
        )
        session.need_rows[need_id] = need_row

        PostgresHelpPointRepository(Factory(session)).create_commitment(
            need_id, "Ana", None
        )

        self.assertEqual(need_row.estado, "HELP_ON_THE_WAY")
        self.assertTrue(session.locked_for_update[need_id])

    def test_update_help_point_returns_fresh_updated_at(self) -> None:
        original = point()
        existing = PostgresHelpPointRepository._row_from_point(original)
        old_time = datetime(2026, 1, 1, tzinfo=UTC)
        existing.updated_at = old_time
        session = Session()
        session.rows[original.id] = existing
        updated = replace(original, name="Nuevo nombre")

        result = PostgresHelpPointRepository(Factory(session)).update_help_point(updated)

        # flush() should update the row's timestamp, and the returned point
        # must carry the new value, not the one the row had before the update.
        self.assertNotEqual(result.updated_at, old_time)
        self.assertEqual(result.updated_at, FIXED_UPDATED_AT)

    def test_create_commitment_on_help_on_the_way_row_keeps_status(self) -> None:
        session = Session()
        need_id = uuid4()
        need_row = NeedRow(
            id=need_id, help_point_id=uuid4(), category_id=uuid4(), estado="HELP_ON_THE_WAY"
        )
        session.need_rows[need_id] = need_row

        PostgresHelpPointRepository(Factory(session)).create_commitment(
            need_id, "Ana", None
        )

        self.assertEqual(need_row.estado, "HELP_ON_THE_WAY")


if __name__ == "__main__":
    unittest.main()
