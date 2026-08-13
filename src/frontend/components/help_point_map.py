"""Public help-point map component."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from uuid import UUID

from nicegui import ui

from backend.domain.models import (
    AffectedArea,
    HelpPointCategory,
    HelpPointLocation,
    NeedStatus,
    PublicHelpPoint,
)

COLOMBIA_CENTER = (4.5709, -74.2973)

_CATEGORY_PIN_COLORS: dict[HelpPointCategory, str] = {
    HelpPointCategory.DONATION_COLLECTION: "#059669",
    HelpPointCategory.DEBRIS_REMOVAL: "#d97706",
    HelpPointCategory.RESCUE_OPERATIONS: "#dc2626",
    HelpPointCategory.PSYCHOLOGICAL_SUPPORT: "#7c3aed",
    HelpPointCategory.MEDICAL_CARE: "#0284c7",
    HelpPointCategory.HOUSING_AND_SHELTER: "#ea580c",
    HelpPointCategory.COMMUNITY_FOOD: "#65a30d",
    HelpPointCategory.VOLUNTEERING: "#4f46e5",
    HelpPointCategory.BLOOD_DONATION: "#e11d48",
    HelpPointCategory.MONEY_DONATION: "#0d9488",
    HelpPointCategory.PET_ASSISTANCE: "#a21caf",
}


def category_pin_color(category: HelpPointCategory) -> str:
    """Return the strong, saturated hex color for a category's map pin."""
    return _CATEGORY_PIN_COLORS[category]


def category_badge_classes(category: HelpPointCategory) -> str:
    """Return the solid-color pill classes for a point's category badge."""
    return (
        f"text-[10px] font-bold uppercase tracking-wide text-white "
        f"bg-[{category_pin_color(category)}] rounded-full px-2.5 py-1 self-start"
    )


def pin_icon_html(color: str) -> str:
    """Build an inline SVG teardrop pin filled with the given color."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="26" height="38" '
        'viewBox="0 0 26 38">'
        f'<path d="M13 0C5.82 0 0 5.82 0 13c0 9.75 13 25 13 25s13-15.25 13-25'
        f'C26 5.82 20.18 0 13 0z" fill="{color}"/>'
        '<circle cx="13" cy="13" r="5.5" fill="white"/>'
        "</svg>"
    )

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


def apply_modern_basemap(map_element) -> None:
    """Replace the default OSM tiles with a lighter, more modern basemap."""
    map_element.clear_layers()
    map_element.tile_layer(
        url_template="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        options={
            "attribution": (
                '&copy; <a href="https://www.openstreetmap.org/copyright">'
                "OpenStreetMap</a> contributors &copy; "
                '<a href="https://carto.com/attributions">CARTO</a>'
            ),
        },
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
        "w-full h-80 md:h-[28rem] rounded-2xl overflow-hidden shadow-sm"
    )
    apply_modern_basemap(map_element)
    marker_popups = []
    marker_icons = []
    for point in points:
        if not point.active:
            continue
        icon_html = pin_icon_html(category_pin_color(point.category))
        for location in point.locations:
            marker = map_element.marker(
                latlng=(location.latitude, location.longitude)
            )
            marker_popups.append(
                (marker, build_popup_html(point, categories, location))
            )
            marker_icons.append((marker, icon_html))

    def bind_popups() -> None:
        for marker, popup_html in marker_popups:
            marker.run_method(
                "bindPopup", popup_html, {"maxWidth": 240, "maxHeight": 180}
            )
        for marker, icon_html in marker_icons:
            marker.run_method(
                ":setIcon",
                "L.divIcon({"
                f"html: {json.dumps(icon_html)}, "
                "className: '', "
                "iconSize: [26, 38], "
                "iconAnchor: [13, 38], "
                "popupAnchor: [0, -34]"
                "})",
            )

    map_element.on("init", bind_popups)
    return map_element
