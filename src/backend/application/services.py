from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import secrets
from typing import Protocol
from uuid import UUID, uuid4

from backend.domain.emergency_scope import AFFECTED_DEPARTMENTS
from backend.domain.models import (
    CreateHelpPoint,
    CreatedHelpPoint,
    HelpPoint,
    Need,
    NeedStatus,
    PublicHelpPoint,
    validate_optional,
    validate_required,
)


class HelpPointRepository(Protocol):
    def create_help_point(self, point: HelpPoint) -> HelpPoint: ...

    def update_help_point(self, point: HelpPoint) -> HelpPoint: ...

    def list_active_categories(self) -> Mapping[str, UUID]: ...

    def list_active_help_points(self) -> tuple[HelpPoint, ...]: ...

    def get_help_point_by_admin_token(self, admin_token: str) -> HelpPoint | None: ...

    def create_custom_category(self, name: str) -> UUID: ...


class LocationCatalog(Protocol):
    def list_localities(self, department: str) -> tuple[str, ...]: ...


class HelpPointService:
    def __init__(
        self,
        repository: HelpPointRepository,
        location_catalog: LocationCatalog,
    ) -> None:
        self._repository = repository
        self._location_catalog = location_catalog

    def create_help_point(self, command: CreateHelpPoint) -> CreatedHelpPoint:
        city = command.city.strip()
        department = command.department.strip()
        affected_city = command.affected_city.strip()
        affected_department = command.affected_department.strip()
        if affected_department not in AFFECTED_DEPARTMENTS:
            raise ValueError("affected department is outside active emergency scope")
        if city not in self._location_catalog.list_localities(department):
            raise ValueError("city does not belong to department")
        if affected_city not in self._location_catalog.list_localities(
            affected_department
        ):
            raise ValueError("affected city does not belong to affected department")
        token = secrets.token_urlsafe(32)
        needs = tuple(
            Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP)
            for category_id in command.category_ids
        )
        point = HelpPoint(
            id=uuid4(),
            name=command.name.strip(),
            description=command.description.strip(),
            city=city,
            department=department,
            address=command.address.strip(),
            affected_city=affected_city,
            affected_department=affected_department,
            latitude=command.latitude,
            longitude=command.longitude,
            coordinator_name=command.coordinator_name.strip(),
            coordinator_contact=command.coordinator_contact.strip(),
            admin_token=token,
            active=True,
            needs=needs,
            additional_affected_areas=(
                command.additional_affected_areas.strip()
                if command.additional_affected_areas
                else None
            ),
        )
        created = self._repository.create_help_point(point)
        return CreatedHelpPoint(point=created, admin_token=token)

    def add_need(self, point: HelpPoint, admin_token: str, category_id: UUID) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if any(need.category_id == category_id for need in point.needs):
            raise ValueError("category already exists")
        updated = replace(
            point,
            needs=(*point.needs, Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP)),
        )
        return self._repository.update_help_point(updated)

    def remove_need(self, point: HelpPoint, admin_token: str, need_id: UUID) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        needs = tuple(need for need in point.needs if need.id != need_id)
        if len(needs) == len(point.needs):
            raise ValueError("need does not exist")
        return self._repository.update_help_point(replace(point, needs=needs))

    def change_need_status(
        self,
        point: HelpPoint,
        admin_token: str,
        need_id: UUID,
        status: NeedStatus,
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if not any(need.id == need_id for need in point.needs):
            raise ValueError("need does not exist")
        needs = tuple(
            replace(need, status=status) if need.id == need_id else need for need in point.needs
        )
        return self._repository.update_help_point(replace(point, needs=needs))

    def deactivate_help_point(self, point: HelpPoint, admin_token: str) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        return self._repository.update_help_point(replace(point, active=False))

    def list_active_categories(self) -> Mapping[str, UUID]:
        return self._repository.list_active_categories()

    def list_active_help_points(self) -> tuple[PublicHelpPoint, ...]:
        return tuple(self.to_public(point) for point in self._repository.list_active_help_points())

    def get_public_help_point(self, point_id: UUID) -> PublicHelpPoint | None:
        for point in self._repository.list_active_help_points():
            if point.id == point_id and point.active:
                return self.to_public(point)
        return None

    def get_managed_help_point(self, admin_token: str) -> HelpPoint:
        if not admin_token:
            raise PermissionError("invalid admin token")
        point = self._repository.get_help_point_by_admin_token(admin_token)
        if point is None:
            raise PermissionError("invalid admin token")
        return point

    def create_custom_category(self, name: str) -> UUID:
        normalized_name = name.strip()
        validate_required(normalized_name, "name", 120)
        return self._repository.create_custom_category(normalized_name)

    def update_help_point_info(
        self,
        point: HelpPoint,
        admin_token: str,
        description: str,
        coordinator_contact: str,
        additional_affected_areas: str | None = None,
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        normalized_description = description.strip()
        normalized_contact = coordinator_contact.strip()
        normalized_additional_areas = (
            additional_affected_areas.strip() if additional_affected_areas is not None else ""
        ) or None
        validate_required(normalized_description, "description", 1_000)
        validate_required(normalized_contact, "coordinator_contact", 240)
        validate_optional(normalized_additional_areas, "additional_affected_areas", 500)
        return self._repository.update_help_point(
            replace(
                point,
                description=normalized_description,
                coordinator_contact=normalized_contact,
                additional_affected_areas=normalized_additional_areas,
            )
        )

    def _require_admin_token(self, point: HelpPoint, admin_token: str) -> None:
        if not self.verify_admin_token(point.admin_token, admin_token):
            raise PermissionError("invalid admin token")

    @staticmethod
    def verify_admin_token(expected: str, provided: str) -> bool:
        if not expected or not provided:
            return False
        return secrets.compare_digest(expected, provided)

    @staticmethod
    def to_public(point: HelpPoint) -> PublicHelpPoint:
        return PublicHelpPoint(
            id=point.id,
            name=point.name,
            description=point.description,
            city=point.city,
            department=point.department,
            address=point.address,
            affected_city=point.affected_city,
            affected_department=point.affected_department,
            latitude=point.latitude,
            longitude=point.longitude,
            active=point.active,
            needs=point.needs,
            additional_affected_areas=point.additional_affected_areas,
        )
