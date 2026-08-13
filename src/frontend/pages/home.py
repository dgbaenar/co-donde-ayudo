"""Public mobile-first page for active help points."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from uuid import UUID

from nicegui import ui

from backend.domain.models import HelpPointCategory, Need, PublicHelpPoint
from frontend.components.help_point_map import (
    category_badge_classes,
    category_pin_color,
    describe_affected_areas,
    format_relative_time,
    format_short_date,
    format_short_datetime,
    render_help_point_map,
)

ListDepartments = Callable[[], Sequence[str]]
ListLocalities = Callable[[str], Sequence[str]]

_NEED_STATUS_PRIORITY = {"NEEDS_HELP": 0, "HELP_ON_THE_WAY": 1, "COVERED": 2}


def needs_preview_text(
    needs: Sequence[Need],
    category_names: Mapping[UUID, str],
    *,
    limit: int = 2,
) -> str | None:
    """Describe the most urgent need names, up to `limit`, or None if empty."""
    if not needs:
        return None
    ordered = sorted(
        needs,
        key=lambda need: (
            _NEED_STATUS_PRIORITY[need.status.value],
            category_names.get(need.category_id, "Necesidad").casefold(),
        ),
    )
    names = [category_names.get(need.category_id, "Necesidad") for need in ordered[:limit]]
    remaining = len(ordered) - limit
    text = f"Necesita: {', '.join(names)}"
    if remaining > 0:
        text += f" +{remaining} más"
    return text


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


def latest_activity_text(points: Sequence[PublicHelpPoint]) -> str | None:
    """Describe how recently any of the given points was updated, or None if empty."""
    if not points:
        return None
    latest = max(point.updated_at for point in points)
    relative = format_relative_time(latest)
    if relative:
        return f"Última actividad: {relative}"
    return f"Última actividad: el {format_short_datetime(latest)}"


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

    selected_category: HelpPointCategory | str = ""

    def select_category(category: HelpPointCategory | str) -> None:
        nonlocal selected_category
        selected_category = category
        refresh()

    def render_category_chip(
        label: str, color: str, count: int, *, is_selected: bool, value: HelpPointCategory | str
    ) -> None:
        chip_classes = (
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm "
            "font-semibold cursor-pointer transition-colors shrink-0 "
        )
        if is_selected:
            chip_classes += f"text-white bg-[{color}]"
        else:
            chip_classes += (
                "bg-white border border-slate-200 text-slate-700 "
                f"hover:border-[{color}]"
            )
        with ui.row().classes(chip_classes).on(
            "click", lambda: select_category(value)
        ):
            if not is_selected:
                ui.element("div").classes(
                    f"w-2 h-2 rounded-full bg-[{color}] shrink-0"
                )
            ui.label(label)
            ui.label(str(count)).classes(
                "text-xs " + ("text-white/80" if is_selected else "text-slate-400")
            )

    def render_category_chips() -> None:
        category_chips.clear()
        with category_chips:
            location_filtered = filter_public_help_points(
                active_points,
                city=city.value or "",
                department=department.value or "",
            )
            render_category_chip(
                "Todas las categorías",
                "#003893",
                len(location_filtered),
                is_selected=selected_category == "",
                value="",
            )
            for point_category in HelpPointCategory:
                render_category_chip(
                    point_category.value,
                    category_pin_color(point_category),
                    len(
                        filter_public_help_points(
                            location_filtered, category=point_category
                        )
                    ),
                    is_selected=selected_category == point_category,
                    value=point_category,
                )

    def refresh() -> None:
        render_category_chips()
        filtered_points = filter_public_help_points(
            active_points,
            city=city.value or "",
            department=department.value or "",
            category=selected_category,
        )
        activity_indicator.clear()
        activity_text = latest_activity_text(filtered_points)
        if activity_text:
            with activity_indicator:
                ui.icon("schedule").classes("text-slate-500 text-sm").props(
                    "aria-hidden=true"
                )
                ui.label(activity_text).classes("text-xs text-slate-500")
        map_container.clear()
        with map_container:
            render_help_point_map(filtered_points, categories)
        results.clear()
        with results:
            with ui.row().classes("w-full items-center justify-between gap-2"):
                ui.label("Puntos que necesitan ayuda").classes(
                    "text-xl font-bold text-slate-900"
                )
                ui.label(f"{len(filtered_points)} resultados").classes(
                    "text-xs font-semibold text-white bg-[#003893] "
                    "rounded-full px-3 py-1 whitespace-nowrap"
                )
            if not active_points:
                ui.label("Todavía no hay puntos de ayuda activos.")
            elif not filtered_points:
                ui.label(
                    "No encontramos puntos con estos filtros. "
                    "Prueba con otro departamento, ciudad / municipio o categoría."
                )
            with ui.grid().classes("w-full grid-cols-1 sm:grid-cols-2 gap-3"):
                for point in filtered_points:
                    with ui.link(target=f"/puntos/{point.id}").classes(
                        "w-full min-h-[160px] no-underline text-inherit bg-white "
                        f"border-l-4 border-[{category_pin_color(point.category)}] "
                        "rounded-2xl shadow-sm hover:shadow-md transition-shadow"
                    ):
                        with ui.column().classes("w-full gap-2 p-4"):
                            with ui.row().classes(
                                "w-full items-center justify-between gap-2"
                            ):
                                ui.label(point.category.value).classes(
                                    category_badge_classes(point.category)
                                )
                                ui.icon("chevron_right").classes(
                                    "text-emerald-700 shrink-0"
                                ).props("aria-hidden=true")
                            with ui.row().classes(
                                "w-full items-center gap-2 flex-nowrap"
                            ):
                                ui.icon("circle").classes(
                                    indicator_classes(point)
                                ).props("aria-hidden=true")
                                ui.label(point.name).classes(
                                    "text-base font-semibold text-slate-900"
                                )
                            ui.label(f"📍 {affected_area_text(point)}").classes(
                                "text-xs text-slate-500 line-clamp-1"
                            )
                            with ui.row().classes(
                                "w-full items-center justify-between gap-2 flex-nowrap"
                            ):
                                preview = needs_preview_text(point.needs, category_names)
                                ui.label(preview or "Sin necesidades registradas").classes(
                                    "flex-1 min-w-0 truncate "
                                    + (
                                        "text-xs font-medium text-slate-700"
                                        if preview
                                        else "text-xs text-slate-400"
                                    )
                                )
                                ui.label(
                                    f"Publicado el {format_short_date(point.created_at)}"
                                ).classes(
                                    "shrink-0 text-xs text-slate-400 whitespace-nowrap"
                                )

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

    with ui.column().classes("w-full min-h-screen bg-slate-50 text-slate-900"):
        with ui.row().classes("w-full gap-0 h-1.5"):
            ui.row().classes("flex-1 h-1.5 bg-[#FCD116]")
            ui.row().classes("flex-1 h-1.5 bg-[#003893]")
            ui.row().classes("flex-1 h-1.5 bg-[#CE1126]")
        with ui.column().classes(
            "w-full items-center gap-3 bg-white border-b border-slate-200 "
            "py-8 px-4 text-center"
        ):
            with ui.column().classes("items-center gap-2"):
                ui.icon("location_on").classes(
                    "text-white "
                    "bg-[linear-gradient(to_bottom,#FCD116_50%,#003893_50%,"
                    "#003893_75%,#CE1126_75%)] rounded-xl p-2 text-xl shrink-0"
                ).props("aria-hidden=true")
                ui.label("¿Dónde ayudo?").classes(
                    "text-2xl sm:text-4xl font-bold leading-tight text-emerald-950"
                )
            ui.label(
                "Explora el mapa o revisa la lista de puntos activos y ayudemos "
                "juntos a Colombia."
            ).classes("text-sm md:text-base text-slate-600 max-w-xl")
            activity_indicator = ui.row().classes("items-center justify-center gap-1")
            with ui.row().classes(
                "flex-col sm:flex-row items-center justify-center gap-3 w-full sm:w-auto"
            ):
                ui.link("Encontrar cómo ayudar", "#resultados").classes(
                    "min-h-[48px] flex items-center justify-center w-full sm:w-64 "
                    "px-6 text-base rounded-2xl font-medium bg-[#003893] text-white "
                    "hover:bg-[#002d76] no-underline shadow-sm"
                )
                ui.link("Crear iniciativa", "/crear").classes(
                    "min-h-[48px] flex items-center justify-center w-full sm:w-64 "
                    "px-6 text-base rounded-2xl font-medium bg-[#003893] text-white "
                    "hover:bg-[#002d76] no-underline shadow-sm"
                )
        with ui.column().classes("w-full max-w-7xl mx-auto gap-6 p-4"):
            with ui.column().classes(
                "w-full gap-1 rounded-2xl bg-white p-4 border-l-4 border-red-600 "
                "shadow-sm"
            ):
                ui.label("Emergencia activa").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-600"
                )
                ui.label("Respuesta al terremoto de Chocó").classes(
                    "text-lg sm:text-xl font-semibold text-slate-900"
                )
                ui.label("Terremoto del 10 de agosto de 2026").classes(
                    "text-xs font-medium text-red-700"
                )
                ui.label(
                    "Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, "
                    "Valle del Cauca, Risaralda y Quindío."
                ).classes("text-sm leading-relaxed text-slate-600")
            with ui.column().classes(
                "w-full gap-3 rounded-2xl bg-white p-4 shadow-sm"
            ).props("id=resultados"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("filter_alt").classes("text-[#003893]").props(
                        "aria-hidden=true"
                    )
                    ui.label("Filtros").classes(
                        "text-base font-bold text-slate-800"
                    )
                category_chips = ui.row().classes(
                    "w-full flex-nowrap sm:flex-wrap gap-2 overflow-x-auto "
                    "sm:overflow-visible pb-1"
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
                        "w-full sm:w-auto sm:flex-1 sm:min-w-0"
                    ).props(
                        'filled rounded behavior=menu color=blue-grey-9 '
                        'transition-show=none transition-hide=none '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
                    city = ui.select(
                        options=empty_city_options(),
                        value="",
                        label="Ciudad / Municipio",
                        on_change=refresh,
                    ).classes(
                        "w-full sm:w-auto sm:flex-1 sm:min-w-0"
                    ).props(
                        'filled rounded behavior=menu color=blue-grey-9 '
                        'transition-show=none transition-hide=none '
                        'popup-content-class=bounded-select-menu '
                        'popup-content-style="max-height: 40vh !important; overflow-y: auto"'
                    )
                    city.disable()
            with ui.grid().classes(
                "w-full grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 items-start"
            ):
                map_container = ui.column().classes(
                    "w-full overflow-hidden rounded-2xl bg-white shadow-sm"
                )
                results = ui.column().classes("w-full gap-3")
            refresh()
