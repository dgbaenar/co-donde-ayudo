from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.domain.models import Commitment, HelpPoint, Need, NeedStatus
from backend.infrastructure.postgres.orm_models import (
    CommitmentRow,
    HelpPointRow,
    NeedCategoryRow,
    NeedRow,
)


class PostgresHelpPointRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_help_point(self, point: HelpPoint) -> HelpPoint:
        with self._session_factory() as session:
            with session.begin():
                session.add(self._row_from_point(point))
        return point

    def update_help_point(self, point: HelpPoint) -> HelpPoint:
        with self._session_factory() as session:
            with session.begin():
                row = session.get(HelpPointRow, point.id)
                if row is None:
                    raise KeyError(point.id)
                self._apply_point(row, point)
                existing = {need.category_id: need for need in row.needs}
                desired = {need.category_id: need for need in point.needs}
                for category_id, need_row in existing.items():
                    if category_id not in desired:
                        session.delete(need_row)
                    else:
                        need_row.estado = desired[category_id].status.value
                for category_id, need in desired.items():
                    if category_id not in existing:
                        row.needs.append(NeedRow(id=need.id, category_id=category_id, estado=need.status.value))
        return point

    def list_active_categories(self) -> dict[str, UUID]:
        with self._session_factory() as session:
            rows = session.scalars(select(NeedCategoryRow).where(NeedCategoryRow.activo.is_(True))).all()
        return {row.nombre: row.id for row in rows}

    def list_active_help_points(self) -> tuple[HelpPoint, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(HelpPointRow).where(HelpPointRow.activo.is_(True))).all()
            return tuple(self._point_from_row(row) for row in rows)

    def get_help_point_by_admin_token(self, admin_token: str) -> HelpPoint | None:
        with self._session_factory() as session:
            row = session.scalars(select(HelpPointRow).where(HelpPointRow.admin_token == admin_token)).first()
            return None if row is None else self._point_from_row(row)

    def get_help_point_by_need_id(self, need_id: UUID) -> HelpPoint | None:
        with self._session_factory() as session:
            need_row = session.get(NeedRow, need_id)
            return None if need_row is None else self._point_from_row(need_row.help_point)

    def create_commitment(self, need_id: UUID, name: str, note: str | None) -> Commitment:
        with self._session_factory() as session:
            with session.begin():
                row = CommitmentRow(
                    id=uuid4(),
                    need_id=need_id,
                    nombre=name,
                    nota=note,
                    activo=True,
                    created_at=datetime.now(UTC),
                )
                session.add(row)
            return Commitment(
                id=row.id,
                need_id=row.need_id,
                name=row.nombre,
                note=row.nota,
                active=row.activo,
                created_at=row.created_at,
            )

    def create_custom_category(self, name: str) -> UUID:
        with self._session_factory() as session:
            with session.begin():
                row = NeedCategoryRow(nombre=name, grupo="Otros", es_global=False, activo=True)
                session.add(row)
                session.flush()
                return row.id

    @staticmethod
    def _row_from_point(point: HelpPoint) -> HelpPointRow:
        row = HelpPointRow(id=point.id)
        PostgresHelpPointRepository._apply_point(row, point)
        row.needs = [NeedRow(id=need.id, category_id=need.category_id, estado=need.status.value) for need in point.needs]
        return row

    @staticmethod
    def _apply_point(row: HelpPointRow, point: HelpPoint) -> None:
        row.nombre = point.name
        row.descripcion = point.description
        row.ciudad = point.city
        row.departamento = point.department
        row.direccion = point.address
        row.ciudad_afectada = point.affected_city
        row.departamento_afectado = point.affected_department
        row.zonas_adicionales = point.additional_affected_areas
        row.latitude = point.latitude
        row.longitude = point.longitude
        row.nombre_coordinador = point.coordinator_name
        row.contacto_coordinador = point.coordinator_contact
        row.admin_token = point.admin_token
        row.activo = point.active

    @staticmethod
    def _point_from_row(row: HelpPointRow) -> HelpPoint:
        return HelpPoint(
            id=row.id,
            name=row.nombre,
            description=row.descripcion,
            city=row.ciudad,
            department=row.departamento,
            address=row.direccion,
            affected_city=row.ciudad_afectada,
            affected_department=row.departamento_afectado,
            additional_affected_areas=row.zonas_adicionales,
            latitude=row.latitude,
            longitude=row.longitude,
            coordinator_name=row.nombre_coordinador,
            coordinator_contact=row.contacto_coordinador,
            admin_token=row.admin_token,
            active=row.activo,
            needs=tuple(
                Need(
                    id=need.id,
                    category_id=need.category_id,
                    status=NeedStatus(need.estado),
                    commitments=tuple(
                        Commitment(
                            id=commitment.id,
                            need_id=commitment.need_id,
                            name=commitment.nombre,
                            note=commitment.nota,
                            active=commitment.activo,
                            created_at=commitment.created_at,
                        )
                        for commitment in need.commitments
                    ),
                    active_commitment_count=sum(
                        1 for commitment in need.commitments if commitment.activo
                    ),
                )
                for need in row.needs
            ),
        )
