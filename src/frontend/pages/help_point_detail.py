"""Public help-point detail page."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from nicegui import ui

from backend.domain.models import PublicHelpPoint
from frontend.components.help_point_map import render_help_point_map, status_text


GetPublicHelpPoint = Callable[[UUID], PublicHelpPoint | None]
_NOT_FOUND_MESSAGE = "No fue posible encontrar este punto de ayuda."


def render_help_point_detail_for_path(
    point_id: str,
    get_public_help_point: GetPublicHelpPoint,
    categories: Mapping[str, UUID],
) -> None:
    """Resolve an untrusted path ID and render only a public active point."""
    try:
        parsed_id = UUID(point_id)
    except (AttributeError, TypeError, ValueError):
        render_help_point_detail(None, categories)
        return
    render_help_point_detail(get_public_help_point(parsed_id), categories)


def render_help_point_detail(
    point: PublicHelpPoint | None,
    categories: Mapping[str, UUID],
) -> None:
    if point is None or not point.active:
        ui.label(_NOT_FOUND_MESSAGE)
        return

    category_names = {category_id: name for name, category_id in categories.items()}
    reception_location = ", ".join(
        value for value in (point.address, point.city, point.department) if value
    )
    with ui.column().classes("w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4"):
        ui.label(point.name).classes("text-h5")
        ui.label(
            f"Ayuda destinada a: {point.affected_city}, {point.affected_department}"
        )
        ui.label(f"Recibe ayuda en: {reception_location}")
        ui.label(point.description)
        ui.label("Necesidades").classes("text-h6")
        for need in point.needs:
            ui.label(
                f"{status_text(need.status)} "
                f"{category_names.get(need.category_id, 'Necesidad')}"
            )
        render_help_point_map(
            (point,),
            categories,
            center=(point.latitude, point.longitude),
            zoom=15,
        )
