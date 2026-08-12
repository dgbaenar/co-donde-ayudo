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
_CUSTOM_CATEGORY_PLACEHOLDER_ID = UUID(int=0)
_PUBLICATION_FAILURE_MESSAGE = "No fue posible publicar el punto. Inténtalo de nuevo."


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

    return CreateHelpPoint(
        name=values.name.strip(),
        description=values.description.strip(),
        affected_city=values.affected_city.strip(),
        affected_department=values.affected_department.strip(),
        city=values.city.strip(),
        department=values.department.strip(),
        address=values.address.strip(),
        latitude=values.latitude,
        longitude=values.longitude,
        coordinator_name=values.coordinator_name.strip(),
        coordinator_contact=values.coordinator_contact.strip(),
        category_ids=category_ids,
    )


def publish_help_point(
    values: FormValues,
    selected_categories: Sequence[str],
    categories: Mapping[str, UUID],
    custom_category_name: str,
    create_custom_category: CreateCustomCategoryHandler,
    create_help_point: CreateHelpPointHandler,
) -> str:
    custom_category_name = custom_category_name.strip()
    if custom_category_name:
        selected_categories = (*selected_categories, custom_category_name)
        build_command(
            values,
            selected_categories,
            {
                **categories,
                custom_category_name: _CUSTOM_CATEGORY_PLACEHOLDER_ID,
            },
        )
        try:
            custom_category_id = create_custom_category(custom_category_name)
        except Exception as error:
            raise _PublicationHandlerError from error
        categories = {**categories, custom_category_name: custom_category_id}

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

    def update_locality_select(department_select, locality_select) -> None:
        locality_select.value = ""
        selected_department = department_select.value or ""
        if selected_department:
            localities = tuple(list_localities(selected_department))
            locality_select.options = {
                "": "Selecciona una ciudad / municipio",
                **{locality: locality for locality in localities},
            }
            locality_select.enable()
        else:
            locality_select.options = {"": "Selecciona primero un departamento"}
            locality_select.disable()
        locality_select.update()

    def change_affected_department() -> None:
        update_locality_select(affected_department, affected_city)

    def change_department() -> None:
        update_locality_select(department, city)

    departments = tuple(list_departments())
    affected_departments = tuple(list_affected_departments())
    with ui.column().classes("w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4"):
        form_container = ui.column().classes("w-full gap-3")
        with form_container:
            ui.label("Crear punto de ayuda").classes("text-h5")
            name = ui.input("Nombre del lugar").classes("w-full")
            description = ui.textarea("¿Qué está pasando?").classes("w-full")
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
                label="Ciudad / Municipio afectado",
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            affected_city.disable()
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
            ).classes("w-full").props(_BOUNDED_MENU_PROPS)
            custom_category_name = ui.input("+ Agregar otra necesidad").classes(
                "w-full"
            )

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
                )
                submitting = True
                publish_button.disable()
                try:
                    admin_path = publish_help_point(
                        values,
                        selected_categories.value or (),
                        categories,
                        custom_category_name.value or "",
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
