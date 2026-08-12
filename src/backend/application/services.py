from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
import secrets
from typing import Protocol
from uuid import UUID, uuid4

from backend.domain.emergency_scope import AFFECTED_DEPARTMENTS
from backend.domain.models import (
    Commitment,
    CreateHelpPoint,
    CreatedHelpPoint,
    HelpPoint,
    HelpPointCategory,
    HelpPointLocation,
    Need,
    NeedStatus,
    NewHelpPointLocation,
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

    def get_help_point_by_need_id(self, need_id: UUID) -> HelpPoint | None: ...

    def create_custom_category(self, name: str) -> UUID: ...

    def create_commitment(self, need_id: UUID, name: str, note: str | None) -> Need: ...


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
        affected_city = (
            command.affected_city.strip() if command.affected_city is not None else ""
        ) or None
        affected_department = command.affected_department.strip()
        if affected_department not in AFFECTED_DEPARTMENTS:
            raise ValueError("affected department is outside active emergency scope")
        for location in command.locations:
            city = location.city.strip()
            department = location.department.strip()
            if city not in self._location_catalog.list_localities(department):
                raise ValueError("city does not belong to department")
        if affected_city is not None and affected_city not in (
            self._location_catalog.list_localities(affected_department)
        ):
            raise ValueError("affected city does not belong to affected department")
        token = secrets.token_urlsafe(32)
        needs = tuple(
            Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP)
            for category_id in command.category_ids
        )
        locations = tuple(
            HelpPointLocation(
                id=uuid4(),
                address=location.address.strip(),
                city=location.city.strip(),
                department=location.department.strip(),
                latitude=location.latitude,
                longitude=location.longitude,
            )
            for location in command.locations
        )
        point = HelpPoint(
            id=uuid4(),
            name=command.name.strip(),
            description=command.description.strip(),
            affected_city=affected_city,
            affected_department=affected_department,
            locations=locations,
            coordinator_name=command.coordinator_name.strip(),
            coordinator_contact=command.coordinator_contact.strip(),
            admin_token=token,
            active=True,
            needs=needs,
            category=command.category,
            updated_at=datetime.now(UTC),
            additional_affected_areas=(
                command.additional_affected_areas.strip()
                if command.additional_affected_areas
                else None
            ),
            important_links=command.important_links,
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

    def update_help_point_category(
        self,
        point: HelpPoint,
        admin_token: str,
        category: HelpPointCategory,
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if not isinstance(category, HelpPointCategory):
            raise ValueError("category must be a valid HelpPointCategory")
        return self._repository.update_help_point(replace(point, category=category))

    def update_help_point_links(
        self,
        point: HelpPoint,
        admin_token: str,
        important_links: tuple[str, ...],
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        normalized = tuple(link.strip() for link in important_links if link.strip())
        for link in normalized:
            if not link.startswith(("http://", "https://")):
                raise ValueError("important_links must start with http:// or https://")
            if not 1 <= len(link) <= 500:
                raise ValueError("important_links must be between 1 and 500 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("important_links must be unique")
        return self._repository.update_help_point(replace(point, important_links=normalized))

    def update_help_point_locations(
        self,
        point: HelpPoint,
        admin_token: str,
        locations: tuple[NewHelpPointLocation, ...],
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if not locations:
            raise ValueError("at least one location is required")
        for location in locations:
            validate_required(location.address, "address", 240)
            validate_required(location.city, "city", 120)
            validate_required(location.department, "department", 120)
            if not -90 <= location.latitude <= 90:
                raise ValueError("latitude must be between -90 and 90")
            if not -180 <= location.longitude <= 180:
                raise ValueError("longitude must be between -180 and 180")
        updated = tuple(
            HelpPointLocation(
                id=uuid4(),
                address=location.address.strip(),
                city=location.city.strip(),
                department=location.department.strip(),
                latitude=location.latitude,
                longitude=location.longitude,
            )
            for location in locations
        )
        return self._repository.update_help_point(replace(point, locations=updated))

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

    def create_commitment(self, need_id: UUID, name: str, note: str | None) -> Need:
        point = self._repository.get_help_point_by_need_id(need_id)
        if point is None or not point.active:
            raise ValueError("need not found")
        if not any(n.id == need_id for n in point.needs):
            raise ValueError("need not found")
        normalized_name = name.strip()
        validate_required(normalized_name, "name", 120)
        normalized_note = (note or "").strip() or None
        if normalized_note is not None:
            validate_optional(normalized_note, "note", 500)
        # The "already covered" check and the NEEDS_HELP -> HELP_ON_THE_WAY transition
        # happen atomically inside the repository call (single transaction, row lock),
        # not here: a check-then-act split across two separate transactions would leave
        # a window where a commitment could land on a need the coordinator just covered.
        try:
            self._repository.create_commitment(need_id, normalized_name, normalized_note)
        except KeyError as error:
            raise ValueError("need not found") from error
        refreshed_point = self._repository.get_help_point_by_need_id(need_id)
        if refreshed_point is None:
            raise ValueError("need not found")
        updated_need = next((n for n in refreshed_point.needs if n.id == need_id), None)
        if updated_need is None:
            raise ValueError("need not found")
        return updated_need

    def update_help_point_info(
        self,
        point: HelpPoint,
        admin_token: str,
        name: str,
        description: str,
        coordinator_contact: str,
        additional_affected_areas: str | None = None,
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        normalized_name = name.strip()
        normalized_description = description.strip()
        normalized_contact = coordinator_contact.strip()
        normalized_additional_areas = (
            additional_affected_areas.strip() if additional_affected_areas is not None else ""
        ) or None
        validate_required(normalized_name, "name", 120)
        validate_required(normalized_description, "description", 5_000)
        validate_required(normalized_contact, "coordinator_contact", 240)
        validate_optional(normalized_additional_areas, "additional_affected_areas", 500)
        return self._repository.update_help_point(
            replace(
                point,
                name=normalized_name,
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
            affected_city=point.affected_city,
            affected_department=point.affected_department,
            locations=point.locations,
            coordinator_name=point.coordinator_name,
            coordinator_contact=point.coordinator_contact,
            active=point.active,
            needs=tuple(replace(need, commitments=()) for need in point.needs),
            category=point.category,
            updated_at=point.updated_at,
            additional_affected_areas=point.additional_affected_areas,
            important_links=point.important_links,
        )
