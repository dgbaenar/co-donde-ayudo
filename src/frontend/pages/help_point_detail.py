"""Public help-point detail page."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from uuid import UUID

from nicegui import ui

from backend.domain.models import Need, NeedStatus, PublicHelpPoint
from frontend.components.help_point_map import (
    category_badge_classes,
    category_pin_color,
    describe_affected_areas,
    format_relative_time,
    format_short_date,
    render_help_point_map,
)

logger = logging.getLogger(__name__)


GetPublicHelpPoint = Callable[[UUID], PublicHelpPoint | None]
CreateCommitmentHandler = Callable[[UUID, str, str | None], Need]
_NOT_FOUND_MESSAGE = "No fue posible encontrar este punto de ayuda."
_STATUS_BORDER_CLASSES = {
    NeedStatus.NEEDS_HELP: "border-l-red-500",
    NeedStatus.HELP_ON_THE_WAY: "border-l-amber-500",
    NeedStatus.COVERED: "border-l-emerald-500",
}
_STATUS_BADGE_BG = {
    NeedStatus.NEEDS_HELP: "bg-red-600",
    NeedStatus.HELP_ON_THE_WAY: "bg-amber-600",
    NeedStatus.COVERED: "bg-emerald-600",
}
_STATUS_BADGE_LABEL = {
    NeedStatus.NEEDS_HELP: "Se necesita",
    NeedStatus.HELP_ON_THE_WAY: "En camino",
    NeedStatus.COVERED: "Cubierto",
}
_STATUS_LEGEND_LABEL = {
    NeedStatus.NEEDS_HELP: "Se necesita ayuda",
    NeedStatus.HELP_ON_THE_WAY: "Ayuda en camino",
    NeedStatus.COVERED: "Cubierto — no enviar más",
}


def status_badge_classes(status: NeedStatus) -> str:
    """Return the solid-color pill classes for a need's status badge."""
    return (
        f"text-[10px] font-bold uppercase tracking-wide text-white "
        f"{_STATUS_BADGE_BG[status]} rounded-full px-2.5 py-1 shrink-0"
    )


_THANKS_MESSAGE = (
    "Gracias. Las personas que coordinan este punto podrán ver que hay "
    "ayuda en camino."
)


def commitment_count_text(count: int) -> str | None:
    """Describe how many people committed, or None when there is nobody yet."""
    if count <= 0:
        return None
    if count == 1:
        return "1 persona confirmó ayuda"
    return f"{count} personas confirmaron ayuda"


def render_updated_at(updated_at: datetime) -> None:
    """Show a relative or absolute last-updated timestamp."""
    relative = format_relative_time(updated_at)
    label = (
        f"Actualizado {relative}"
        if relative
        else f"Actualizado el {format_short_date(updated_at)}"
    )
    ui.label(label).classes("text-xs text-slate-400 mt-1")


def render_help_point_detail_for_path(
    point_id: str,
    get_public_help_point: GetPublicHelpPoint,
    categories: Mapping[str, UUID],
    create_commitment: CreateCommitmentHandler,
) -> None:
    """Resolve an untrusted path ID and render only a public active point."""
    try:
        parsed_id = UUID(point_id)
    except (AttributeError, TypeError, ValueError):
        render_help_point_detail(None, categories, create_commitment)
        return
    render_help_point_detail(
        get_public_help_point(parsed_id), categories, create_commitment
    )


def render_commitment_control(
    need: Need,
    create_commitment: CreateCommitmentHandler,
    *,
    on_committed: Callable[[Need], None],
) -> None:
    """Render the "Voy a ayudar" trigger and its confirmation dialog."""

    def confirm(commit_card: ui.card, commit_dialog: ui.dialog, name_input: ui.input, note_input: ui.textarea) -> None:
        name_value = (name_input.value or "").strip()
        if not name_value:
            ui.notify("El nombre es obligatorio.", type="negative")
            return
        note_value = (note_input.value or "").strip() or None
        try:
            updated_need = create_commitment(need.id, name_value, note_value)
        except Exception:
            logger.exception(
                "failed to create commitment for need %s", need.id
            )
            ui.notify(
                "No fue posible registrar tu ayuda. Inténtalo de nuevo.",
                type="negative",
            )
            return
        commit_card.clear()
        with commit_card:
            ui.label(_THANKS_MESSAGE).classes("text-slate-700")
            ui.button(
                "Cerrar", on_click=commit_dialog.close
            ).classes("w-full min-h-[44px] rounded-2xl").props(
                "unelevated color=secondary"
            )
        on_committed(updated_need)

    def build_dialog() -> tuple[ui.dialog, ui.card, ui.input, ui.textarea]:
        with ui.dialog() as commit_dialog, ui.card().classes(
            "w-full max-w-sm gap-3 p-4"
        ) as commit_card:
            ui.label("Voy a ayudar").classes(
                "text-lg font-semibold text-slate-900"
            )
            name_input = ui.input("Nombre").classes("w-full")
            note_input = ui.textarea(
                "Nota (opcional)", placeholder="Ej: Voy para allá."
            ).classes("w-full")

            with ui.row().classes("w-full flex-col sm:flex-row gap-2"):
                ui.button(
                    "Cancelar", on_click=commit_dialog.close
                ).classes("w-full sm:flex-1 min-h-[44px] rounded-2xl").props(
                    "unelevated color=blue-grey-7"
                )
                ui.button("Confirmar", on_click=lambda: confirm(commit_card, commit_dialog, name_input, note_input)).classes(
                    "w-full sm:flex-1 min-h-[44px] rounded-2xl"
                ).props("unelevated color=secondary")

        return commit_dialog, commit_card, name_input, note_input

    commit_dialog, _, _, _ = build_dialog()

    ui.button("Voy a ayudar", on_click=commit_dialog.open).classes(
        "shrink-0 min-h-[44px] px-3 rounded-2xl"
    ).props("unelevated color=secondary")


def render_help_point_detail(
    point: PublicHelpPoint | None,
    categories: Mapping[str, UUID],
    create_commitment: CreateCommitmentHandler,
) -> None:
    if point is None or not point.active:
        ui.label(_NOT_FOUND_MESSAGE)
        return

    category_names = {category_id: name for name, category_id in categories.items()}
    with ui.column().classes("w-full min-h-screen bg-slate-50"):
        with ui.column().classes("w-full max-w-4xl mx-auto gap-4 p-4 md:p-6"):
            ui.link("Volver al mapa", "/").classes(
                "text-sm font-medium text-slate-700 min-h-[44px] flex items-center"
            )

            with ui.column().classes(
                "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4 md:p-6 "
                f"border-l-4 border-[{category_pin_color(point.category)}]"
            ):
                ui.label(point.category.value).classes(
                    category_badge_classes(point.category)
                )
                ui.label(point.name).classes(
                    "text-2xl md:text-3xl font-bold text-slate-900"
                ).props("role=heading aria-level=1")
                ui.label(point.description).classes(
                    "text-base leading-relaxed text-slate-600"
                )
                with ui.column().classes(
                    "w-full gap-1 rounded-lg bg-slate-50 p-3 mt-1"
                ):
                    ui.label(f"Coordina: {point.coordinator_name}").classes(
                        "text-base font-semibold text-slate-800"
                    )
                    ui.label(f"Contacto: {point.coordinator_contact}").classes(
                        "text-base text-slate-700"
                    )
                ui.label(f"Publicado el {format_short_date(point.created_at)}").classes(
                    "text-xs text-slate-400 mt-1"
                )
                render_updated_at(point.updated_at)

            with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-3"):
                with ui.column().classes(
                    "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Ayuda destinada a").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    affected_area = describe_affected_areas(point.affected_areas)
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
                    for location in point.locations:
                        reception_location = ", ".join(
                            value
                            for value in (
                                location.address,
                                location.city,
                                location.department,
                            )
                            if value
                        )
                        ui.label(reception_location).classes("text-slate-700")

            with ui.column().classes(
                "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
            ):
                ui.label("Necesidades actuales").classes(
                    "text-lg font-semibold text-slate-900"
                ).props("role=heading aria-level=2")
                with ui.row().classes("w-full flex-wrap gap-2"):
                    for legend_status in (
                        NeedStatus.NEEDS_HELP,
                        NeedStatus.HELP_ON_THE_WAY,
                        NeedStatus.COVERED,
                    ):
                        ui.label(_STATUS_LEGEND_LABEL[legend_status]).classes(
                            status_badge_classes(legend_status)
                        )
                with ui.row().classes(
                    "w-full items-start gap-2 rounded-xl bg-blue-50 p-3"
                ):
                    ui.icon("info").classes(
                        "text-blue-600 text-base shrink-0"
                    ).props("aria-hidden=true")
                    ui.label(
                        "El amarillo se activa automáticamente al confirmar "
                        "ayuda. Solo quien coordina este punto puede marcarlo "
                        "como cubierto (verde)."
                    ).classes("text-xs leading-relaxed text-blue-900")
                with ui.row().classes(
                    "w-full items-start gap-2 rounded-xl bg-amber-50 p-3"
                ):
                    ui.icon("volunteer_activism").classes(
                        "text-amber-600 text-base shrink-0"
                    ).props("aria-hidden=true")
                    ui.label(
                        "Marca \"Voy a ayudar\" solo si de verdad vas a "
                        "cumplir con esa necesidad. Si no vas a poder, "
                        "por favor no la marques."
                    ).classes("text-xs leading-relaxed text-amber-900")
                for need in point.needs:
                    with ui.row().classes("w-full flex-wrap items-center gap-3"):
                        status_slot = ui.column().classes("flex-1 min-w-0")

                        def render_status(
                            current_need: Need, slot: ui.column = status_slot
                        ) -> None:
                            slot.clear()
                            with slot:
                                with ui.column().classes(
                                    "w-full gap-2 rounded-2xl border "
                                    "border-slate-200 bg-white p-3 border-l-4 "
                                    f"{_STATUS_BORDER_CLASSES[current_need.status]}"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(
                                            _STATUS_BADGE_LABEL[current_need.status]
                                        ).classes(
                                            status_badge_classes(current_need.status)
                                        )
                                        need_name = category_names.get(
                                            current_need.category_id, "Necesidad"
                                        )
                                        ui.label(need_name).classes(
                                            "text-sm font-semibold text-slate-900 "
                                            "break-words"
                                        )
                                    count_text = commitment_count_text(
                                        current_need.active_commitment_count
                                    )
                                    if count_text:
                                        ui.label(count_text).classes(
                                            "text-xs text-slate-500"
                                        )

                        render_status(need)
                        if need.status != NeedStatus.COVERED:
                            render_commitment_control(
                                need, create_commitment, on_committed=render_status
                            )

            if point.important_links:
                with ui.column().classes(
                    "w-full gap-2 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
                ):
                    ui.label("Enlaces importantes").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    for link_url in point.important_links:
                        ui.link(link_url, link_url).classes(
                            "text-sm text-blue-700 break-all"
                        )

            with ui.column().classes(
                "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:p-6"
            ):
                ui.label("Ubicación del punto de recepción").classes(
                    "text-lg font-semibold text-slate-900"
                ).props("role=heading aria-level=2")
                first_location = point.locations[0]
                render_help_point_map(
                    (point,),
                    categories,
                    center=(first_location.latitude, first_location.longitude),
                    zoom=15,
                )
