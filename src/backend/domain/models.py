from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID


class NeedStatus(str, Enum):
    NEEDS_HELP = "NEEDS_HELP"
    HELP_ON_THE_WAY = "HELP_ON_THE_WAY"
    COVERED = "COVERED"


class HelpPointCategory(str, Enum):
    """Fixed classification of the help point itself (not of its individual needs)."""

    DONATION_COLLECTION = "Recolección de donaciones"
    DEBRIS_REMOVAL = "Remoción de escombros"
    RESCUE_OPERATIONS = "Labores de rescate"


def validate_required(value: str, field: str, maximum: int) -> None:
    if not value.strip():
        raise ValueError(f"{field} is required")
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")


def validate_optional(value: str | None, field: str, maximum: int) -> None:
    if value is None:
        return
    if not value.strip():
        raise ValueError(f"{field} must not be empty when provided")
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")


@dataclass(frozen=True, slots=True)
class HelpPointLocation:
    id: UUID
    address: str | None
    city: str
    department: str
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class NewHelpPointLocation:
    address: str
    city: str
    department: str
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class AffectedArea:
    department: str
    city: str | None


@dataclass(frozen=True, slots=True)
class CreateHelpPoint:
    name: str
    description: str
    affected_areas: tuple[AffectedArea, ...]
    locations: tuple[NewHelpPointLocation, ...]
    coordinator_name: str
    coordinator_contact: str
    category_ids: tuple[UUID, ...]
    category: HelpPointCategory
    additional_affected_areas: str | None = None
    important_links: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, field, maximum in (
            (self.name, "name", 120),
            (self.description, "description", 5_000),
            (self.coordinator_name, "coordinator_name", 120),
            (self.coordinator_contact, "coordinator_contact", 240),
        ):
            validate_required(value, field, maximum)
        validate_optional(self.additional_affected_areas, "additional_affected_areas", 500)
        if not self.affected_areas:
            raise ValueError("at least one affected area is required")
        for area in self.affected_areas:
            validate_required(area.department, "affected_department", 120)
            validate_optional(area.city, "affected_city", 120)
        pairs = tuple((area.department, area.city) for area in self.affected_areas)
        if len(set(pairs)) != len(pairs):
            raise ValueError("affected areas must be unique")
        for link in self.important_links:
            stripped = link.strip()
            if not stripped.startswith(("http://", "https://")):
                raise ValueError("important_links must start with http:// or https://")
            if not 1 <= len(stripped) <= 500:
                raise ValueError("important_links must be between 1 and 500 characters")
        if not self.important_links:
            raise ValueError("at least one important link is required")
        if not self.locations:
            raise ValueError("at least one location is required")
        for location in self.locations:
            validate_required(location.address, "address", 240)
            validate_required(location.city, "city", 120)
            validate_required(location.department, "department", 120)
            if not -90 <= location.latitude <= 90:
                raise ValueError("latitude must be between -90 and 90")
            if not -180 <= location.longitude <= 180:
                raise ValueError("longitude must be between -180 and 180")
        if not self.category_ids:
            raise ValueError("at least one category is required")
        if len(set(self.category_ids)) != len(self.category_ids):
            raise ValueError("category IDs must be unique")
        if not isinstance(self.category, HelpPointCategory):
            raise ValueError("category must be a valid HelpPointCategory")


@dataclass(frozen=True, slots=True)
class Commitment:
    id: UUID
    need_id: UUID
    name: str
    note: str | None
    active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Need:
    id: UUID
    category_id: UUID
    status: NeedStatus
    commitments: tuple[Commitment, ...] = ()
    active_commitment_count: int = 0


@dataclass(frozen=True, slots=True)
class HelpPoint:
    id: UUID
    name: str
    description: str
    affected_areas: tuple[AffectedArea, ...]
    locations: tuple[HelpPointLocation, ...]
    coordinator_name: str
    coordinator_contact: str
    admin_token: str
    active: bool
    needs: tuple[Need, ...]
    category: HelpPointCategory
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    additional_affected_areas: str | None = None
    important_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicHelpPoint:
    id: UUID
    name: str
    description: str
    affected_areas: tuple[AffectedArea, ...]
    locations: tuple[HelpPointLocation, ...]
    coordinator_name: str
    coordinator_contact: str
    active: bool
    needs: tuple[Need, ...]
    category: HelpPointCategory
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    additional_affected_areas: str | None = None
    important_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatedHelpPoint:
    point: HelpPoint
    admin_token: str
