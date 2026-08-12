"""NiceGUI creation page for a help point."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import logging
from urllib.parse import urlsplit
from uuid import UUID

from nicegui import ui

from backend.domain.models import CreateHelpPoint, CreatedHelpPoint
from frontend.components.location_picker import render_location_picker

logger = logging.getLogger(__name__)


CreateHelpPointHandler = Callable[[CreateHelpPoint], CreatedHelpPoint]
CreateCustomCategoryHandler = Callable[[str], UUID]
CoordinatorAuthorizationCheck = Callable[[], bool]
ListDepartments = Callable[[], Sequence[str]]
ListLocalities = Callable[[str], Sequence[str]]
GeocodeAddress = Callable[[str, str, str], Awaitable[object | None]]

_BOUNDED_MENU_PROPS = (
    'outlined dense behavior=menu color=blue-grey-9 '
    'popup-content-class=bounded-select-menu '
    'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
)
_NEEDS_MULTISELECT_PROPS = f"{_BOUNDED_MENU_PROPS} use-chips"
_CUSTOM_CATEGORY_PLACEHOLDER_ID = UUID(int=0)
_PUBLICATION_FAILURE_MESSAGE = "No fue posible publicar el punto. Inténtalo de nuevo."
_DUPLICATE_CUSTOM_CATEGORY_MESSAGE = "Esa necesidad ya está en la lista."


class _PublicationHandlerError(Exception):
    """Hide backend-handler details from the presentation layer."""


@dataclass(frozen=True, slots=True)
class FormValues:
    name: str
    description: str
    affected_city: str
    affected_department: str
    city: str
    department: str
    address: str
    latitude: float | None
    longitude: float | None
    coordinator_name: str
    coordinator_contact: str
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
) -> CreateHelpPoint:
    if values.latitude is None or values.longitude is None:
        raise ValueError("Selecciona una ubicación en el mapa.")
    try:
        category_ids = tuple(categories[name] for name in selected_categories)
    except KeyError as error:
        raise ValueError(f"unknown category: {error.args[0]}") from error

    try:
        return CreateHelpPoint(
            name=values.name.strip(),
            description=values.description.strip(),
            affected_city=values.affected_city.strip() or None,
            affected_department=values.affected_department.strip(),
            city=values.city.strip(),
            department=values.department.strip(),
            address=values.address.strip(),
            latitude=values.latitude,
            longitude=values.longitude,
            coordinator_name=values.coordinator_name.strip(),
            coordinator_contact=values.coordinator_contact.strip(),
            category_ids=category_ids,
            additional_affected_areas=(values.additional_affected_areas or "").strip() or None,
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
        )
        try:
            created_ids = [create_custom_category(name) for name in unknown_names]
        except Exception as error:
            raise _PublicationHandlerError from error
        categories = {
            **categories,
            **{name: category_id for name, category_id in zip(unknown_names, created_ids)},
        }

    command = build_command(values, selected_categories, categories)
    try:
        created = create_help_point(command)
        return f"/administrar/{created.admin_token}"
    except Exception as error:
        raise _PublicationHandlerError from error


def render_create_help_point(
    categories: Mapping[str, UUID],
    create_help_point: CreateHelpPointHandler,
    create_custom_category: CreateCustomCategoryHandler,
    is_coordinator_authorized: CoordinatorAuthorizationCheck,
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

    def change_affected_department() -> None:
        update_locality_select(
            affected_department,
            affected_city,
            no_selection_label="Toda la zona del departamento (opcional)",
        )

    def change_department() -> None:
        update_locality_select(department, city)

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
            ui.label("Zona que recibirá la ayuda").classes("text-h6")
            affected_department = ui.select(
                options={
                    "": "Selecciona un departamento",
                    **{department: department for department in affected_departments},
                },
                value="",
                label="Departamento afectado",
                on_change=change_affected_department,
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            affected_city = ui.select(
                options={"": "Selecciona primero un departamento"},
                value="",
                label="Ciudad / Municipio afectado (opcional)",
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            affected_city.disable()
            additional_affected_areas = ui.textarea(
                "¿Hay otras zonas que también recibirán ayuda? (opcional)"
            ).classes("w-full")
            ui.label("Dónde se recibe o coordina la ayuda").classes("text-h6")
            department = ui.select(
                options={
                    "": "Selecciona un departamento",
                    **{department: department for department in departments},
                },
                value="",
                label="Departamento del punto",
                on_change=change_department,
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            city = ui.select(
                options={"": "Selecciona primero un departamento"},
                value="",
                label="Ciudad / Municipio del punto",
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            city.disable()
            address = ui.input("Dirección o referencia del lugar").classes("w-full")

            async def search_address() -> None:
                address_value = (address.value or "").strip()
                city_value = city.value or ""
                department_value = department.value or ""
                if not address_value or not city_value or not department_value:
                    ui.notify(
                        "Completa departamento, ciudad / municipio y dirección.",
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
                        "No encontramos esa dirección. Ubícala tocando el mapa.",
                        type="negative",
                    )
                    return
                location.set_coordinates(geocoded.latitude, geocoded.longitude)

            ui.button("Buscar en el mapa", on_click=search_address).classes(
                "w-full min-h-[44px]"
            )
            location = render_location_picker()
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

            def submit() -> None:
                nonlocal submitting, published
                if submitting or published:
                    return
                if not is_coordinator_authorized():
                    ui.notify(
                        "No fue posible autorizar la publicación.", type="negative"
                    )
                    ui.navigate.to("/acceso")
                    return

                values = FormValues(
                    name=name.value or "",
                    description=description.value or "",
                    affected_city=affected_city.value or "",
                    affected_department=affected_department.value or "",
                    city=city.value or "",
                    department=department.value or "",
                    address=address.value or "",
                    latitude=location.latitude,
                    longitude=location.longitude,
                    coordinator_name=coordinator_name.value or "",
                    coordinator_contact=coordinator_contact.value or "",
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
