"""Public mobile-first page for active help points."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
import logging
from typing import Any, Protocol
from uuid import UUID

from nicegui import ui

from backend.domain.models import HelpPointCategory, Need, PublicHelpPoint
from frontend.components.help_point_map import (
    build_popup_html,
    category_badge_classes,
    category_pin_color,
    describe_affected_areas,
    format_relative_time,
    format_short_date,
    format_short_datetime,
    pin_icon_html,
    render_help_point_map,
)

ListDepartments = Callable[[], Sequence[str]]
ListLocalities = Callable[[str], Sequence[str]]
ListActiveCategories = Callable[[], Mapping[str, UUID]]
OpenPublicHelpPointsSnapshot = Callable[[], tuple[datetime, int]]
ListPublicHelpPointsPage = Callable[..., Sequence[PublicHelpPoint]]
ProgressCallback = Callable[[tuple[PublicHelpPoint, ...], int, int, bool], None]


class CachedPublicHomeView(Protocol):
    points: Sequence[PublicHelpPoint]
    categories: Mapping[str, UUID]
    stale: bool


GetCachedPublicHome = Callable[[], CachedPublicHomeView | None]
BeginPublicHomeRefresh = Callable[[], Any | None]
FinishPublicHomeRefresh = Callable[
    [Any, tuple[PublicHelpPoint, ...], Mapping[str, UUID]], bool
]
AbortPublicHomeRefresh = Callable[[Any], None]
WaitForCachedPublicHome = Callable[..., CachedPublicHomeView | None]

_NEED_STATUS_PRIORITY = {"NEEDS_HELP": 0, "HELP_ON_THE_WAY": 1, "COVERED": 2}
PUBLIC_POINTS_BATCH_SIZE = 24
PUBLIC_POINTS_OPERATION_TIMEOUT_SECONDS = 15.0
logger = logging.getLogger(__name__)


async def load_public_help_points_progressively(
    open_public_help_points_snapshot: OpenPublicHelpPointsSnapshot,
    list_public_help_points_page: ListPublicHelpPointsPage,
    on_progress: ProgressCallback,
    *,
    batch_size: int = PUBLIC_POINTS_BATCH_SIZE,
    operation_timeout_seconds: float = PUBLIC_POINTS_OPERATION_TIMEOUT_SECONDS,
) -> tuple[PublicHelpPoint, ...]:
    """Load a stable newest-first snapshot without blocking the NiceGUI event loop."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if operation_timeout_seconds <= 0:
        raise ValueError("operation_timeout_seconds must be positive")
    snapshot_created_at, total = await asyncio.wait_for(
        asyncio.to_thread(open_public_help_points_snapshot),
        timeout=operation_timeout_seconds,
    )
    loaded: list[PublicHelpPoint] = []
    before_created_at: datetime | None = None
    before_id: UUID | None = None
    on_progress((), 0, total, False)

    maximum_page_requests = max(1, (max(total, 0) + batch_size - 1) // batch_size + 1)
    for _page_number in range(maximum_page_requests):
        page = tuple(
            await asyncio.wait_for(
                asyncio.to_thread(
                    list_public_help_points_page,
                    snapshot_created_at=snapshot_created_at,
                    before_created_at=before_created_at,
                    before_id=before_id,
                    limit=batch_size,
                ),
                timeout=operation_timeout_seconds,
            )
        )
        if not page:
            on_progress((), len(loaded), max(total, len(loaded)), True)
            return tuple(loaded)

        loaded.extend(page)
        complete = len(page) < batch_size
        on_progress(page, len(loaded), max(total, len(loaded)), complete)
        if complete:
            return tuple(loaded)

        cursor = page[-1]
        before_created_at = cursor.created_at
        before_id = cursor.id
        await asyncio.sleep(0)
    raise RuntimeError("public help point pagination exceeded its snapshot bound")


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


def matches_search_query(
    point: PublicHelpPoint,
    category_names: Mapping[UUID, str],
    query: str,
) -> bool:
    """Return True if query is a substring of the point's name, description, or needs."""
    normalized = query.strip().casefold()
    if not normalized:
        return True
    haystacks = (
        point.name,
        point.description,
        *(category_names.get(need.category_id, "") for need in point.needs),
    )
    return any(normalized in haystack.casefold() for haystack in haystacks if haystack)


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
    *,
    list_active_categories: ListActiveCategories | None = None,
    open_public_help_points_snapshot: OpenPublicHelpPointsSnapshot | None = None,
    list_public_help_points_page: ListPublicHelpPointsPage | None = None,
    get_cached_public_home: GetCachedPublicHome | None = None,
    begin_public_home_refresh: BeginPublicHomeRefresh | None = None,
    finish_public_home_refresh: FinishPublicHomeRefresh | None = None,
    abort_public_home_refresh: AbortPublicHomeRefresh | None = None,
    wait_for_cached_public_home: WaitForCachedPublicHome | None = None,
) -> None:
    """Render active public points and the two location filters."""
    progressive_callbacks = (
        list_active_categories,
        open_public_help_points_snapshot,
        list_public_help_points_page,
    )
    if any(callback is not None for callback in progressive_callbacks) and not all(
        callback is not None for callback in progressive_callbacks
    ):
        raise ValueError("progressive loading requires category, count, and page callbacks")
    cache_callbacks = (
        get_cached_public_home,
        begin_public_home_refresh,
        finish_public_home_refresh,
        abort_public_home_refresh,
        wait_for_cached_public_home,
    )
    if any(callback is not None for callback in cache_callbacks) and not all(
        callback is not None for callback in cache_callbacks
    ):
        raise ValueError("public home cache requires all refresh callbacks")
    cached_home = get_cached_public_home() if get_cached_public_home else None
    if cached_home is not None:
        points = cached_home.points
        categories = cached_home.categories
    category_names = {category_id: name for name, category_id in categories.items()}
    active_points = filter_public_help_points(points)
    departments, _ = location_filter_options(list_departments, list_localities)
    cache_stale = bool(cached_home and cached_home.stale)
    should_load = open_public_help_points_snapshot is not None and (
        cached_home is None or cache_stale
    )
    loading = should_load and cached_home is None
    refreshing = should_load and cache_stale
    load_failed = False
    total_count: int | None = None
    refresh_token = (
        begin_public_home_refresh()
        if should_load and begin_public_home_refresh is not None
        else object()
        if should_load
        else None
    )
    owns_refresh = refresh_token is not None

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
        if loading or load_failed:
            return
        selected_category = category
        refresh()

    def render_category_chip(
        label: str, color: str, count: int, *, is_selected: bool, value: HelpPointCategory | str
    ) -> None:
        chip_classes = (
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm "
            "font-semibold transition-colors shrink-0 "
        )
        if loading or load_failed:
            chip_classes += "cursor-default opacity-60 "
        else:
            chip_classes += "cursor-pointer "
        if is_selected:
            chip_classes += f"text-white bg-[{color}]"
        else:
            chip_classes += (
                "bg-white border border-slate-200 text-slate-700 "
                f"hover:border-[{color}]"
            )
        chip = ui.row().classes(chip_classes)
        if loading or load_failed:
            chip.props("aria-disabled=true")
        else:
            chip.on("click", lambda: select_category(value))
        with chip:
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
            if loading or load_failed:
                with ui.row().classes(
                    "rounded-full px-3 py-1.5 text-sm font-semibold "
                    "bg-slate-100 text-slate-500 cursor-default"
                ).props("aria-disabled=true"):
                    ui.label(
                        "Cargando filtros…" if loading else "Filtros no disponibles"
                    )
                return
            location_filtered = filter_public_help_points(
                active_points,
                city=city.value or "",
                department=department.value or "",
            )
            location_filtered = tuple(
                point
                for point in location_filtered
                if matches_search_query(
                    point, category_names, search_input.value or ""
                )
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

    map_element = None
    results_grid = None
    result_count_label = None
    results_message = None

    def render_activity(points_to_describe: Sequence[PublicHelpPoint]) -> None:
        activity_indicator.clear()
        activity_text = latest_activity_text(points_to_describe)
        if activity_text:
            with activity_indicator:
                ui.icon("schedule").classes("text-slate-500 text-sm").props(
                    "aria-hidden=true"
                )
                ui.label(activity_text).classes("text-xs text-slate-500")

    def render_point_card(point: PublicHelpPoint) -> None:
        with ui.link(target=f"/puntos/{point.id}").classes(
            "w-full min-h-[160px] no-underline text-inherit bg-white "
            f"border-l-4 border-[{category_pin_color(point.category)}] "
            "rounded-2xl shadow-sm hover:shadow-md transition-shadow"
        ):
            with ui.column().classes("w-full gap-2 p-4"):
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    ui.label(point.category.value).classes(
                        category_badge_classes(point.category)
                    )
                    ui.icon("chevron_right").classes(
                        "text-emerald-700 shrink-0"
                    ).props("aria-hidden=true")
                with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
                    ui.icon("circle").classes(indicator_classes(point)).props(
                        "aria-hidden=true"
                    )
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
                    ).classes("shrink-0 text-xs text-slate-400 whitespace-nowrap")

    def append_map_points(points_to_append: Sequence[PublicHelpPoint]) -> None:
        if map_element is None:
            return
        for point in points_to_append:
            if not point.active:
                continue
            icon_html = pin_icon_html(category_pin_color(point.category))
            for location in point.locations:
                marker = map_element.marker(
                    latlng=(location.latitude, location.longitude)
                )
                marker.run_method(
                    "bindPopup",
                    build_popup_html(point, categories, location),
                    {"maxWidth": 240, "maxHeight": 180},
                )
                marker.run_method(
                    ":setIcon",
                    "L.divIcon({"
                    f"html: {json.dumps(icon_html)}, "
                    "className: '', iconSize: [26, 38], iconAnchor: [13, 38], "
                    "popupAnchor: [0, -34]})",
                )

    def append_result_cards(points_to_append: Sequence[PublicHelpPoint]) -> None:
        if results_grid is None:
            return
        with results_grid:
            for point in points_to_append:
                render_point_card(point)

    def refresh() -> None:
        nonlocal map_element, results_grid, result_count_label, results_message
        render_category_chips()
        filtered_points = filter_public_help_points(
            active_points,
            city=city.value or "",
            department=department.value or "",
            category=selected_category,
        )
        filtered_points = tuple(
            point
            for point in filtered_points
            if matches_search_query(point, category_names, search_input.value or "")
        )
        render_activity(filtered_points)
        map_container.clear()
        with map_container:
            map_element = render_help_point_map(filtered_points, categories)
        results.clear()
        with results:
            with ui.row().classes("w-full items-center justify-between gap-2"):
                ui.label("Puntos que necesitan ayuda").classes(
                    "text-xl font-bold text-slate-900"
                )
                if loading:
                    count_text = (
                        f"{len(filtered_points)} de {total_count} cargados"
                        if total_count is not None
                        else "Cargando puntos…"
                    )
                elif load_failed:
                    count_text = f"{len(filtered_points)} cargados parcialmente"
                else:
                    count_text = f"{len(filtered_points)} resultados"
                result_count_label = ui.label(count_text).classes(
                    "text-xs font-semibold text-white bg-[#003893] "
                    "rounded-full px-3 py-1 whitespace-nowrap"
                )
            results_message = ui.column().classes("w-full")
            with results_message:
                if loading and not active_points:
                    ui.label("Estamos cargando los puntos de ayuda…")
                elif not active_points:
                    ui.label("Todavía no hay puntos de ayuda activos.")
                elif not filtered_points:
                    ui.label(
                        "No encontramos puntos con estos filtros. "
                        "Prueba con otro departamento, ciudad / municipio o categoría."
                    )
            results_grid = ui.grid().classes(
                "w-full grid-cols-1 sm:grid-cols-2 gap-3"
            )
            with results_grid:
                for point in filtered_points:
                    render_point_card(point)

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
                "w-full gap-1 rounded-2xl bg-white p-4 border-l-4 border-amber-500 "
                "shadow-sm"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("gpp_maybe").classes("text-amber-600").props(
                        "aria-hidden=true"
                    )
                    ui.label("Antes de ayudar").classes(
                        "text-sm font-semibold text-slate-900"
                    )
                ui.label(
                    "Verifica que la iniciativa siga activa y confirma la "
                    "identidad de la persona coordinadora antes de compartir "
                    "dinero, datos personales o comprometerte a ayudar."
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
                search_input = ui.input(
                    "Buscar por nombre, lugar o necesidad",
                    on_change=refresh,
                ).classes("w-full").props("filled rounded clearable prepend-icon=search")
                category_chips = ui.row().classes(
                    "w-full flex-nowrap sm:flex-wrap gap-2 overflow-x-auto "
                    "sm:overflow-visible pb-1"
                )
                ui.label(
                    "Busca por el departamento o ciudad hacia donde se "
                    "dirige la ayuda."
                ).classes("text-xs text-slate-500")
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
            loading_message = (
                "Cargando puntos…"
                if loading
                else "Mostrando datos guardados mientras actualizamos…"
                if refreshing
                else ""
            )
            loading_status = ui.label(loading_message).classes(
                "text-sm text-slate-600 text-center"
            )
            refresh()

    if should_load:
        if loading:
            search_input.disable()
            department.disable()
        refreshed_points: list[PublicHelpPoint] = []

        def update_progress(
            page: tuple[PublicHelpPoint, ...],
            loaded_count: int,
            total: int,
            complete: bool,
        ) -> None:
            nonlocal active_points, loading, refreshing, total_count
            filtered_page = filter_public_help_points(page)
            total_count = total
            if refreshing:
                refreshed_points.extend(filtered_page)
                if complete:
                    active_points = tuple(refreshed_points)
                    refreshing = False
                    loading_status.set_text("")
                    refresh()
                return

            if filtered_page:
                if results_message is not None:
                    results_message.clear()
                active_points = (*active_points, *filtered_page)
                append_map_points(filtered_page)
                append_result_cards(filtered_page)
                render_activity(active_points)
            loading = not complete
            if result_count_label is not None:
                result_count_label.set_text(
                    f"{len(active_points)} resultados"
                    if complete
                    else f"{len(active_points)} de {total_count} cargados"
                )
            if complete:
                loading_status.set_text("")
                search_input.enable()
                department.enable()
                render_category_chips()
            else:
                loading_status.set_text(
                    f"Cargando puntos… {loaded_count} de {total_count}"
                )

        async def load_points() -> None:
            nonlocal active_points, categories, category_names, loading, refreshing, load_failed
            assert list_active_categories is not None
            assert open_public_help_points_snapshot is not None
            assert list_public_help_points_page is not None
            try:
                if not owns_refresh:
                    logger.info(
                        "public home refresh already in progress; loading this view directly"
                    )
                categories = await asyncio.wait_for(
                    asyncio.to_thread(list_active_categories),
                    timeout=PUBLIC_POINTS_OPERATION_TIMEOUT_SECONDS,
                )
                category_names = {
                    category_id: name for name, category_id in categories.items()
                }
                loaded_points = await load_public_help_points_progressively(
                    open_public_help_points_snapshot,
                    list_public_help_points_page,
                    update_progress,
                )
                if owns_refresh and finish_public_home_refresh is not None:
                    assert refresh_token is not None
                    finish_public_home_refresh(refresh_token, loaded_points, categories)
            except Exception:
                logger.exception("progressive public help point loading failed")
                loading = False
                if refreshing:
                    refreshing = False
                    loading_status.set_text(
                        "Mostrando datos guardados. No pudimos actualizarlos ahora."
                    )
                else:
                    load_failed = True
                    loading_status.set_text(
                        "No pudimos terminar de cargar todos los puntos. "
                        "Recarga la página."
                    )
                    render_category_chips()
                    if result_count_label is not None:
                        result_count_label.set_text(
                            f"{len(active_points)} cargados parcialmente"
                        )
            finally:
                if (
                    owns_refresh
                    and refresh_token is not None
                    and abort_public_home_refresh is not None
                ):
                    abort_public_home_refresh(refresh_token)

        ui.timer(0, load_points, once=True)
