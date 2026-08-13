from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from backend.domain.models import (
    AffectedArea,
    Commitment,
    HelpPoint,
    HelpPointCategory,
    HelpPointLocation,
    Need,
    NeedStatus,
)
from backend.infrastructure.postgres.orm_models import (
    CommitmentRow,
    HelpPointAffectedAreaRow,
    HelpPointLocationRow,
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
                row = self._row_from_point(point)
                session.add(row)
                session.flush()
                return replace(point, created_at=row.created_at, updated_at=row.updated_at)

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
                existing_locations = {location.id: location for location in row.locations}
                desired_locations = {location.id: location for location in point.locations}
                for location_id, location_row in existing_locations.items():
                    if location_id not in desired_locations:
                        session.delete(location_row)
                    else:
                        location_row.direccion = desired_locations[location_id].address
                        location_row.ciudad = desired_locations[location_id].city
                        location_row.departamento = desired_locations[location_id].department
                        location_row.latitude = desired_locations[location_id].latitude
                        location_row.longitude = desired_locations[location_id].longitude
                for location_id, location in desired_locations.items():
                    if location_id not in existing_locations:
                        row.locations.append(
                            HelpPointLocationRow(
                                id=location.id,
                                direccion=location.address,
                                ciudad=location.city,
                                departamento=location.department,
                                latitude=location.latitude,
                                longitude=location.longitude,
                            )
                        )
                existing_areas = {
                    (area.departamento, area.municipio): area for area in row.affected_areas
                }
                desired_areas = {
                    (area.department, area.city): area for area in point.affected_areas
                }
                for area_key, area_row in existing_areas.items():
                    if area_key not in desired_areas:
                        session.delete(area_row)
                for area_key in desired_areas:
                    if area_key not in existing_areas:
                        department, city = area_key
                        row.affected_areas.append(
                            HelpPointAffectedAreaRow(
                                id=uuid4(), departamento=department, municipio=city
                            )
                        )
                session.flush()
                return replace(point, updated_at=row.updated_at)

    def list_active_categories(self) -> dict[str, UUID]:
        with self._session_factory() as session:
            rows = session.scalars(select(NeedCategoryRow).where(NeedCategoryRow.activo.is_(True))).all()
        return {row.nombre: row.id for row in rows}

    def list_active_help_points(self) -> tuple[HelpPoint, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(HelpPointRow)
                .where(HelpPointRow.activo.is_(True))
                .order_by(HelpPointRow.created_at.desc())
            ).all()
            return tuple(self._point_from_row(row) for row in rows)

    def get_active_help_point_by_id(self, point_id: UUID) -> HelpPoint | None:
        statement = (
            select(HelpPointRow)
            .where(
                HelpPointRow.id == point_id,
                HelpPointRow.activo.is_(True),
            )
            .options(
                selectinload(HelpPointRow.affected_areas),
                selectinload(HelpPointRow.locations),
                selectinload(HelpPointRow.needs).selectinload(NeedRow.commitments),
            )
        )
        with self._session_factory() as session:
            row = session.scalars(statement).first()
            return None if row is None else self._point_from_row(row)

    def open_active_help_points_snapshot(self) -> tuple[datetime, int]:
        with self._session_factory() as session:
            snapshot_created_at = session.scalar(select(func.now()))
            if snapshot_created_at is None:
                raise RuntimeError("database did not provide a snapshot timestamp")
            count = session.scalar(
                select(func.count(HelpPointRow.id)).where(
                    HelpPointRow.activo.is_(True),
                    HelpPointRow.created_at <= snapshot_created_at,
                )
            )
        return snapshot_created_at, int(count or 0)

    def list_active_help_points_page(
        self,
        *,
        snapshot_created_at: datetime,
        before_created_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> tuple[HelpPoint, ...]:
        statement = (
            select(HelpPointRow)
            .where(
                HelpPointRow.activo.is_(True),
                HelpPointRow.created_at <= snapshot_created_at,
            )
            .options(
                selectinload(HelpPointRow.affected_areas),
                selectinload(HelpPointRow.locations),
                selectinload(HelpPointRow.needs).selectinload(NeedRow.commitments),
            )
            .order_by(HelpPointRow.created_at.desc(), HelpPointRow.id.desc())
            .limit(limit)
        )
        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    HelpPointRow.created_at < before_created_at,
                    and_(
                        HelpPointRow.created_at == before_created_at,
                        HelpPointRow.id < before_id,
                    ),
                )
            )
        with self._session_factory() as session:
            rows = session.scalars(statement).all()
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
                need_row = session.get(NeedRow, need_id, with_for_update=True)
                if need_row is None:
                    raise KeyError(need_id)
                if need_row.estado == NeedStatus.COVERED.value:
                    raise ValueError("need is already covered")
                row = CommitmentRow(
                    id=uuid4(),
                    need_id=need_id,
                    nombre=name,
                    nota=note,
                    activo=True,
                    created_at=datetime.now(UTC),
                )
                session.add(row)
                if need_row.estado == NeedStatus.NEEDS_HELP.value:
                    # Locking the need row above serializes this against a concurrent
                    # change_need_status(COVERED): either that transaction commits first
                    # (and our check above sees COVERED and raises), or ours commits first
                    # and theirs waits, blocked on the same row, until we're done.
                    need_row.estado = NeedStatus.HELP_ON_THE_WAY.value
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
        row.locations = [
            HelpPointLocationRow(
                id=location.id,
                direccion=location.address,
                ciudad=location.city,
                departamento=location.department,
                latitude=location.latitude,
                longitude=location.longitude,
            )
            for location in point.locations
        ]
        row.affected_areas = [
            HelpPointAffectedAreaRow(id=uuid4(), departamento=area.department, municipio=area.city)
            for area in point.affected_areas
        ]
        return row

    @staticmethod
    def _apply_point(row: HelpPointRow, point: HelpPoint) -> None:
        row.nombre = point.name
        row.descripcion = point.description
        row.zonas_adicionales = point.additional_affected_areas
        row.enlaces_importantes = list(point.important_links)
        row.categoria = point.category.value
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
            affected_areas=tuple(
                AffectedArea(department=area.departamento, city=area.municipio)
                for area in row.affected_areas
            ),
            additional_affected_areas=row.zonas_adicionales,
            important_links=tuple(row.enlaces_importantes),
            category=HelpPointCategory(row.categoria),
            coordinator_name=row.nombre_coordinador,
            coordinator_contact=row.contacto_coordinador,
            admin_token=row.admin_token,
            active=row.activo,
            created_at=row.created_at,
            updated_at=row.updated_at,
            locations=tuple(
                HelpPointLocation(
                    id=location.id,
                    address=location.direccion,
                    city=location.ciudad,
                    department=location.departamento,
                    latitude=location.latitude,
                    longitude=location.longitude,
                )
                for location in row.locations
            ),
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
