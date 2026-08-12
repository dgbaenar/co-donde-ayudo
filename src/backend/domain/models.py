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
class CreateHelpPoint:
    name: str
    description: str
    city: str
    department: str
    address: str
    affected_city: str | None
    affected_department: str
    latitude: float
    longitude: float
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
            (self.city, "city", 120),
            (self.department, "department", 120),
            (self.address, "address", 240),
            (self.affected_department, "affected_department", 120),
            (self.coordinator_name, "coordinator_name", 120),
            (self.coordinator_contact, "coordinator_contact", 240),
        ):
            validate_required(value, field, maximum)
        validate_optional(self.affected_city, "affected_city", 120)
        validate_optional(self.additional_affected_areas, "additional_affected_areas", 500)
        for link in self.important_links:
            stripped = link.strip()
            if not stripped.startswith(("http://", "https://")):
                raise ValueError("important_links must start with http:// or https://")
            if not 1 <= len(stripped) <= 500:
                raise ValueError("important_links must be between 1 and 500 characters")
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
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
    city: str
    department: str
    address: str | None
    affected_city: str | None
    affected_department: str
    latitude: float
    longitude: float
    coordinator_name: str
    coordinator_contact: str
    admin_token: str
    active: bool
    needs: tuple[Need, ...]
    category: HelpPointCategory
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    additional_affected_areas: str | None = None
    important_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicHelpPoint:
    id: UUID
    name: str
    description: str
    city: str
    department: str
    address: str | None
    affected_city: str | None
    affected_department: str
    latitude: float
    longitude: float
    coordinator_name: str
    coordinator_contact: str
    active: bool
    needs: tuple[Need, ...]
    category: HelpPointCategory
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    additional_affected_areas: str | None = None
    important_links: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatedHelpPoint:
    point: HelpPoint
    admin_token: str
