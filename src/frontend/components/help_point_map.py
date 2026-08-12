"""Public help-point map component."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from uuid import UUID

from nicegui import ui

from backend.domain.models import (
    AffectedArea,
    HelpPointLocation,
    NeedStatus,
    PublicHelpPoint,
)

COLOMBIA_CENTER = (4.5709, -74.2973)

_SHORT_MONTHS = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)


def format_short_date(value: datetime) -> str:
    """Format a date as "12 ago 2026", for compact publication/update labels."""
    return f"{value.day} {_SHORT_MONTHS[value.month - 1]} {value.year}"


def format_short_datetime(value: datetime) -> str:
    """Format a date and time as "12 ago 2026, 14:35", for last-updated labels."""
    return f"{format_short_date(value)}, {value.strftime('%H:%M')}"


def format_relative_time(value: datetime) -> str | None:
    """Return "hace N minutos/horas" for values within the last day, else None."""
    delta = datetime.now(UTC) - value
    if delta.total_seconds() < 60:
        return "hace menos de un minuto"
    if delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() // 60)
        return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
    if delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() // 3600)
        return f"hace {hours} hora{'s' if hours != 1 else ''}"
    return None

_STATUS_EMOJI = {
    NeedStatus.NEEDS_HELP: "🔴",
    NeedStatus.HELP_ON_THE_WAY: "🟡",
    NeedStatus.COVERED: "🟢",
}
_STATUS_SUFFIX = {
    NeedStatus.COVERED: " — no enviar más",
}


def status_line(status: NeedStatus, name: str) -> str:
    """Return the emoji + need name, with a warning suffix only for COVERED."""
    return f"{_STATUS_EMOJI[status]} {name}{_STATUS_SUFFIX.get(status, '')}"


def describe_affected_areas(areas: Sequence[AffectedArea]) -> str:
    """Group affected areas by department into one readable, joined line."""
    departments_in_order: list[str] = []
    cities_by_department: dict[str, list[str]] = {}
    whole_department: set[str] = set()
    for area in areas:
        if area.department not in cities_by_department:
            cities_by_department[area.department] = []
            departments_in_order.append(area.department)
        if area.city is None:
            whole_department.add(area.department)
        else:
            cities_by_department[area.department].append(area.city)
    parts = [
        f"Todo el departamento de {department}"
        if department in whole_department
        else f"{', '.join(cities_by_department[department])}, {department}"
        for department in departments_in_order
    ]
    return "; ".join(parts)


def build_popup_html(
    point: PublicHelpPoint,
    categories: Mapping[str, UUID],
    location: HelpPointLocation,
) -> str:
    """Build a popup after escaping every dynamic value."""
    category_names = {category_id: name for name, category_id in categories.items()}
    needs = "".join(
        "<li>"
        f"{status_line(need.status, escape(category_names.get(need.category_id, 'Necesidad')))}"
        "</li>"
        for need in point.needs
    )
    affected_location = describe_affected_areas(point.affected_areas)
    reception_location = ", ".join(
        value for value in (location.address, location.city, location.department) if value
    )
    return (
        f"<strong>{escape(point.name)}</strong>"
        f"<div>Ayuda destinada a: {escape(affected_location)}</div>"
        f"<div>Recibe ayuda en: {escape(reception_location)}</div>"
        f"<ul>{needs}</ul>"
        f'<a href="/puntos/{escape(str(point.id), quote=True)}">Ver punto</a>'
    )


def render_help_point_map(
    points: Sequence[PublicHelpPoint],
    categories: Mapping[str, UUID],
    *,
    center: tuple[float, float] = COLOMBIA_CENTER,
    zoom: int = 5,
):
    """Render active points as Leaflet markers with safe popups."""
    map_element = ui.leaflet(center=center, zoom=zoom).classes(
        "w-full h-64 md:h-[28rem] rounded-2xl overflow-hidden shadow-sm"
    )
    marker_popups = []
    for point in points:
        if not point.active:
            continue
        for location in point.locations:
            marker = map_element.marker(
                latlng=(location.latitude, location.longitude)
            )
            marker_popups.append(
                (marker, build_popup_html(point, categories, location))
            )

    def bind_popups() -> None:
        for marker, popup_html in marker_popups:
            marker.run_method("bindPopup", popup_html)

    map_element.on("init", bind_popups)
    return map_element
