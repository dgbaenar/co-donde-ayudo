from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class NeedStatus(str, Enum):
    NEEDS_HELP = "NEEDS_HELP"
    HELP_ON_THE_WAY = "HELP_ON_THE_WAY"
    COVERED = "COVERED"


def validate_required(value: str, field: str, maximum: int) -> None:
    if not value.strip():
        raise ValueError(f"{field} is required")
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")


@dataclass(frozen=True, slots=True)
class CreateHelpPoint:
    name: str
    description: str
    city: str
    department: str
    address: str
    affected_city: str
    affected_department: str
    latitude: float
    longitude: float
    coordinator_name: str
    coordinator_contact: str
    category_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        for value, field, maximum in (
            (self.name, "name", 120),
            (self.description, "description", 1_000),
            (self.city, "city", 120),
            (self.department, "department", 120),
            (self.address, "address", 240),
            (self.affected_city, "affected_city", 120),
            (self.affected_department, "affected_department", 120),
            (self.coordinator_name, "coordinator_name", 120),
            (self.coordinator_contact, "coordinator_contact", 240),
        ):
            validate_required(value, field, maximum)
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if not self.category_ids:
            raise ValueError("at least one category is required")
        if len(set(self.category_ids)) != len(self.category_ids):
            raise ValueError("category IDs must be unique")


@dataclass(frozen=True, slots=True)
class Need:
    id: UUID
    category_id: UUID
    status: NeedStatus


@dataclass(frozen=True, slots=True)
class HelpPoint:
    id: UUID
    name: str
    description: str
    city: str
    department: str
    address: str | None
    affected_city: str
    affected_department: str
    latitude: float
    longitude: float
    coordinator_name: str
    coordinator_contact: str
    admin_token: str
    active: bool
    needs: tuple[Need, ...]


@dataclass(frozen=True, slots=True)
class PublicHelpPoint:
    id: UUID
    name: str
    description: str
    city: str
    department: str
    address: str | None
    affected_city: str
    affected_department: str
    latitude: float
    longitude: float
    active: bool
    needs: tuple[Need, ...]


@dataclass(frozen=True, slots=True)
class CreatedHelpPoint:
    point: HelpPoint
    admin_token: str
