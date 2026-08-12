"""NiceGUI administration page for one help point."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from nicegui import ui

from backend.domain.models import HelpPoint, NeedStatus


AddNeedHandler = Callable[[HelpPoint, str, UUID], HelpPoint]
RemoveNeedHandler = Callable[[HelpPoint, str, UUID], HelpPoint]
ChangeNeedStatusHandler = Callable[[HelpPoint, str, UUID, NeedStatus], HelpPoint]
DeactivateHelpPointHandler = Callable[[HelpPoint, str], HelpPoint]
UpdateHelpPointInfoHandler = Callable[[HelpPoint, str, str, str], HelpPoint]


def category_name(categories: Mapping[str, UUID], category_id: UUID) -> str:
    return next(
        (name for name, current_id in categories.items() if current_id == category_id),
        "Necesidad",
    )


def status_options() -> dict[str, NeedStatus]:
    return {
        "Se necesita": NeedStatus.NEEDS_HELP,
        "Hay ayuda en camino": NeedStatus.HELP_ON_THE_WAY,
        "Cubierto": NeedStatus.COVERED,
    }


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
    description: str,
    coordinator_contact: str,
    update_help_point_info: UpdateHelpPointInfoHandler,
) -> HelpPoint:
    return update_help_point_info(point, admin_token, description, coordinator_contact)


def render_manage_help_point(
    point: HelpPoint,
    admin_token: str,
    categories: Mapping[str, UUID],
    add_need: AddNeedHandler,
    remove_need: RemoveNeedHandler,
    change_need_status: ChangeNeedStatusHandler,
    deactivate_help_point: DeactivateHelpPointHandler,
    update_help_point_info: UpdateHelpPointInfoHandler,
) -> None:
    """Render administration controls using injected backend operations only."""
    with ui.column().classes("w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4"):
        ui.label("Administrar punto de ayuda").classes("text-h5")
        content = ui.column().classes("w-full gap-2")

        def apply(operation: Callable[[], HelpPoint]) -> None:
            nonlocal point
            try:
                point = operation()
            except (PermissionError, ValueError) as error:
                ui.notify(str(error), type="negative")
                return
            render_content()

        def render_content() -> None:
            content.clear()
            with content:
                description = ui.textarea("¿Qué está pasando?", value=point.description).classes("w-full")
                coordinator_contact = ui.input("Contacto", value=point.coordinator_contact).classes("w-full")
                ui.button(
                    "Guardar información",
                    on_click=lambda: apply(
                        lambda: update_point_info(
                            point,
                            admin_token,
                            description.value or "",
                            coordinator_contact.value or "",
                            update_help_point_info,
                        )
                    ),
                ).classes("w-full min-h-[44px]")
                ui.label("Necesidades").classes("text-h6")
                for need in point.needs:
                    with ui.card().classes("w-full"):
                        public_statuses = status_options()
                        options = {
                            status: label for label, status in public_statuses.items()
                        }
                        ui.label(category_name(categories, need.category_id))
                        ui.label(options[need.status])
                        selected_status = ui.select(
                            options=options, label="Estado", value=need.status
                        ).classes("w-full")
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
                        ).classes("w-full min-h-[44px]")
                        ui.button(
                            "Quitar",
                            on_click=lambda need_id=need.id: apply(
                                lambda: remove_need_from_point(
                                    point, admin_token, need_id, remove_need
                                )
                            ),
                        ).classes("w-full min-h-[44px]")
                category = ui.select(options=list(categories), label="Agregar necesidad").classes("w-full")
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
                ).classes("w-full min-h-[44px]")
                ui.button(
                    "Desactivar punto",
                    on_click=lambda: apply(
                        lambda: deactivate_point(point, admin_token, deactivate_help_point)
                    ),
                ).classes("w-full min-h-[44px]")

        render_content()
