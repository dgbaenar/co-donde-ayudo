"""Public help-point map component."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from uuid import UUID

from nicegui import ui

from backend.domain.models import NeedStatus, PublicHelpPoint


COLOMBIA_CENTER = (4.5709, -74.2973)

_STATUS_TEXT = {
    NeedStatus.NEEDS_HELP: "🔴 Se necesita",
    NeedStatus.HELP_ON_THE_WAY: "🟡 Hay ayuda en camino — todavía se necesita",
    NeedStatus.COVERED: "🟢 Cubierto — no enviar más",
}


def status_text(status: NeedStatus) -> str:
    return _STATUS_TEXT[status]


def build_popup_html(
    point: PublicHelpPoint,
    categories: Mapping[str, UUID],
) -> str:
    """Build a popup after escaping every dynamic value."""
    category_names = {category_id: name for name, category_id in categories.items()}
    needs = "".join(
        "<li>"
        f"{escape(status_text(need.status))} "
        f"{escape(category_names.get(need.category_id, 'Necesidad'))}"
        "</li>"
        for need in point.needs
    )
    affected_location = f"{point.affected_city}, {point.affected_department}"
    reception_location = ", ".join(
        value for value in (point.address, point.city, point.department) if value
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
        marker = map_element.marker(latlng=(point.latitude, point.longitude))
        marker_popups.append((marker, build_popup_html(point, categories)))

    def bind_popups() -> None:
        for marker, popup_html in marker_popups:
            marker.run_method("bindPopup", popup_html)

    map_element.on("init", bind_popups)
    return map_element
