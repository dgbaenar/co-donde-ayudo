"""Public help-point detail page."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from nicegui import ui

from backend.domain.models import NeedStatus, PublicHelpPoint
from frontend.components.help_point_map import render_help_point_map, status_text


GetPublicHelpPoint = Callable[[UUID], PublicHelpPoint | None]
_NOT_FOUND_MESSAGE = "No fue posible encontrar este punto de ayuda."
_STATUS_ROW_CLASSES = {
    NeedStatus.NEEDS_HELP: "border-l-red-500 bg-red-50/50",
    NeedStatus.HELP_ON_THE_WAY: "border-l-amber-500 bg-amber-50/50",
    NeedStatus.COVERED: "border-l-emerald-500 bg-emerald-50/50",
}


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
    with ui.column().classes("w-full min-h-screen bg-slate-50"):
        with ui.column().classes("w-full max-w-4xl mx-auto gap-4 p-4 md:p-6"):
            ui.link("Volver al mapa", "/").classes(
                "text-sm font-medium text-slate-700 min-h-[44px] flex items-center"
            )

            with ui.column().classes(
                "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
            ):
                ui.label(point.name).classes(
                    "text-2xl md:text-3xl font-bold text-slate-900"
                ).props("role=heading aria-level=1")
                ui.label(point.description).classes(
                    "text-base leading-relaxed text-slate-600"
                )

            with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-3"):
                with ui.column().classes(
                    "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Ayuda destinada a").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    affected_area = (
                        f"{point.affected_city}, {point.affected_department}"
                        if point.affected_city
                        else f"Todo el departamento de {point.affected_department}"
                    )
                    ui.label(affected_area).classes("text-slate-700")
                    if point.additional_affected_areas:
                        ui.label(
                            f"También: {point.additional_affected_areas}"
                        ).classes("text-slate-700")

                with ui.column().classes(
                    "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Recibe ayuda en").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    ui.label(reception_location).classes("text-slate-700")

            with ui.column().classes(
                "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
            ):
                ui.label("Necesidades actuales").classes(
                    "text-lg font-semibold text-slate-900"
                ).props("role=heading aria-level=2")
                for need in point.needs:
                    with ui.row().classes(
                        "w-full flex-nowrap items-start gap-3 rounded-xl border "
                        "border-slate-200 border-l-4 p-3 "
                        f"{_STATUS_ROW_CLASSES[need.status]}"
                    ):
                        ui.label(
                            f"{status_text(need.status)} "
                            f"{category_names.get(need.category_id, 'Necesidad')}"
                        ).classes("text-sm leading-relaxed text-slate-800")

            with ui.column().classes(
                "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
            ):
                ui.label("Ubicación del punto de recepción").classes(
                    "text-lg font-semibold text-slate-900"
                ).props("role=heading aria-level=2")
                render_help_point_map(
                    (point,),
                    categories,
                    center=(point.latitude, point.longitude),
                    zoom=15,
                )
