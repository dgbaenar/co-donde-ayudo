from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.domain.models import Commitment, HelpPoint, Need, NeedStatus
from backend.infrastructure.postgres.orm_models import CommitmentRow, HelpPointRow, NeedRow
from backend.infrastructure.postgres.repository import PostgresHelpPointRepository


class Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.rows: dict[UUID, HelpPointRow] = {}
        self.need_rows: dict[UUID, NeedRow] = {}

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
        return None

    def get(self, model, key):
        if model is NeedRow:
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
) -> HelpPoint:
    return HelpPoint(
        id=UUID("00000000-0000-0000-0000-000000000001"), name="Parque", description="Ayuda",
        city="Cali", department="Valle del Cauca", address="Calle 5 # 10-20",
        affected_city=affected_city, affected_department="Valle del Cauca",
        latitude=3.4, longitude=-76.5, coordinator_name="Ana",
        coordinator_contact="Contacto", admin_token="x" * 40, active=True,
        needs=(Need(UUID("00000000-0000-0000-0000-000000000010"), UUID("00000000-0000-0000-0000-000000000100"), NeedStatus.NEEDS_HELP),),
        additional_affected_areas=additional_affected_areas,
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

        result = PostgresHelpPointRepository(Factory(session)).create_commitment(
            need_id, "Ana", None
        )

        self.assertIsNone(result.note)
        self.assertIsNone(session.added[0].nota)


if __name__ == "__main__":
    unittest.main()
