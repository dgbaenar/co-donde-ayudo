"""Public help-point detail page."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from uuid import UUID

from nicegui import ui

from backend.domain.models import Need, NeedStatus, PublicHelpPoint
from frontend.components.help_point_map import render_help_point_map, status_line

logger = logging.getLogger(__name__)


GetPublicHelpPoint = Callable[[UUID], PublicHelpPoint | None]
CreateCommitmentHandler = Callable[[UUID, str, str | None], Need]
_NOT_FOUND_MESSAGE = "No fue posible encontrar este punto de ayuda."
_STATUS_ROW_CLASSES = {
    NeedStatus.NEEDS_HELP: "border-l-red-500 bg-red-50/50",
    NeedStatus.HELP_ON_THE_WAY: "border-l-amber-500 bg-amber-50/50",
    NeedStatus.COVERED: "border-l-emerald-500 bg-emerald-50/50",
}
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
            ).classes("w-full min-h-[44px]").props("unelevated color=primary")
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
                ).classes("w-full sm:flex-1 min-h-[44px]").props(
                    "outline color=blue-grey-7"
                )
                ui.button("Confirmar", on_click=lambda: confirm(commit_card, commit_dialog, name_input, note_input)).classes(
                    "w-full sm:flex-1 min-h-[44px]"
                ).props("unelevated color=primary")

        return commit_dialog, commit_card, name_input, note_input

    commit_dialog, _, _, _ = build_dialog()

    ui.button("Voy a ayudar", on_click=commit_dialog.open).classes(
        "shrink-0 min-h-[44px] px-3"
    ).props("unelevated color=primary")


def render_help_point_detail(
    point: PublicHelpPoint | None,
    categories: Mapping[str, UUID],
    create_commitment: CreateCommitmentHandler,
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
                with ui.column().classes(
                    "w-full gap-1 rounded-lg bg-slate-50 p-3 mt-1"
                ):
                    ui.label(f"Coordina: {point.coordinator_name}").classes(
                        "text-base font-semibold text-slate-800"
                    )
                    ui.label(f"Contacto: {point.coordinator_contact}").classes(
                        "text-base text-slate-700"
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
                with ui.row().classes("w-full flex-wrap gap-x-3 gap-y-1"):
                    ui.label("🔴 Se necesita ayuda").classes(
                        "text-xs text-slate-500"
                    )
                    ui.label("🟡 Ya hay alguien en camino").classes(
                        "text-xs text-slate-500"
                    )
                    ui.label("🟢 Cubierto — no enviar más").classes(
                        "text-xs text-slate-500"
                    )
                with ui.row().classes(
                    "w-full items-start gap-2 rounded-lg border "
                    "border-slate-200 bg-slate-50 p-2"
                ):
                    ui.label("ℹ️").classes("text-xs leading-relaxed")
                    ui.label(
                        "El amarillo se activa automáticamente al confirmar "
                        "ayuda. Solo quien coordina este punto puede marcarlo "
                        "como cubierto (verde)."
                    ).classes("text-xs leading-relaxed text-slate-600")
                with ui.row().classes(
                    "w-full items-start gap-2 rounded-lg border "
                    "border-slate-200 bg-slate-50 p-2"
                ):
                    ui.label("🙏").classes("text-xs leading-relaxed")
                    ui.label(
                        "Marca \"Voy a ayudar\" solo si de verdad vas a "
                        "cumplir con esa necesidad. Si no vas a poder, "
                        "por favor no la marques."
                    ).classes("text-xs leading-relaxed text-slate-600")
                for need in point.needs:
                    with ui.row().classes("w-full flex-wrap items-center gap-3"):
                        status_slot = ui.row().classes("flex-1 min-w-0")

                        def render_status(
                            current_need: Need, slot: ui.row = status_slot
                        ) -> None:
                            slot.clear()
                            with slot:
                                with ui.column().classes(
                                    "w-full gap-1 rounded-xl border border-slate-200 "
                                    "border-l-4 p-3 "
                                    f"{_STATUS_ROW_CLASSES[current_need.status]}"
                                ):
                                    ui.label(
                                        status_line(
                                            current_need.status,
                                            category_names.get(
                                                current_need.category_id, "Necesidad"
                                            ),
                                        )
                                    ).classes(
                                        "text-sm leading-relaxed text-slate-800"
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
