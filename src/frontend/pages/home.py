"""Public mobile-first page for active help points."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from uuid import UUID

from nicegui import ui

from backend.domain.models import HelpPointCategory, PublicHelpPoint
from frontend.components.help_point_map import (
    describe_affected_areas,
    format_relative_time,
    format_short_date,
    format_short_datetime,
    render_help_point_map,
    status_line,
)

ListDepartments = Callable[[], Sequence[str]]
ListLocalities = Callable[[str], Sequence[str]]

_CATEGORY_BADGE_CLASSES: dict[HelpPointCategory, str] = {
    HelpPointCategory.DONATION_COLLECTION: "text-emerald-800 bg-emerald-50 border-emerald-200",
    HelpPointCategory.DEBRIS_REMOVAL: "text-amber-800 bg-amber-50 border-amber-200",
    HelpPointCategory.RESCUE_OPERATIONS: "text-red-800 bg-red-50 border-red-200",
    HelpPointCategory.PSYCHOLOGICAL_SUPPORT: "text-violet-800 bg-violet-50 border-violet-200",
    HelpPointCategory.MEDICAL_CARE: "text-sky-800 bg-sky-50 border-sky-200",
    HelpPointCategory.HOUSING_AND_SHELTER: "text-orange-800 bg-orange-50 border-orange-200",
    HelpPointCategory.COMMUNITY_FOOD: "text-lime-800 bg-lime-50 border-lime-200",
    HelpPointCategory.VOLUNTEERING: "text-indigo-800 bg-indigo-50 border-indigo-200",
    HelpPointCategory.BLOOD_DONATION: "text-rose-800 bg-rose-50 border-rose-200",
}


def category_badge_classes(category: HelpPointCategory) -> str:
    """Return the badge color classes for a point's category, one per category."""
    colors = _CATEGORY_BADGE_CLASSES[category]
    return (
        f"text-xs font-medium {colors} border rounded-full px-2 py-0.5 self-start"
    )


def filter_public_help_points(
    points: Sequence[PublicHelpPoint],
    *,
    city: str = "",
    department: str = "",
    category: HelpPointCategory | str = "",
) -> tuple[PublicHelpPoint, ...]:
    """Return active points matching the public location and category filters."""
    return tuple(
        point
        for point in points
        if point.active
        and (
            not city
            or any(area.city == city for area in point.affected_areas)
        )
        and (
            not department
            or any(area.department == department for area in point.affected_areas)
        )
        and (not category or point.category == category)
    )


def affected_area_text(point: PublicHelpPoint) -> str:
    """Describe every affected area, grouped by department."""
    return describe_affected_areas(point.affected_areas)


def freshness_text(point: PublicHelpPoint) -> str:
    """Describe how recently the point was updated, relative or absolute."""
    relative = format_relative_time(point.updated_at)
    if relative:
        return f"Actualizado {relative}"
    return f"Actualizado el {format_short_datetime(point.updated_at)}"


def location_filter_options(
    list_departments: ListDepartments,
    list_localities: ListLocalities,
    *,
    department: str = "",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    departments = tuple(list_departments())
    cities = tuple(list_localities(department)) if department else ()
    return departments, cities


def render_home(
    points: Sequence[PublicHelpPoint],
    categories: Mapping[str, UUID],
    list_departments: ListDepartments,
    list_localities: ListLocalities,
) -> None:
    """Render active public points and the two location filters."""
    category_names = {category_id: name for name, category_id in categories.items()}
    active_points = filter_public_help_points(points)
    departments, _ = location_filter_options(list_departments, list_localities)

    def department_options(values: Sequence[str]) -> dict[str, str]:
        return {"": "Todos los departamentos", **{value: value for value in values}}

    def city_options(values: Sequence[str]) -> dict[str, str]:
        return {
            "": "Todas las ciudades / municipios",
            **{value: value for value in values},
        }

    def point_category_options() -> dict[HelpPointCategory | str, str]:
        return {
            "": "Todas las categorías",
            **{category: category.value for category in HelpPointCategory},
        }

    def empty_city_options() -> dict[str, str]:
        return {"": "Selecciona primero un departamento"}

    def indicator_classes(point: PublicHelpPoint) -> str:
        if not point.needs:
            return "text-slate-300 text-[10px] mt-1"
        return {
            "NEEDS_HELP": "text-red-500 text-[10px] mt-1",
            "HELP_ON_THE_WAY": "text-amber-500 text-[10px] mt-1",
            "COVERED": "text-emerald-600 text-[10px] mt-1",
        }[point.needs[0].status.value]

    def refresh() -> None:
        filtered_points = filter_public_help_points(
            active_points,
            city=city.value or "",
            department=department.value or "",
            category=point_category.value or "",
        )
        map_container.clear()
        with map_container:
            render_help_point_map(filtered_points, categories)
        results.clear()
        with results:
            ui.label(
                f"Puntos que necesitan ayuda — {len(filtered_points)} resultados"
            ).classes("text-h6")
            if not active_points:
                ui.label("Todavía no hay puntos de ayuda activos.")
            elif not filtered_points:
                ui.label(
                    "No encontramos puntos con estos filtros. "
                    "Prueba con otro departamento, ciudad / municipio o categoría."
                )
            for point in filtered_points:
                status_priority = {
                    "NEEDS_HELP": 0,
                    "HELP_ON_THE_WAY": 1,
                    "COVERED": 2,
                }
                ordered_needs = sorted(
                    point.needs,
                    key=lambda need: (
                        status_priority[need.status.value],
                        category_names.get(need.category_id, "Necesidad").casefold(),
                    ),
                )
                with ui.link(target=f"/puntos/{point.id}").classes(
                    "w-full min-h-[44px] no-underline text-inherit bg-white "
                    "border border-slate-200 rounded-xl shadow-sm"
                ):
                    with ui.row().classes("w-full items-start gap-3 p-3 flex-nowrap"):
                        ui.icon("circle").classes(indicator_classes(point)).props(
                            "aria-hidden=true"
                        )
                        with ui.column().classes("flex-1 min-w-0 gap-1"):
                            ui.label(point.name).classes("font-semibold text-slate-900")
                            ui.label(freshness_text(point)).classes(
                                "text-sm font-bold text-emerald-700 bg-emerald-50 "
                                "border border-emerald-200 rounded-full px-3 py-1 "
                                "self-start whitespace-nowrap"
                            )
                            ui.label(point.category.value).classes(
                                category_badge_classes(point.category)
                            )
                            ui.label(
                                f"Ayuda destinada a: {affected_area_text(point)}"
                            ).classes(
                                "text-xs text-slate-500"
                            )
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
                                ui.label(
                                    f"Recibe ayuda en: {reception_location}"
                                ).classes("text-xs text-slate-500")
                            ui.label(point.description).classes(
                                "text-sm text-slate-700 line-clamp-2"
                            )
                            with ui.row().classes("w-full flex-wrap gap-x-2 gap-y-1"):
                                for need in ordered_needs[:3]:
                                    category_name = category_names.get(
                                        need.category_id, "Necesidad"
                                    )
                                    ui.label(
                                        status_line(need.status, category_name)
                                    ).classes("text-xs")
                                remaining_needs = len(ordered_needs) - 3
                                if remaining_needs > 0:
                                    ui.label(f"+{remaining_needs} necesidades").classes(
                                        "text-xs text-slate-500"
                                    )
                        with ui.column().classes("items-end gap-1 shrink-0"):
                            ui.label(
                                f"Publicado el {format_short_date(point.created_at)}"
                            ).classes("text-xs text-slate-400 whitespace-nowrap")
                            ui.icon("chevron_right").classes(
                                "text-emerald-700"
                            ).props("aria-hidden=true")

    def change_department() -> None:
        selected_department = department.value or ""
        city.value = ""
        if selected_department:
            _, filtered_cities = location_filter_options(
                list_departments,
                list_localities,
                department=selected_department,
            )
            city.options = city_options(filtered_cities)
            city.enable()
        else:
            city.options = empty_city_options()
            city.disable()
        city.update()
        refresh()

    with ui.column().classes("w-full min-h-screen bg-white text-slate-900"):
        with ui.column().classes("w-full max-w-7xl mx-auto gap-4 p-4"):
            with ui.row().classes(
                "w-full items-center justify-between gap-3 flex-wrap sm:flex-nowrap"
            ):
                with ui.row().classes(
                    "w-full sm:w-auto items-center gap-2 min-w-0 flex-1 flex-nowrap"
                ):
                    ui.icon("location_on").classes(
                        "text-white bg-emerald-700 rounded-xl p-2 text-xl shrink-0"
                    ).props("aria-hidden=true")
                    ui.label("¿Dónde ayudo?").classes(
                        "text-lg sm:text-2xl font-semibold leading-tight "
                        "text-emerald-950 whitespace-nowrap"
                    )
                ui.link("Crear nuevo punto de ayuda o recolección", "/crear").classes(
                    "w-full sm:w-auto min-h-[48px] flex items-center justify-center "
                    "px-4 text-base rounded-lg font-medium bg-emerald-700 text-white "
                    "hover:bg-emerald-800 no-underline shadow-sm shrink-0"
                )
            with ui.column().classes("w-full gap-1 max-w-3xl"):
                ui.label("Explora el mapa o revisa la lista de puntos activos.").classes(
                    "text-sm md:text-base text-slate-600"
                )
            with ui.column().classes(
                "w-full gap-1 rounded-2xl bg-slate-100 p-4"
            ):
                ui.label("Emergencia activa").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-600"
                )
                ui.label("Respuesta al terremoto de Chocó").classes(
                    "text-lg sm:text-xl font-semibold text-slate-900"
                )
                ui.label(
                    "Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, "
                    "Valle del Cauca, Risaralda y Quindío."
                ).classes("text-sm leading-relaxed text-slate-600")
            with ui.column().classes(
                "w-full gap-2 rounded-2xl bg-slate-100 p-3"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("filter_alt").classes("text-slate-700").props(
                        "aria-hidden=true"
                    )
                    ui.label("Filtros").classes(
                        "text-sm font-semibold text-slate-800"
                    )
                with ui.row().classes(
                    "w-full gap-3 flex-col sm:flex-row sm:flex-nowrap"
                ):
                    department = ui.select(
                        options=department_options(departments),
                        value="",
                        label="Departamento",
                        on_change=change_department,
                    ).classes(
                        "w-full sm:w-auto sm:flex-1 sm:min-w-0 bg-white rounded-lg"
                    ).props(
                        'outlined dense behavior=menu color=blue-grey-9 '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
                    city = ui.select(
                        options=empty_city_options(),
                        value="",
                        label="Ciudad / Municipio",
                        on_change=refresh,
                    ).classes(
                        "w-full sm:w-auto sm:flex-1 sm:min-w-0 bg-white rounded-lg"
                    ).props(
                        'outlined dense behavior=menu color=blue-grey-9 '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
                    city.disable()
                    point_category = ui.select(
                        options=point_category_options(),
                        value="",
                        label="Categoría del punto",
                        on_change=refresh,
                    ).classes(
                        "w-full sm:w-auto sm:flex-1 sm:min-w-0 bg-white rounded-lg"
                    ).props(
                        'outlined dense behavior=menu color=blue-grey-9 '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
            with ui.grid().classes(
                "w-full grid-cols-1 lg:grid-cols-[3fr_2fr] gap-4 items-start"
            ):
                map_container = ui.column().classes(
                    "w-full overflow-hidden rounded-2xl bg-white shadow-sm"
                )
                results = ui.column().classes("w-full gap-3")
            refresh()
