from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
import secrets
from typing import Protocol
from uuid import UUID, uuid4

from backend.application.public_cache import (
    CachedPublicHome,
    CachedPublicPoint,
    PublicHelpPointCache,
    RefreshToken,
)
from backend.domain.emergency_scope import AFFECTED_DEPARTMENTS
from backend.domain.models import (
    AffectedArea,
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

    def get_active_help_point_by_id(self, point_id: UUID) -> HelpPoint | None: ...

    def open_active_help_points_snapshot(self) -> tuple[datetime, int]: ...

    def list_active_help_points_page(
        self,
        *,
        snapshot_created_at: datetime,
        before_created_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> tuple[HelpPoint, ...]: ...

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
        *,
        public_cache: PublicHelpPointCache | None = None,
        cache_clock: Callable[[], float] | None = None,
    ) -> None:
        self._repository = repository
        self._location_catalog = location_catalog
        if public_cache is not None and cache_clock is not None:
            raise ValueError("provide public_cache or cache_clock, not both")
        self._public_cache = public_cache or PublicHelpPointCache(
            **({"clock": cache_clock} if cache_clock is not None else {})
        )

    def create_help_point(self, command: CreateHelpPoint) -> CreatedHelpPoint:
        normalized_areas = []
        for area in command.affected_areas:
            department = area.department.strip()
            city = (area.city.strip() if area.city is not None else "") or None
            if department not in AFFECTED_DEPARTMENTS:
                raise ValueError("affected department is outside active emergency scope")
            if city is not None and city not in self._location_catalog.list_localities(
                department
            ):
                raise ValueError("affected city does not belong to affected department")
            normalized_areas.append(AffectedArea(department=department, city=city))
        affected_areas = tuple(normalized_areas)
        for location in command.locations:
            city = location.city.strip()
            department = location.department.strip()
            if city not in self._location_catalog.list_localities(department):
                raise ValueError("city does not belong to department")
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
            affected_areas=affected_areas,
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
        self.invalidate_public_cache()
        return CreatedHelpPoint(point=created, admin_token=token)

    def add_need(self, point: HelpPoint, admin_token: str, category_id: UUID) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if any(need.category_id == category_id for need in point.needs):
            raise ValueError("category already exists")
        updated = replace(
            point,
            needs=(*point.needs, Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP)),
        )
        return self._update_public_point(updated)

    def remove_need(self, point: HelpPoint, admin_token: str, need_id: UUID) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        needs = tuple(need for need in point.needs if need.id != need_id)
        if len(needs) == len(point.needs):
            raise ValueError("need does not exist")
        return self._update_public_point(replace(point, needs=needs))

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
        return self._update_public_point(replace(point, needs=needs))

    def deactivate_help_point(self, point: HelpPoint, admin_token: str) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        return self._update_public_point(replace(point, active=False))

    def update_help_point_category(
        self,
        point: HelpPoint,
        admin_token: str,
        category: HelpPointCategory,
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if not isinstance(category, HelpPointCategory):
            raise ValueError("category must be a valid HelpPointCategory")
        return self._update_public_point(replace(point, category=category))

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
        return self._update_public_point(replace(point, important_links=normalized))

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
        return self._update_public_point(replace(point, locations=updated))

    def update_help_point_affected_areas(
        self,
        point: HelpPoint,
        admin_token: str,
        affected_areas: tuple[AffectedArea, ...],
    ) -> HelpPoint:
        self._require_admin_token(point, admin_token)
        if not affected_areas:
            raise ValueError("at least one affected area is required")
        normalized = []
        for area in affected_areas:
            department = area.department.strip()
            city = (area.city.strip() if area.city is not None else "") or None
            if department not in AFFECTED_DEPARTMENTS:
                raise ValueError("affected department is outside active emergency scope")
            if city is not None and city not in self._location_catalog.list_localities(
                department
            ):
                raise ValueError("affected city does not belong to affected department")
            normalized.append(AffectedArea(department=department, city=city))
        updated = tuple(normalized)
        pairs = tuple((area.department, area.city) for area in updated)
        if len(set(pairs)) != len(pairs):
            raise ValueError("affected areas must be unique")
        return self._update_public_point(replace(point, affected_areas=updated))

    def list_active_categories(self) -> Mapping[str, UUID]:
        return self._repository.list_active_categories()

    def list_active_help_points(self) -> tuple[PublicHelpPoint, ...]:
        return tuple(self.to_public(point) for point in self._repository.list_active_help_points())

    def open_active_help_points_snapshot(self) -> tuple[datetime, int]:
        return self._repository.open_active_help_points_snapshot()

    def list_active_help_points_page(
        self,
        *,
        snapshot_created_at: datetime,
        before_created_at: datetime | None,
        before_id: UUID | None,
        limit: int,
    ) -> tuple[PublicHelpPoint, ...]:
        if (before_created_at is None) != (before_id is None):
            raise ValueError("cursor requires both before_created_at and before_id")
        if limit <= 0:
            raise ValueError("limit must be positive")
        points = self._repository.list_active_help_points_page(
            snapshot_created_at=snapshot_created_at,
            before_created_at=before_created_at,
            before_id=before_id,
            limit=limit,
        )
        return tuple(self.to_public(point) for point in points)

    def get_public_help_point(self, point_id: UUID) -> PublicHelpPoint | None:
        point = self._repository.get_active_help_point_by_id(point_id)
        return None if point is None or not point.active else self.to_public(point)

    def get_cached_public_home(self) -> CachedPublicHome | None:
        return self._public_cache.get_home()

    def store_public_home(
        self,
        points: tuple[PublicHelpPoint, ...],
        categories: Mapping[str, UUID],
    ) -> None:
        self._public_cache.store_home(points, categories)

    def begin_public_home_refresh(self) -> RefreshToken | None:
        return self._public_cache.begin_home_refresh()

    def finish_public_home_refresh(
        self,
        token: RefreshToken,
        points: tuple[PublicHelpPoint, ...],
        categories: Mapping[str, UUID],
    ) -> bool:
        return self._public_cache.finish_home_refresh(token, points, categories)

    def abort_public_home_refresh(self, token: RefreshToken) -> None:
        self._public_cache.abort_home_refresh(token)

    def wait_for_cached_public_home(
        self,
        timeout: float = 15.0,
    ) -> CachedPublicHome | None:
        return self._public_cache.wait_for_home(timeout)

    def get_cached_public_help_point(self, point_id: UUID) -> CachedPublicPoint | None:
        return self._public_cache.get_point(point_id)

    def refresh_public_help_point(
        self,
        point_id: UUID,
        *,
        max_wait_seconds: float = 15.0,
    ) -> CachedPublicPoint | None:
        if max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be positive")
        token = self._public_cache.begin_point_refresh(point_id)
        if token is None:
            status, cached = self._public_cache.wait_for_point_refresh(
                point_id,
                max_wait_seconds,
            )
            if status == "completed":
                return cached
            if status == "timeout":
                raise TimeoutError("timed out waiting for public point refresh")
            token = self._public_cache.begin_point_refresh(point_id)
            if token is None:
                raise TimeoutError("public point refresh remained busy")
        try:
            point = self._repository.get_active_help_point_by_id(point_id)
            if point is None or not point.active:
                _, result = self._public_cache.finish_point_refresh(token, None, None)
                return result
            categories = self._repository.list_active_categories()
            _, result = self._public_cache.finish_point_refresh(
                token,
                self.to_public(point),
                categories,
            )
            return result
        except BaseException:
            self._public_cache.abort_point_refresh(token)
            raise

    def invalidate_public_cache(self) -> None:
        self._public_cache.clear()

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
        category_id = self._repository.create_custom_category(normalized_name)
        self.invalidate_public_cache()
        return category_id

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
        self.invalidate_public_cache()
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
        return self._update_public_point(
            replace(
                point,
                name=normalized_name,
                description=normalized_description,
                coordinator_contact=normalized_contact,
                additional_affected_areas=normalized_additional_areas,
            )
        )

    def _update_public_point(self, point: HelpPoint) -> HelpPoint:
        updated = self._repository.update_help_point(point)
        self.invalidate_public_cache()
        return updated

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
            affected_areas=point.affected_areas,
            locations=point.locations,
            coordinator_name=point.coordinator_name,
            coordinator_contact=point.coordinator_contact,
            active=point.active,
            needs=tuple(replace(need, commitments=()) for need in point.needs),
            category=point.category,
            created_at=point.created_at,
            updated_at=point.updated_at,
            additional_affected_areas=point.additional_affected_areas,
            important_links=point.important_links,
        )
