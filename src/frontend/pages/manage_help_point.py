"""NiceGUI administration page for one help point."""
# style-guard: E6-exempt — cohesive single-page NiceGUI admin form; the cards share apply/render_content and the mutable point, so splitting them would fragment that shared state without reducing complexity.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import logging
from uuid import UUID

from nicegui import ui

from backend.domain.models import (
    HelpPoint,
    HelpPointCategory,
    NeedStatus,
    NewHelpPointLocation,
)
from frontend.components.location_picker import render_location_picker

logger = logging.getLogger(__name__)


AddNeedHandler = Callable[[HelpPoint, str, UUID], HelpPoint]
RemoveNeedHandler = Callable[[HelpPoint, str, UUID], HelpPoint]
ChangeNeedStatusHandler = Callable[[HelpPoint, str, UUID, NeedStatus], HelpPoint]
DeactivateHelpPointHandler = Callable[[HelpPoint, str], HelpPoint]
UpdateHelpPointInfoHandler = Callable[[HelpPoint, str, str, str, str, str | None], HelpPoint]
UpdateHelpPointCategoryHandler = Callable[[HelpPoint, str, HelpPointCategory], HelpPoint]
UpdateHelpPointLinksHandler = Callable[[HelpPoint, str, tuple[str, ...]], HelpPoint]
UpdateHelpPointLocationsHandler = Callable[
    [HelpPoint, str, tuple[NewHelpPointLocation, ...]], HelpPoint
]


def category_name(categories: Mapping[str, UUID], category_id: UUID) -> str:
    return next(
        (name for name, current_id in categories.items() if current_id == category_id),
        "Necesidad",
    )


def status_options() -> dict[str, NeedStatus]:
    return {
        "Se necesita": NeedStatus.NEEDS_HELP,
        "Hay ayuda en camino — todavía se necesita": NeedStatus.HELP_ON_THE_WAY,
        "Cubierto — no enviar más": NeedStatus.COVERED,
    }


def category_options() -> dict[HelpPointCategory, str]:
    return {category: category.value for category in HelpPointCategory}


def add_need_to_point(
    point: HelpPoint,
    admin_token: str,
    category_name: str,
    categories: Mapping[str, UUID],
    add_need: AddNeedHandler,
) -> HelpPoint:
    try:
        category_id = categories[category_name]
    except KeyError as error:
        raise ValueError(f"unknown category: {category_name}") from error
    return add_need(point, admin_token, category_id)


def remove_need_from_point(
    point: HelpPoint,
    admin_token: str,
    need_id: UUID,
    remove_need: RemoveNeedHandler,
) -> HelpPoint:
    return remove_need(point, admin_token, need_id)


def change_need_state(
    point: HelpPoint,
    admin_token: str,
    need_id: UUID,
    status: NeedStatus,
    change_need_status: ChangeNeedStatusHandler,
) -> HelpPoint:
    return change_need_status(point, admin_token, need_id, status)


def deactivate_point(
    point: HelpPoint,
    admin_token: str,
    deactivate_help_point: DeactivateHelpPointHandler,
) -> HelpPoint:
    return deactivate_help_point(point, admin_token)


def update_point_info(
    point: HelpPoint,
    admin_token: str,
    name: str,
    description: str,
    coordinator_contact: str,
    additional_affected_areas: str | None,
    update_help_point_info: UpdateHelpPointInfoHandler,
) -> HelpPoint:
    return update_help_point_info(
        point, admin_token, name, description, coordinator_contact, additional_affected_areas
    )


def update_point_category(
    point: HelpPoint,
    admin_token: str,
    category: HelpPointCategory,
    update_help_point_category: UpdateHelpPointCategoryHandler,
) -> HelpPoint:
    return update_help_point_category(point, admin_token, category)


def update_point_links(
    point: HelpPoint,
    admin_token: str,
    links: Sequence[str],
    update_help_point_links: UpdateHelpPointLinksHandler,
) -> HelpPoint:
    return update_help_point_links(point, admin_token, tuple(links))


def update_point_locations(
    point: HelpPoint,
    admin_token: str,
    locations: Sequence[NewHelpPointLocation],
    update_help_point_locations: UpdateHelpPointLocationsHandler,
) -> HelpPoint:
    return update_help_point_locations(point, admin_token, tuple(locations))


def render_manage_help_point(
    point: HelpPoint,
    admin_token: str,
    categories: Mapping[str, UUID],
    add_need: AddNeedHandler,
    remove_need: RemoveNeedHandler,
    change_need_status: ChangeNeedStatusHandler,
    deactivate_help_point: DeactivateHelpPointHandler,
    update_help_point_info: UpdateHelpPointInfoHandler,
    update_help_point_category: UpdateHelpPointCategoryHandler,
    update_help_point_links: UpdateHelpPointLinksHandler,
    update_help_point_locations: UpdateHelpPointLocationsHandler,
) -> None:
    """Render administration controls using injected backend operations only."""
    with ui.column().classes("w-full max-w-md md:max-w-2xl mx-auto gap-4 p-4"):
        ui.link("Volver al inicio", "/").classes(
            "text-sm font-medium text-slate-700 min-h-[44px] flex items-center"
        )
        ui.label("Administrar punto de ayuda").classes(
            "text-2xl font-bold text-slate-900"
        )
        ui.label(point.name).classes("text-lg font-medium text-slate-700")
        content = ui.column().classes("w-full gap-4")
        important_links: list[str] = list(point.important_links)

        def apply(operation: Callable[[], HelpPoint]) -> None:
            nonlocal point
            try:
                point = operation()
            except Exception:
                logger.exception("failed to update help point %s", point.id)
                ui.notify(
                    "No fue posible actualizar el punto. Inténtalo de nuevo.",
                    type="negative",
                )
                return
            render_content()

        def render_content() -> None:
            content.clear()
            with content:
                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Información pública").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    name = ui.input(
                        "Nombre del punto", value=point.name
                    ).classes("w-full").props("maxlength=120 counter")
                    description = ui.textarea(
                        "¿Qué está pasando en este punto?",
                        value=point.description,
                        placeholder=(
                            "Ej: Varias familias fueron evacuadas y estamos "
                            "organizando ayuda desde este parque."
                        ),
                    ).classes("w-full").props("maxlength=5000 counter")
                    coordinator_contact = ui.input(
                        "Contacto", value=point.coordinator_contact
                    ).classes("w-full")
                    additional_affected_areas = ui.textarea(
                        "¿Hay otras zonas que también recibirán ayuda? (opcional)",
                        value=point.additional_affected_areas or "",
                    ).classes("w-full")
                    ui.button(
                        "Guardar información",
                        on_click=lambda: apply(
                            lambda: update_point_info(
                                point,
                                admin_token,
                                name.value or "",
                                description.value or "",
                                coordinator_contact.value or "",
                                additional_affected_areas.value or None,
                                update_help_point_info,
                            )
                        ),
                    ).classes(
                        "w-full min-h-[44px]"
                    ).props("unelevated color=primary")

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Categoría del punto").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    category_select = ui.select(
                        options=category_options(),
                        label="Categoría del punto",
                        value=point.category,
                    ).classes("w-full").props(
                        "outlined dense behavior=menu color=blue-grey-9 "
                        "transition-show=none transition-hide=none"
                    )
                    ui.button(
                        "Guardar categoría",
                        on_click=lambda: apply(
                            lambda: update_point_category(
                                point,
                                admin_token,
                                category_select.value,
                                update_help_point_category,
                            )
                        ),
                    ).classes(
                        "w-full min-h-[44px]"
                    ).props("unelevated color=primary")

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Enlaces importantes").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")

                    def remove_link(url: str, row) -> None:
                        if url in important_links:
                            important_links.remove(url)
                        row.visible = False

                    def add_link() -> None:
                        url = (link_input.value or "").strip()
                        if not url:
                            return
                        if url in important_links:
                            ui.notify(
                                "Ese enlace ya está en la lista.", type="warning"
                            )
                            return
                        important_links.append(url)
                        link_input.value = ""
                        with links_container:
                            with ui.row().classes(
                                "w-full items-center gap-2 flex-nowrap"
                            ) as link_row:
                                ui.label(url).classes(
                                    "flex-1 min-w-0 break-all text-sm text-slate-700"
                                )
                                ui.button(
                                    "Quitar",
                                    on_click=lambda url=url, row=link_row: remove_link(
                                        url, row
                                    ),
                                ).classes("min-h-[44px] shrink-0").props("flat")

                    links_container = ui.column().classes("w-full gap-2")
                    for url in important_links:
                        with links_container:
                            with ui.row().classes(
                                "w-full items-center gap-2 flex-nowrap"
                            ) as link_row:
                                ui.label(url).classes(
                                    "flex-1 min-w-0 break-all text-sm text-slate-700"
                                )
                                ui.button(
                                    "Quitar",
                                    on_click=lambda url=url, row=link_row: remove_link(
                                        url, row
                                    ),
                                ).classes("min-h-[44px] shrink-0").props("flat")

                    with ui.row().classes("w-full gap-2 items-end flex-nowrap"):
                        link_input = ui.input("Enlace importante (URL)").classes(
                            "flex-1 min-w-0"
                        )
                        ui.button("Agregar enlace", on_click=add_link).classes(
                            "min-h-[44px] shrink-0"
                        )

                    ui.button(
                        "Guardar enlaces",
                        on_click=lambda: apply(
                            lambda: update_point_links(
                                point,
                                admin_token,
                                important_links,
                                update_help_point_links,
                            )
                        ),
                    ).classes("w-full min-h-[44px]").props(
                        "unelevated color=primary"
                    )

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Ubicaciones").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")

                    locations_container = ui.column().classes("w-full gap-2")
                    location_blocks: list[dict] = []

                    def render_location_block(existing=None) -> dict:
                        with locations_container:
                            with ui.card().classes(
                                "w-full gap-2 rounded-xl border border-slate-200 p-3"
                            ) as block_card:
                                address_input = ui.input(
                                    "Dirección",
                                    value=(existing.address if existing else "") or "",
                                ).classes("w-full")
                                city_input = ui.input(
                                    "Ciudad / Municipio",
                                    value=(existing.city if existing else "") or "",
                                ).classes("w-full")
                                department_input = ui.input(
                                    "Departamento",
                                    value=(existing.department if existing else "")
                                    or "",
                                ).classes("w-full")
                                location = render_location_picker()
                                if existing is not None:
                                    location.set_coordinates(
                                        existing.latitude, existing.longitude
                                    )
                                block = {
                                    "card": block_card,
                                    "address": address_input,
                                    "city": city_input,
                                    "department": department_input,
                                    "location": location,
                                }
                                location_blocks.append(block)

                                def remove_location() -> None:
                                    location_blocks.remove(block)
                                    block_card.visible = False

                                ui.button(
                                    "Quitar", on_click=remove_location
                                ).classes("min-h-[44px] w-full").props(
                                    "flat color=red-9"
                                )

                                return block

                    for existing_location in point.locations:
                        render_location_block(existing_location)

                    ui.button(
                        "Agregar ubicación",
                        on_click=lambda: render_location_block(),
                    ).classes("w-full min-h-[44px]").props("outline")

                    def save_locations() -> None:
                        new_locations = []
                        for block in location_blocks:
                            latitude = block["location"].latitude
                            longitude = block["location"].longitude
                            if latitude is None or longitude is None:
                                ui.notify(
                                    "Selecciona una ubicación en el mapa para "
                                    "cada punto.",
                                    type="negative",
                                )
                                return
                            new_locations.append(
                                NewHelpPointLocation(
                                    address=(block["address"].value or "").strip(),
                                    city=(block["city"].value or "").strip(),
                                    department=(block["department"].value or "").strip(),
                                    latitude=latitude,
                                    longitude=longitude,
                                )
                            )
                        if not new_locations:
                            ui.notify(
                                "Agrega al menos una ubicación.", type="negative"
                            )
                            return
                        apply(
                            lambda: update_point_locations(
                                point,
                                admin_token,
                                new_locations,
                                update_help_point_locations,
                            )
                        )

                    ui.button(
                        "Guardar ubicaciones", on_click=save_locations
                    ).classes("w-full min-h-[44px]").props(
                        "unelevated color=primary"
                    )

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Necesidades").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    with ui.row().classes(
                        "w-full items-start gap-2 rounded-lg border "
                        "border-slate-200 bg-slate-50 p-2"
                    ):
                        ui.label("ℹ️").classes("text-xs leading-relaxed")
                        ui.label(
                            "Quien confirma ayuda solo activa el estado "
                            "amarillo. Solo quien tenga este enlace de "
                            "administración puede marcar una necesidad como "
                            "cubierto."
                        ).classes("text-xs leading-relaxed text-slate-600")
                    for need in point.needs:
                        with ui.card().classes(
                            "w-full gap-2 rounded-xl border border-slate-200 p-3"
                        ):
                            public_statuses = status_options()
                            options = {
                                status: label
                                for label, status in public_statuses.items()
                            }
                            need_name = category_name(categories, need.category_id)
                            ui.label(need_name).classes(
                                "font-semibold text-slate-900"
                            )
                            ui.label(options[need.status]).classes(
                                "text-sm text-slate-600"
                            )
                            if need.commitments:
                                with ui.column().classes("w-full gap-0.5"):
                                    ui.label("Confirmaron ayuda:").classes(
                                        "text-xs font-semibold text-slate-700"
                                    )
                                    for commitment in need.commitments:
                                        text = f"• {commitment.name}"
                                        if commitment.note:
                                            text += f" — {commitment.note}"
                                        ui.label(text).classes(
                                            "text-xs text-slate-500"
                                        )
                            selected_status = ui.select(
                                options=options,
                                label="Estado",
                                value=need.status,
                            ).classes("w-full").props(
                                "outlined dense behavior=menu color=blue-grey-9"
                            )
                            with ui.row().classes(
                                "w-full flex-col sm:flex-row gap-2"
                            ):
                                ui.button(
                                    "Guardar estado",
                                    on_click=lambda need_id=need.id, selected_status=selected_status: apply(
                                        lambda: change_need_state(
                                            point,
                                            admin_token,
                                            need_id,
                                            selected_status.value,
                                            change_need_status,
                                        )
                                    ),
                                ).classes(
                                    "w-full sm:flex-1 min-h-[44px]"
                                ).props("unelevated color=primary")

                                with ui.dialog() as remove_dialog, ui.card().classes(
                                    "w-full max-w-sm gap-3 p-4"
                                ):
                                    ui.label("¿Quitar esta necesidad?").classes(
                                        "text-lg font-semibold text-slate-900"
                                    )
                                    ui.label(
                                        f"Se quitará {need_name} de este punto de ayuda."
                                    ).classes("text-slate-600")
                                    with ui.row().classes(
                                        "w-full flex-col sm:flex-row gap-2"
                                    ):
                                        ui.button(
                                            "Cancelar", on_click=remove_dialog.close
                                        ).classes(
                                            "w-full sm:flex-1 min-h-[44px]"
                                        ).props("outline color=blue-grey-7")
                                        ui.button(
                                            "Sí, quitar necesidad",
                                            on_click=lambda need_id=need.id, dialog=remove_dialog: (
                                                dialog.close(),
                                                apply(
                                                    lambda: remove_need_from_point(
                                                        point,
                                                        admin_token,
                                                        need_id,
                                                        remove_need,
                                                    )
                                                ),
                                            ),
                                        ).classes(
                                            "w-full sm:flex-1 min-h-[44px]"
                                        ).props("unelevated color=red-9")

                                ui.button(
                                    "Quitar", on_click=remove_dialog.open
                                ).classes(
                                    "w-full sm:flex-1 min-h-[44px]"
                                ).props("unelevated color=red-9")

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-slate-200 bg-white p-4"
                ):
                    ui.label("Agregar necesidad").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    category = ui.select(
                        options=list(categories), label="Agregar necesidad"
                    ).classes("w-full").props(
                        'outlined dense behavior=menu color=blue-grey-9 '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
                    ui.button(
                        "Agregar necesidad",
                        on_click=lambda: apply(
                            lambda: add_need_to_point(
                                point,
                                admin_token,
                                category.value or "",
                                categories,
                                add_need,
                            )
                        ),
                    ).classes(
                        "w-full min-h-[44px]"
                    ).props("unelevated color=primary")

                with ui.card().classes(
                    "w-full gap-3 rounded-2xl border border-red-200 bg-white p-4"
                ):
                    ui.label("Zona de peligro").classes(
                        "text-lg font-semibold text-slate-900"
                    ).props("role=heading aria-level=2")
                    ui.label(
                        "Desactivar oculta el punto del mapa público."
                    ).classes("text-sm text-slate-600")

                    with ui.dialog() as deactivate_dialog, ui.card().classes(
                        "w-full max-w-sm gap-3 p-4"
                    ):
                        ui.label("¿Desactivar este punto?").classes(
                            "text-lg font-semibold text-slate-900"
                        )
                        ui.label(
                            "El punto dejará de aparecer en el mapa público."
                        ).classes("text-slate-600")
                        with ui.row().classes(
                            "w-full flex-col sm:flex-row gap-2"
                        ):
                            ui.button(
                                "Cancelar", on_click=deactivate_dialog.close
                            ).classes(
                                "w-full sm:flex-1 min-h-[44px]"
                            ).props("outline color=blue-grey-7")
                            ui.button(
                                "Sí, desactivar punto",
                                on_click=lambda dialog=deactivate_dialog: (
                                    dialog.close(),
                                    apply(
                                        lambda: deactivate_point(
                                            point,
                                            admin_token,
                                            deactivate_help_point,
                                        )
                                    ),
                                ),
                            ).classes(
                                "w-full sm:flex-1 min-h-[44px]"
                            ).props("unelevated color=red-9")

                    ui.button(
                        "Desactivar punto", on_click=deactivate_dialog.open
                    ).classes("w-full min-h-[44px]").props(
                        "unelevated color=red-9"
                    )

        render_content()
