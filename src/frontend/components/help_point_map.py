"""Public help-point map component."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from uuid import UUID

from nicegui import ui

from backend.domain.models import HelpPointLocation, NeedStatus, PublicHelpPoint


COLOMBIA_CENTER = (4.5709, -74.2973)

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
    affected_location = (
        f"Todo el departamento de {point.affected_department}"
        if point.affected_city is None
        else f"{point.affected_city}, {point.affected_department}"
    )
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
