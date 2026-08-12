"""NiceGUI creation page for a help point."""
# style-guard: E6-exempt — cohesive single-page NiceGUI form; the UI is built in one render function sharing closure state and validation, so splitting it would fragment that state without reducing complexity.

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from nicegui import ui

from backend.domain.models import (
    AffectedArea,
    CreatedHelpPoint,
    CreateHelpPoint,
    HelpPointCategory,
    NewHelpPointLocation,
)
from frontend.components.location_picker import render_location_picker

logger = logging.getLogger(__name__)


CreateHelpPointHandler = Callable[[CreateHelpPoint], CreatedHelpPoint]
CreateCustomCategoryHandler = Callable[[str], UUID]
ListDepartments = Callable[[], Sequence[str]]
ListLocalities = Callable[[str], Sequence[str]]
GeocodeAddress = Callable[[str, str, str], Awaitable[object | None]]

_BOUNDED_MENU_PROPS = (
    'outlined dense behavior=menu color=blue-grey-9 '
    'transition-show=none transition-hide=none '
    'popup-content-class=bounded-select-menu '
    'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
)
_NEEDS_MULTISELECT_PROPS = f"{_BOUNDED_MENU_PROPS} use-chips"
_CUSTOM_CATEGORY_PLACEHOLDER_ID = UUID(int=0)
_PUBLICATION_FAILURE_MESSAGE = "No fue posible publicar el punto. Inténtalo de nuevo."
_DUPLICATE_CUSTOM_CATEGORY_MESSAGE = "Esa necesidad ya está en la lista."
_DUPLICATE_LINK_MESSAGE = "Ese enlace ya está en la lista."
_LOW_CONFIDENCE_ADDRESS_MESSAGE = "Toca el mapa para ubicar el punto correctamente."


class _PublicationHandlerError(Exception):
    """Hide backend-handler details from the presentation layer."""


@dataclass(frozen=True, slots=True)
class LocationValues:
    address: str
    city: str
    department: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True, slots=True)
class AffectedAreaValues:
    department: str
    city: str


@dataclass(frozen=True, slots=True)
class FormValues:
    name: str
    description: str
    affected_areas: tuple[AffectedAreaValues, ...]
    locations: tuple[LocationValues, ...]
    coordinator_name: str
    coordinator_contact: str
    category: str
    additional_affected_areas: str | None = ""


def build_admin_url(app_base_url: str, admin_path: str) -> str:
    """Build an absolute private URL from the configured public origin."""
    parsed = urlsplit(app_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/{admin_path.lstrip('/')}"


def build_command(
    values: FormValues,
    selected_categories: Sequence[str],
    categories: Mapping[str, UUID],
    important_links: Sequence[str] = (),
) -> CreateHelpPoint:
    if not values.locations:
        raise ValueError("Agrega al menos una ubicación.")
    if any(
        location.latitude is None or location.longitude is None
        for location in values.locations
    ):
        raise ValueError("Selecciona una ubicación en el mapa.")
    if not values.affected_areas:
        raise ValueError("Agrega al menos una zona afectada.")
    try:
        category_ids = tuple(categories[name] for name in selected_categories)
    except KeyError as error:
        raise ValueError(f"unknown category: {error.args[0]}") from error

    try:
        category = HelpPointCategory(values.category)
        return CreateHelpPoint(
            name=values.name.strip(),
            description=values.description.strip(),
            affected_areas=tuple(
                AffectedArea(
                    department=area.department.strip(),
                    city=area.city.strip() or None,
                )
                for area in values.affected_areas
            ),
            locations=tuple(
                NewHelpPointLocation(
                    address=location.address.strip(),
                    city=location.city.strip(),
                    department=location.department.strip(),
                    latitude=location.latitude,
                    longitude=location.longitude,
                )
                for location in values.locations
            ),
            coordinator_name=values.coordinator_name.strip(),
            coordinator_contact=values.coordinator_contact.strip(),
            category_ids=category_ids,
            category=category,
            additional_affected_areas=(values.additional_affected_areas or "").strip() or None,
            important_links=tuple(important_links),
        )
    except ValueError as error:
        raise ValueError(
            "Completa todos los campos obligatorios antes de publicar."
        ) from error


def publish_help_point(
    values: FormValues,
    selected_categories: Sequence[str],
    categories: Mapping[str, UUID],
    create_custom_category: CreateCustomCategoryHandler,
    create_help_point: CreateHelpPointHandler,
    important_links: Sequence[str] = (),
) -> str:
    unknown_names = [name for name in selected_categories if name not in categories]
    if unknown_names:
        # Each unknown name gets its own placeholder UUID: CreateHelpPoint rejects
        # duplicate category IDs, so reusing a single placeholder across two or
        # more unknown names would make this pre-validation fail spuriously.
        placeholder_ids = {
            name: UUID(int=_CUSTOM_CATEGORY_PLACEHOLDER_ID.int + index)
            for index, name in enumerate(unknown_names)
        }
        build_command(
            values,
            selected_categories,
            {**categories, **placeholder_ids},
            important_links,
        )
        try:
            created_ids = [create_custom_category(name) for name in unknown_names]
        except Exception as error:
            raise _PublicationHandlerError from error
        categories = {
            **categories,
            **{name: category_id for name, category_id in zip(unknown_names, created_ids)},
        }

    command = build_command(values, selected_categories, categories, important_links)
    try:
        created = create_help_point(command)
        return f"/administrar/{created.admin_token}"
    except Exception as error:
        raise _PublicationHandlerError from error


def render_create_help_point(
    categories: Mapping[str, UUID],
    create_help_point: CreateHelpPointHandler,
    create_custom_category: CreateCustomCategoryHandler,
    list_departments: ListDepartments,
    list_localities: ListLocalities,
    list_affected_departments: ListDepartments,
    geocode_address: GeocodeAddress,
    app_base_url: str,
) -> None:
    """Render the creation page using only injected backend-facing dependencies."""

    submitting = False
    published = False

    def update_locality_select(
        department_select,
        locality_select,
        *,
        no_selection_label: str = "Selecciona una ciudad / municipio",
    ) -> None:
        locality_select.value = ""
        selected_department = department_select.value or ""
        if selected_department:
            localities = tuple(list_localities(selected_department))
            locality_select.options = {
                "": no_selection_label,
                **{locality: locality for locality in localities},
            }
            locality_select.enable()
        else:
            locality_select.options = {"": "Selecciona primero un departamento"}
            locality_select.disable()
        locality_select.update()

    departments = tuple(list_departments())
    affected_departments = tuple(list_affected_departments())
    with ui.column().classes("w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4"):
        form_container = ui.column().classes("w-full gap-3")
        with form_container:
            ui.label("Crear punto de ayuda").classes("text-h5")
            name = ui.input("Nombre del lugar").classes("w-full")
            description = ui.textarea(
                "¿Qué está pasando en este punto?",
                placeholder=(
                    "Ej: Varias familias fueron evacuadas y estamos "
                    "organizando ayuda desde este parque."
                ),
            ).classes("w-full")
            category = ui.select(
                options={"": "Selecciona una categoría", **{
                    member.value: member.value for member in HelpPointCategory
                }},
                value="",
                label="Categoría del punto",
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            ui.label("Zona que recibirá la ayuda").classes("text-h6")
            affected_areas_container = ui.column().classes("w-full gap-2")
            affected_area_blocks: list[dict] = []

            def render_affected_area_block() -> dict:
                with affected_areas_container:
                    with ui.card().classes(
                        "w-full gap-2 rounded-xl border border-slate-200 p-3"
                    ) as block_card:
                        block_department = ui.select(
                            options={
                                "": "Selecciona un departamento",
                                **{
                                    department: department
                                    for department in affected_departments
                                },
                            },
                            value="",
                            label="Departamento afectado",
                        ).classes("w-full").props(_BOUNDED_MENU_PROPS)
                        block_city = ui.select(
                            options={"": "Selecciona primero un departamento"},
                            value="",
                            label="Ciudad / Municipio afectado (opcional)",
                        ).classes("w-full").props(_BOUNDED_MENU_PROPS)
                        block_city.disable()

                        def change_block_department() -> None:
                            update_locality_select(
                                block_department,
                                block_city,
                                no_selection_label=(
                                    "Toda la zona del departamento (opcional)"
                                ),
                            )

                        block_department.on_value_change(change_block_department)

                        block = {"department": block_department, "city": block_city}
                        affected_area_blocks.append(block)

                        def remove_affected_area() -> None:
                            affected_area_blocks.remove(block)
                            block_card.visible = False

                        ui.button(
                            "Quitar", on_click=remove_affected_area
                        ).classes("w-full min-h-[44px]").props("flat color=red-9")

                        return block

            render_affected_area_block()
            ui.button(
                "Agregar otra zona afectada", on_click=render_affected_area_block
            ).classes("w-full min-h-[44px]").props("outline")
            additional_affected_areas = ui.textarea(
                "¿Hay otras zonas que también recibirán ayuda? (opcional)"
            ).classes("w-full")
            ui.label("Dónde se recibe o coordina la ayuda").classes("text-h6")
            locations_container = ui.column().classes("w-full gap-2")
            location_blocks: list[dict] = []

            def render_location_block() -> dict:
                with locations_container:
                    with ui.card().classes(
                        "w-full gap-2 rounded-xl border border-slate-200 p-3"
                    ) as block_card:
                        block_department = ui.select(
                            options={
                                "": "Selecciona un departamento",
                                **{
                                    department: department
                                    for department in departments
                                },
                            },
                            value="",
                            label="Departamento del punto",
                        ).classes("w-full").props(_BOUNDED_MENU_PROPS)
                        block_city = ui.select(
                            options={"": "Selecciona primero un departamento"},
                            value="",
                            label="Ciudad / Municipio del punto",
                        ).classes("w-full").props(_BOUNDED_MENU_PROPS)
                        block_city.disable()
                        block_address = ui.input(
                            "Dirección o referencia del lugar"
                        ).classes("w-full")

                        def change_block_department() -> None:
                            update_locality_select(block_department, block_city)

                        block_department.on_value_change(change_block_department)

                        block_location = render_location_picker()

                        async def search_address() -> None:
                            address_value = (block_address.value or "").strip()
                            city_value = block_city.value or ""
                            department_value = block_department.value or ""
                            if (
                                not address_value
                                or not city_value
                                or not department_value
                            ):
                                ui.notify(
                                    "Completa departamento, ciudad / municipio y "
                                    "dirección.",
                                    type="negative",
                                )
                                return
                            try:
                                geocoded = await geocode_address(
                                    address_value,
                                    city_value,
                                    department_value,
                                )
                            except Exception:
                                geocoded = None
                            if geocoded is None:
                                ui.notify(
                                    "No encontramos esa dirección. "
                                    "Ubícala tocando el mapa.",
                                    type="negative",
                                )
                                return
                            block_location.set_coordinates(
                                geocoded.latitude, geocoded.longitude
                            )
                            if geocoded.is_low_confidence:
                                ui.notify(
                                    _LOW_CONFIDENCE_ADDRESS_MESSAGE, type="warning"
                                )

                        ui.button(
                            "Buscar en el mapa", on_click=search_address
                        ).classes("w-full min-h-[44px]")

                        block = {
                            "department": block_department,
                            "city": block_city,
                            "address": block_address,
                            "location": block_location,
                        }
                        location_blocks.append(block)

                        def remove_location() -> None:
                            location_blocks.remove(block)
                            block_card.visible = False

                        ui.button("Quitar", on_click=remove_location).classes(
                            "w-full min-h-[44px]"
                        ).props("flat color=red-9")

                        return block

            render_location_block()
            ui.button(
                "Agregar otra ubicación", on_click=render_location_block
            ).classes("w-full min-h-[44px]").props("outline")
            coordinator_name = ui.input("Nombre de la persona coordinadora").classes(
                "w-full"
            )
            coordinator_contact = ui.input(
                "Contacto de la persona coordinadora"
            ).classes("w-full")
            selected_categories = ui.select(
                options=list(categories),
                label="Necesidades",
                multiple=True,
            ).classes("w-full").props(_NEEDS_MULTISELECT_PROPS)

            def add_custom_category() -> None:
                name = (custom_category_name.value or "").strip()
                if not name:
                    return
                if name in categories:
                    current_values = list(selected_categories.value or ())
                    if name not in current_values:
                        current_values.append(name)
                        selected_categories.value = current_values
                    custom_category_name.value = ""
                    return
                if name in selected_categories.options:
                    ui.notify(_DUPLICATE_CUSTOM_CATEGORY_MESSAGE, type="warning")
                    return
                selected_categories.options = [*selected_categories.options, name]
                selected_categories.value = [*(selected_categories.value or ()), name]
                selected_categories.update()
                custom_category_name.value = ""

            with ui.row().classes("w-full gap-2 items-end flex-nowrap"):
                custom_category_name = ui.input("+ Agregar otra necesidad").classes(
                    "flex-1 min-w-0"
                )
                ui.button("Agregar", on_click=add_custom_category).classes(
                    "min-h-[44px] shrink-0"
                )
            custom_category_name.on("keydown.enter", add_custom_category)

            important_links: list[str] = []

            def remove_link(url: str, row) -> None:
                if url in important_links:
                    important_links.remove(url)
                row.visible = False

            def add_link() -> None:
                url = (link_input.value or "").strip()
                if not url:
                    return
                if url in important_links:
                    ui.notify(_DUPLICATE_LINK_MESSAGE, type="warning")
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

            ui.label("Enlaces importantes").classes("text-h6")
            with ui.row().classes("w-full gap-2 items-end flex-nowrap"):
                link_input = ui.input("Enlace importante (URL)").classes(
                    "flex-1 min-w-0"
                )
                ui.button("Agregar enlace", on_click=add_link).classes(
                    "min-h-[44px] shrink-0"
                )
            link_input.on("keydown.enter", add_link)
            links_container = ui.column().classes("w-full gap-2")

            def submit() -> None:
                nonlocal submitting, published
                if submitting or published:
                    return

                values = FormValues(
                    name=name.value or "",
                    description=description.value or "",
                    affected_areas=tuple(
                        AffectedAreaValues(
                            department=block["department"].value or "",
                            city=block["city"].value or "",
                        )
                        for block in affected_area_blocks
                    ),
                    locations=tuple(
                        LocationValues(
                            address=block["address"].value or "",
                            city=block["city"].value or "",
                            department=block["department"].value or "",
                            latitude=block["location"].latitude,
                            longitude=block["location"].longitude,
                        )
                        for block in location_blocks
                    ),
                    coordinator_name=coordinator_name.value or "",
                    coordinator_contact=coordinator_contact.value or "",
                    category=category.value or "",
                    additional_affected_areas=additional_affected_areas.value or "",
                )
                submitting = True
                publish_button.disable()
                try:
                    admin_path = publish_help_point(
                        values,
                        selected_categories.value or (),
                        categories,
                        create_custom_category,
                        create_help_point,
                        tuple(important_links),
                    )
                except (TypeError, ValueError) as error:
                    ui.notify(str(error), type="negative")
                    return
                except _PublicationHandlerError:
                    logger.exception("failed to publish help point")
                    ui.notify(_PUBLICATION_FAILURE_MESSAGE, type="negative")
                    return
                else:
                    admin_url = build_admin_url(app_base_url, admin_path)
                    published = True
                    form_container.visible = False
                    success_container.clear()
                    with success_container:
                        ui.label("Punto de ayuda publicado").classes("text-h5")
                        ui.label(
                            "Este enlace es privado. Cópialo y guárdalo: lo necesitarás "
                            "para administrar el punto."
                        )
                        ui.label(
                            "Puedes compartirlo con otras personas de confianza para "
                            "que sigan coordinando cuando tú no puedas."
                        )
                        ui.input(
                            "Enlace privado de administración", value=admin_url
                        ).classes("w-full").props("readonly")

                        async def copy_admin_url() -> None:
                            script = (
                                "navigator.clipboard.writeText("
                                + json.dumps(admin_url)
                                + ").then(() => true).catch(() => false)"
                            )
                            try:
                                copied = bool(await ui.run_javascript(script))
                            except Exception:
                                copied = False
                            if copied:
                                ui.notify("Enlace privado copiado.", type="positive")
                            else:
                                ui.notify(
                                    "No se pudo copiar automáticamente. Mantén presionado "
                                    "el enlace y cópialo manualmente.",
                                    type="negative",
                                )

                        ui.button("Copiar enlace", on_click=copy_admin_url).classes(
                            "w-full min-h-[44px]"
                        )
                        ui.link("Abrir administración", admin_url).classes(
                            "w-full min-h-[44px] flex items-center justify-center"
                        )
                    success_container.visible = True
                finally:
                    submitting = False
                    if not published:
                        publish_button.enable()

            publish_button = ui.button(
                "Publicar punto de ayuda", on_click=submit
            ).classes("w-full min-h-[44px]")

        success_container = ui.column().classes("w-full gap-4")
        success_container.visible = False
