from __future__ import annotations

import unittest
from dataclasses import replace
from uuid import UUID

from backend.domain.models import HelpPoint, Need, NeedStatus
from backend.infrastructure.postgres.orm_models import HelpPointRow, NeedRow
from backend.infrastructure.postgres.repository import PostgresHelpPointRepository


class Session:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.rows: dict[UUID, HelpPointRow] = {}

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
        return self.rows.get(key)


class Factory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(self) -> Session:
        return self.session


def point(additional_affected_areas: str | None = None) -> HelpPoint:
    return HelpPoint(
        id=UUID("00000000-0000-0000-0000-000000000001"), name="Parque", description="Ayuda",
        city="Cali", department="Valle del Cauca", address="Calle 5 # 10-20",
        affected_city="Roldanillo", affected_department="Valle del Cauca",
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


if __name__ == "__main__":
    unittest.main()
