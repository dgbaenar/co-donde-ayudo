from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch
from uuid import UUID, uuid4

from backend.domain.models import (
    AffectedArea,
    HelpPointCategory,
    HelpPointLocation,
    Need,
    NeedStatus,
    PublicHelpPoint,
)
from frontend.components.help_point_map import category_pin_color, status_line
from frontend.pages import home
from frontend.pages.home import (
    affected_area_text,
    category_badge_classes,
    filter_public_help_points,
    latest_activity_text,
    location_filter_options,
    load_public_help_points_progressively,
    matches_search_query,
)


DEPARTMENTS = (
    "Amazonas",
    "Antioquia",
    "Arauca",
    "Atlántico",
    "Bogotá, D.C.",
    "Bolívar",
    "Boyacá",
    "Caldas",
    "Caquetá",
    "Casanare",
    "Cauca",
    "Cesar",
    "Chocó",
    "Córdoba",
    "Cundinamarca",
    "Guainía",
    "Guaviare",
    "Huila",
    "La Guajira",
    "Magdalena",
    "Meta",
    "Nariño",
    "Norte de Santander",
    "Putumayo",
    "Quindío",
    "Risaralda",
    "San Andrés, Providencia y Santa Catalina",
    "Santander",
    "Sucre",
    "Tolima",
    "Valle del Cauca",
    "Vaupés",
    "Vichada",
)

AFFECTED_DEPARTMENTS = (
    "Caldas",
    "Chocó",
    "Quindío",
    "Risaralda",
    "Valle del Cauca",
)


def list_localities(department: str) -> tuple[str, ...]:
    return {
        "Antioquia": ("Medellín",),
        "Chocó": ("Quibdó",),
        "Quindío": ("Armenia",),
        "Valle del Cauca": ("Cali", "Palmira", "Roldanillo"),
    }.get(department, ())


def click_category_chip(fake_ui, label_text: str) -> None:
    """Simulate clicking a category chip by its visible label text."""
    chip_label = next(
        element
        for element in fake_ui.elements
        if element.kind == "label" and element.args == (label_text,)
    )
    chip_row = next(
        element
        for element in fake_ui.elements
        if element.kind == "row" and chip_label in element.children
    )
    chip_row.handlers["click"]()


class RecordingElement:
    def __init__(self, owner, kind, *args, **kwargs):
        self.owner = owner
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.children = []
        self.value = kwargs.get("value")
        self.options = kwargs.get("options", args[0] if args else None)
        self.on_change = kwargs.get("on_change")
        self.update_calls = 0
        self.clear_calls = 0
        self.classes_value = ""
        self.props_value = ""
        self.enabled = True
        self.enable_calls = 0
        self.disable_calls = 0
        self.handlers = {}

    def __enter__(self): self.owner.stack.append(self); return self
    def __exit__(self, *_args): self.owner.stack.pop(); return False
    def classes(self, value): self.classes_value = value; return self
    def props(self, value):
        self.props_value = value
        if "disable" in value.split():
            self.enabled = False
        return self
    def on(self, event_name, handler, *_args, **_kwargs):
        self.handlers[event_name] = handler
        return self
    def enable(self): self.enable_calls += 1; self.enabled = True
    def disable(self): self.disable_calls += 1; self.enabled = False
    def clear(self):
        self.clear_calls += 1
        def remove_descendants(element):
            for child in tuple(element.children):
                remove_descendants(child)
                if child in self.owner.elements:
                    self.owner.elements.remove(child)
            element.children.clear()

        remove_descendants(self)
    def update(self): self.update_calls += 1
    def set_text(self, value): self.args = (value,); return self


class RecordingUi:
    def __init__(self): self.elements = []; self.stack = []
    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(self, kind, *args, **kwargs)
        self.elements.append(element)
        if self.stack:
            self.stack[-1].children.append(element)
        return element
    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def row(self, *args, **kwargs): return self._record("row", *args, **kwargs)
    def grid(self, *args, **kwargs): return self._record("grid", *args, **kwargs)
    def element(self, *args, **kwargs): return self._record("element", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def select(self, *args, **kwargs): return self._record("select", *args, **kwargs)
    def input(self, *args, **kwargs): return self._record("input", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def link(self, *args, **kwargs): return self._record("link", *args, **kwargs)
    def icon(self, *args, **kwargs): return self._record("icon", *args, **kwargs)
    def timer(self, *args, **kwargs): return self._record("timer", *args, **kwargs)


class ProgressiveHomeLoadingTests(unittest.TestCase):
    @staticmethod
    def point(created_at: datetime, suffix: int) -> PublicHelpPoint:
        return PublicHelpPoint(
            id=UUID(f"00000000-0000-0000-0000-{suffix:012d}"),
            name=f"Punto {suffix}",
            description="Apoyo",
            affected_areas=(AffectedArea(department="Chocó", city="Quibdó"),),
            locations=(
                HelpPointLocation(
                    id=UUID(f"10000000-0000-0000-0000-{suffix:012d}"),
                    address="Calle 5",
                    city="Quibdó",
                    department="Chocó",
                    latitude=5.69 + suffix / 10_000,
                    longitude=-76.66,
                ),
            ),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=True,
            needs=(),
            category=HelpPointCategory.RESCUE_OPERATIONS,
            created_at=created_at,
            updated_at=created_at,
        )

    def test_loads_every_page_automatically_with_stable_cursor(self) -> None:
        newest = self.point(datetime(2026, 8, 13, 12, tzinfo=UTC), 3)
        middle = self.point(datetime(2026, 8, 13, 11, tzinfo=UTC), 2)
        oldest = self.point(datetime(2026, 8, 13, 10, tzinfo=UTC), 1)
        calls = []
        pages = ((newest, middle), (oldest,))

        def list_page(*, snapshot_created_at, before_created_at, before_id, limit):
            calls.append((snapshot_created_at, before_created_at, before_id, limit))
            return pages[len(calls) - 1]

        progress = []
        result = asyncio.run(
            load_public_help_points_progressively(
                lambda: (datetime(2026, 8, 13, 13, tzinfo=UTC), 3),
                list_page,
                lambda page, loaded_count, total, complete: progress.append(
                    (
                        tuple(point.id for point in page),
                        loaded_count,
                        total,
                        complete,
                    )
                ),
                batch_size=2,
            )
        )

        self.assertEqual(result, (newest, middle, oldest))
        snapshot = calls[0][0]
        self.assertEqual(calls, [
            (snapshot, None, None, 2),
            (snapshot, middle.created_at, middle.id, 2),
        ])
        self.assertEqual(progress[-1], ((oldest.id,), 3, 3, True))
        self.assertTrue(
            all(not complete for _page, _loaded, _total, complete in progress[:-1])
        )

    def test_times_out_a_database_operation_instead_of_loading_forever(self) -> None:
        release = asyncio.Event()

        async def never_finishes(*_args, **_kwargs):
            await release.wait()

        with patch.object(home.asyncio, "to_thread", side_effect=never_finishes):
            with self.assertRaises(TimeoutError):
                asyncio.run(
                    load_public_help_points_progressively(
                        lambda: (datetime(2026, 8, 13, 13, tzinfo=UTC), 1),
                        lambda **_kwargs: (),
                        lambda *_args: None,
                        operation_timeout_seconds=0.001,
                    )
                )

    def test_each_page_is_appended_without_rebuilding_existing_results_or_map(self) -> None:
        class RecordingMarker:
            def __init__(self):
                self.method_calls = []

            def run_method(self, *args):
                self.method_calls.append(args)

        class RecordingMap:
            def __init__(self):
                self.markers = []

            def marker(self, *, latlng):
                marker = RecordingMarker()
                marker.latlng = latlng
                self.markers.append(marker)
                return marker

        fake_ui = RecordingUi()
        map_element = RecordingMap()
        created_at = datetime(2026, 8, 13, 12, tzinfo=UTC)
        points = tuple(self.point(created_at, suffix) for suffix in range(1, 26))
        pages = (points[:24], points[24:])
        page_calls = []
        intermediate_visible_counts = []
        stored = []

        def list_page(**kwargs):
            page_calls.append(kwargs)
            if len(page_calls) == 2:
                intermediate_visible_counts.append(
                    (
                        sum(
                            element.kind == "link"
                            and str(element.kwargs.get("target", "")).startswith(
                                "/puntos/"
                            )
                            for element in fake_ui.elements
                        ),
                        len(map_element.markers),
                    )
                )
            return pages[len(page_calls) - 1]

        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(
                home,
                "render_help_point_map",
                return_value=map_element,
            ) as render_map:
                home.render_home(
                    (),
                    {},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                    list_active_categories=lambda: {},
                    open_public_help_points_snapshot=lambda: (created_at, 25),
                    list_public_help_points_page=list_page,
                    get_cached_public_home=lambda: None,
                    begin_public_home_refresh=lambda: "token",
                    finish_public_home_refresh=lambda token, loaded, loaded_categories: stored.append(
                        (tuple(loaded), loaded_categories)
                    ) is None,
                    abort_public_home_refresh=lambda _token: None,
                    wait_for_cached_public_home=lambda **_kwargs: None,
                )
                results = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column" and element.classes_value == "w-full gap-3"
                )
                timer = next(
                    element for element in fake_ui.elements if element.kind == "timer"
                )

                asyncio.run(timer.args[1]())

                point_links = [
                    element
                    for element in fake_ui.elements
                    if element.kind == "link"
                    and str(element.kwargs.get("target", "")).startswith("/puntos/")
                ]
                self.assertEqual(len(page_calls), 2)
                self.assertEqual(intermediate_visible_counts, [(24, 24)])
                self.assertEqual(len(point_links), 25)
                self.assertEqual(len(map_element.markers), 25)
                self.assertEqual(render_map.call_count, 1)
                self.assertEqual(results.clear_calls, 1)
                self.assertFalse(
                    any(
                        element.kind == "label"
                        and element.args
                        == ("Estamos cargando los puntos de ayuda…",)
                        for element in fake_ui.elements
                    )
                )
                self.assertFalse(
                    any(
                        element.kind == "button"
                        and element.args == ("Mostrar más puntos",)
                        for element in fake_ui.elements
                    )
                )
                search = next(
                    element for element in fake_ui.elements if element.kind == "input"
                )
                department = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs["label"] == "Departamento"
                )
                self.assertTrue(search.enabled)
                self.assertTrue(department.enabled)
                self.assertEqual(stored, [(points, {})])
        finally:
            home.ui = original_ui

    def test_progressive_render_schedules_loading_after_initial_page_render(self) -> None:
        fake_ui = RecordingUi()
        page_calls = []
        category_calls = []
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (),
                    {},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                    list_active_categories=lambda: category_calls.append(True) or {"Agua": uuid4()},
                    open_public_help_points_snapshot=lambda: (
                        datetime(2026, 8, 13, 13, tzinfo=UTC),
                        0,
                    ),
                    list_public_help_points_page=lambda **kwargs: page_calls.append(
                        kwargs
                    )
                    or (),
                )
                timers = [
                    element for element in fake_ui.elements if element.kind == "timer"
                ]
                self.assertEqual(len(timers), 1)
                self.assertEqual(category_calls, [])
                self.assertEqual(timers[0].args[0], 0)
                self.assertTrue(timers[0].kwargs["once"])
                labels = [
                    element.args[0]
                    for element in fake_ui.elements
                    if element.kind == "label"
                ]
                self.assertIn("Cargando puntos…", labels)
                search = next(
                    element for element in fake_ui.elements if element.kind == "input"
                )
                department = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs["label"] == "Departamento"
                )
                self.assertFalse(search.enabled)
                self.assertFalse(department.enabled)
                self.assertFalse(
                    any(
                        element.kind == "row"
                        and "cursor-pointer" in element.classes_value
                        for element in fake_ui.elements
                    )
                )
                self.assertFalse(
                    any(
                        element.kind == "label"
                        and element.args == ("Todavía no hay puntos de ayuda activos.",)
                        for element in fake_ui.elements
                    )
                )
                self.assertFalse(
                    any(
                        element.kind == "button"
                        and element.args == ("Mostrar más puntos",)
                        for element in fake_ui.elements
                    )
                )

                asyncio.run(timers[0].args[1]())

                self.assertEqual(category_calls, [True])
                self.assertEqual(
                    page_calls,
                    [
                        {
                            "snapshot_created_at": ANY,
                            "before_created_at": None,
                            "before_id": None,
                            "limit": 24,
                        }
                    ],
                )
                self.assertTrue(search.enabled)
                self.assertTrue(department.enabled)
        finally:
            home.ui = original_ui

    def test_fresh_cached_home_renders_immediately_without_database_loading(self) -> None:
        fake_ui = RecordingUi()
        point = self.point(datetime(2026, 8, 13, 12, tzinfo=UTC), 1)
        database_calls = []
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map") as render_map:
                home.render_home(
                    (),
                    {},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                    list_active_categories=lambda: database_calls.append("categories") or {},
                    open_public_help_points_snapshot=lambda: database_calls.append("snapshot")
                    or (datetime(2026, 8, 13, 13, tzinfo=UTC), 1),
                    list_public_help_points_page=lambda **_kwargs: database_calls.append("page")
                    or (point,),
                    get_cached_public_home=lambda: SimpleNamespace(
                        points=(point,), categories={}, stale=False
                    ),
                    begin_public_home_refresh=lambda: "token",
                    finish_public_home_refresh=lambda *_args: True,
                    abort_public_home_refresh=lambda _token: None,
                    wait_for_cached_public_home=lambda **_kwargs: None,
                )

                self.assertEqual(database_calls, [])
                self.assertFalse(
                    any(element.kind == "timer" for element in fake_ui.elements)
                )
                self.assertEqual(render_map.call_args.args[0], (point,))
                self.assertTrue(
                    any(
                        element.kind == "link"
                        and element.kwargs.get("target") == f"/puntos/{point.id}"
                        for element in fake_ui.elements
                    )
                )
        finally:
            home.ui = original_ui

    def test_stale_cached_home_stays_interactive_while_refreshing_in_background(self) -> None:
        fake_ui = RecordingUi()
        stale_point = self.point(datetime(2026, 8, 13, 11, tzinfo=UTC), 1)
        fresh_point = self.point(datetime(2026, 8, 13, 12, tzinfo=UTC), 2)
        stored = []
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (),
                    {},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                    list_active_categories=lambda: {},
                    open_public_help_points_snapshot=lambda: (
                        datetime(2026, 8, 13, 13, tzinfo=UTC),
                        1,
                    ),
                    list_public_help_points_page=lambda **_kwargs: (fresh_point,),
                    get_cached_public_home=lambda: SimpleNamespace(
                        points=(stale_point,), categories={}, stale=True
                    ),
                    begin_public_home_refresh=lambda: "token",
                    finish_public_home_refresh=lambda _token, points, categories: stored.append(
                        (tuple(points), categories)
                    ) is None,
                    abort_public_home_refresh=lambda _token: None,
                    wait_for_cached_public_home=lambda **_kwargs: None,
                )
                search = next(
                    element for element in fake_ui.elements if element.kind == "input"
                )
                department = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs["label"] == "Departamento"
                )
                self.assertTrue(search.enabled)
                self.assertTrue(department.enabled)
                self.assertTrue(
                    any(
                        element.kind == "link"
                        and element.kwargs.get("target") == f"/puntos/{stale_point.id}"
                        for element in fake_ui.elements
                    )
                )
                timer = next(
                    element for element in fake_ui.elements if element.kind == "timer"
                )

                asyncio.run(timer.args[1]())

                self.assertEqual(stored, [((fresh_point,), {})])
                self.assertTrue(search.enabled)
                self.assertTrue(department.enabled)
        finally:
            home.ui = original_ui


class PublicHelpPointFilteringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.water_id = uuid4()
        self.blanket_id = uuid4()
        self.categories = {"Agua": self.water_id, "Cobijas": self.blanket_id}
        self.cali_water = self.point(
            name="Parque Central",
            city="Cali",
            department="Valle del Cauca",
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            active=True,
            category_id=self.water_id,
        )
        self.medellin_blanket = self.point(
            name="Albergue Norte",
            city="Medellín",
            department="Antioquia",
            affected_areas=(AffectedArea(department="Quindío", city="Armenia"),),
            active=True,
            category_id=self.blanket_id,
        )
        self.inactive = self.point(
            name="Punto cerrado",
            city="Cali",
            department="Valle del Cauca",
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Palmira"),
            ),
            active=False,
            category_id=self.water_id,
        )
        self.multi_area = self.point(
            name="Punto multizona",
            city="Cali",
            department="Valle del Cauca",
            affected_areas=(
                AffectedArea(department="Chocó", city="Quibdó"),
                AffectedArea(department="Caldas", city=None),
            ),
            active=True,
            category_id=self.water_id,
        )
        self.points = (
            self.cali_water,
            self.medellin_blanket,
            self.inactive,
            self.multi_area,
        )

    @staticmethod
    def point(
        *,
        name: str,
        city: str,
        department: str,
        affected_areas: tuple[AffectedArea, ...],
        active: bool,
        category_id,
        category: HelpPointCategory = HelpPointCategory.RESCUE_OPERATIONS,
    ) -> PublicHelpPoint:
        return PublicHelpPoint(category=category,
            id=uuid4(),
            name=name,
            description="Se requiere apoyo.",
            locations=(
                HelpPointLocation(
                    id=uuid4(),
                    address="Calle 5 # 10-20",
                    city=city,
                    department=department,
                    latitude=3.0,
                    longitude=-76.0,
                ),
            ),
            affected_areas=affected_areas,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=active,
            needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
        )

    def test_without_filters_lists_only_active_points(self) -> None:
        filtered = filter_public_help_points(self.points)

        self.assertEqual(
            filtered, (self.cali_water, self.medellin_blanket, self.multi_area)
        )

    def test_department_filter_matches_point_via_any_of_its_areas(self) -> None:
        self.assertEqual(
            filter_public_help_points(self.points, department="Chocó"),
            (self.multi_area,),
        )
        self.assertEqual(
            filter_public_help_points(self.points, department="Caldas"),
            (self.multi_area,),
        )

    def test_city_filter_matches_point_via_any_of_its_areas(self) -> None:
        self.assertEqual(
            filter_public_help_points(self.points, city="Quibdó"),
            (self.multi_area,),
        )

    def test_category_filter_matches_only_points_of_that_category(self) -> None:
        donation_point = self.point(
            name="Punto de donaciones",
            city="Cali",
            department="Valle del Cauca",
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            active=True,
            category_id=self.water_id,
            category=HelpPointCategory.DONATION_COLLECTION,
        )
        points = (*self.points, donation_point)

        self.assertEqual(
            filter_public_help_points(
                points, category=HelpPointCategory.DONATION_COLLECTION
            ),
            (donation_point,),
        )
        self.assertEqual(
            filter_public_help_points(
                points, category=HelpPointCategory.RESCUE_OPERATIONS
            ),
            (self.cali_water, self.medellin_blanket, self.multi_area),
        )

    def test_filters_destination_while_map_coordinates_stay_physical(self) -> None:
        self.assertEqual(
            filter_public_help_points(self.points, city="Roldanillo"),
            (self.cali_water,),
        )
        self.assertEqual(
            (self.cali_water.locations[0].latitude, self.cali_water.locations[0].longitude),
            (3.0, -76.0),
        )

    def test_location_filter_options_come_from_injected_catalog(self) -> None:
        self.assertEqual(
            location_filter_options(lambda: AFFECTED_DEPARTMENTS, list_localities),
            (AFFECTED_DEPARTMENTS, ()),
        )
        self.assertEqual(
            location_filter_options(
                lambda: AFFECTED_DEPARTMENTS,
                list_localities,
                department="Valle del Cauca",
            )[1],
            ("Cali", "Palmira", "Roldanillo"),
        )
        self.assertEqual(
            filter_public_help_points(self.points, department="Quindío"),
            (self.medellin_blanket,),
        )
        self.assertEqual(
            filter_public_help_points(
                self.points,
                city="Roldanillo",
                department="Valle del Cauca",
            ),
            (self.cali_water,),
        )

    def test_empty_search_query_matches_every_point(self) -> None:
        category_names = {value: key for key, value in self.categories.items()}
        self.assertTrue(matches_search_query(self.cali_water, category_names, ""))
        self.assertTrue(matches_search_query(self.cali_water, category_names, "   "))

    def test_search_query_matches_name_case_insensitively(self) -> None:
        category_names = {value: key for key, value in self.categories.items()}
        self.assertTrue(matches_search_query(self.cali_water, category_names, "parque"))
        self.assertTrue(
            matches_search_query(self.cali_water, category_names, "PARQUE CENTRAL")
        )
        self.assertFalse(
            matches_search_query(self.medellin_blanket, category_names, "parque")
        )

    def test_search_query_matches_description(self) -> None:
        category_names = {value: key for key, value in self.categories.items()}
        self.assertTrue(matches_search_query(self.cali_water, category_names, "apoyo"))

    def test_search_query_matches_need_category_name(self) -> None:
        category_names = {value: key for key, value in self.categories.items()}
        self.assertTrue(matches_search_query(self.cali_water, category_names, "agua"))
        self.assertFalse(
            matches_search_query(self.medellin_blanket, category_names, "agua")
        )
        self.assertTrue(
            matches_search_query(self.medellin_blanket, category_names, "cobijas")
        )

    def test_search_query_with_no_match_returns_false(self) -> None:
        category_names = {value: key for key, value in self.categories.items()}
        self.assertFalse(
            matches_search_query(self.cali_water, category_names, "xyz-no-existe")
        )


class AffectedAreaTextTests(unittest.TestCase):
    @staticmethod
    def point(*, affected_areas: tuple[AffectedArea, ...]) -> PublicHelpPoint:
        return PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(),
            name="Parque Central",
            description="Se requiere apoyo.",
            locations=(
                HelpPointLocation(
                    id=uuid4(),
                    address="Calle 5 # 10-20",
                    city="Cali",
                    department="Valle del Cauca",
                    latitude=3.0,
                    longitude=-76.0,
                ),
            ),
            affected_areas=affected_areas,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=True,
            needs=(),
        )

    def test_uses_city_and_department_when_city_is_set(self) -> None:
        self.assertEqual(
            affected_area_text(
                self.point(
                    affected_areas=(
                        AffectedArea(department="Valle del Cauca", city="Roldanillo"),
                    )
                )
            ),
            "Roldanillo, Valle del Cauca",
        )

    def test_falls_back_to_whole_department_when_city_is_none(self) -> None:
        self.assertEqual(
            affected_area_text(
                self.point(
                    affected_areas=(
                        AffectedArea(department="Valle del Cauca", city=None),
                    )
                )
            ),
            "Todo el departamento de Valle del Cauca",
        )

    def test_lists_multiple_departments_and_groups_cities_within_one(self) -> None:
        text = affected_area_text(
            self.point(
                affected_areas=(
                    AffectedArea(department="Chocó", city="Quibdó"),
                    AffectedArea(department="Chocó", city="Istmina"),
                    AffectedArea(department="Caldas", city=None),
                )
            )
        )

        self.assertEqual(
            text, "Quibdó, Istmina, Chocó; Todo el departamento de Caldas"
        )


class LatestActivityTextTests(unittest.TestCase):
    @staticmethod
    def point(*, updated_at: datetime) -> PublicHelpPoint:
        return PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(),
            name="Parque Central",
            description="Se requiere apoyo.",
            locations=(
                HelpPointLocation(
                    id=uuid4(),
                    address="Calle 5 # 10-20",
                    city="Cali",
                    department="Valle del Cauca",
                    latitude=3.0,
                    longitude=-76.0,
                ),
            ),
            affected_areas=(),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=True,
            needs=(),
            updated_at=updated_at,
        )

    def test_returns_none_for_no_points(self) -> None:
        self.assertIsNone(latest_activity_text(()))

    def test_uses_the_most_recently_updated_point_among_several(self) -> None:
        older = self.point(updated_at=datetime(2020, 1, 1, 10, 30, tzinfo=UTC))
        newer = self.point(updated_at=datetime(2020, 6, 1, 8, 0, tzinfo=UTC))

        self.assertEqual(
            latest_activity_text((older, newer)),
            "Última actividad: el 1 jun 2020, 08:00",
        )

    def test_uses_relative_time_when_recent(self) -> None:
        recent = self.point(updated_at=datetime.now(UTC))

        self.assertEqual(
            latest_activity_text((recent,)), "Última actividad: hace menos de un minuto"
        )


class NeedsPreviewTextTests(unittest.TestCase):
    @staticmethod
    def need(status: NeedStatus) -> Need:
        return Need(id=uuid4(), category_id=uuid4(), status=status)

    def test_returns_none_for_no_needs(self) -> None:
        self.assertIsNone(home.needs_preview_text((), {}))

    def test_shows_the_most_urgent_names_first_up_to_the_limit(self) -> None:
        covered = self.need(NeedStatus.COVERED)
        on_the_way = self.need(NeedStatus.HELP_ON_THE_WAY)
        needs_help = self.need(NeedStatus.NEEDS_HELP)
        category_names = {
            covered.category_id: "Cobijas",
            on_the_way.category_id: "Comida",
            needs_help.category_id: "Agua",
        }

        self.assertEqual(
            home.needs_preview_text((covered, on_the_way, needs_help), category_names),
            "Necesita: Agua, Comida +1 más",
        )

    def test_omits_remainder_suffix_when_within_the_limit(self) -> None:
        needs_help = self.need(NeedStatus.NEEDS_HELP)
        category_names = {needs_help.category_id: "Agua"}

        self.assertEqual(
            home.needs_preview_text((needs_help,), category_names),
            "Necesita: Agua",
        )

    def test_falls_back_to_generic_name_for_unknown_category(self) -> None:
        needs_help = self.need(NeedStatus.NEEDS_HELP)

        self.assertEqual(
            home.needs_preview_text((needs_help,), {}),
            "Necesita: Necesidad",
        )


class NeedStatusTextTests(unittest.TestCase):
    def test_uses_the_exact_public_text_for_each_need_status(self) -> None:
        self.assertEqual(status_line(NeedStatus.NEEDS_HELP, "Agua"), "🔴 Agua")
        self.assertEqual(
            status_line(NeedStatus.HELP_ON_THE_WAY, "Agua"), "🟡 Agua"
        )
        self.assertEqual(
            status_line(NeedStatus.COVERED, "Agua"), "🟢 Agua — no enviar más"
        )


class HomeBrandingTests(unittest.TestCase):
    def test_uses_one_exact_public_title_without_duplicate_brand_label(self) -> None:
        source = (
            Path(__file__).resolve().parents[2] / "src/frontend/pages/home.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(source.count('ui.label("¿Dónde ayudo?")'), 1)
        self.assertNotIn('ui.label("Dónde Ayudo")', source)
        self.assertNotIn("Ayuda Colombia", source)


class HomeResponsivePresentationTests(unittest.TestCase):
    def test_renders_polished_defaults_count_cta_and_no_apply_button(self) -> None:
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        rendered_map_points = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: rendered_map_points.append(tuple(points)),
                create=True,
            ):
                home.render_home((), {}, lambda: AFFECTED_DEPARTMENTS, list_localities)
        finally:
            home.ui = original_ui

        self.assertTrue(any(element.kind == "link" and element.args == ("Crear iniciativa", "/crear") for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "link" and element.args == ("Encontrar cómo ayudar", "#resultados") for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "label" and element.args == ("Todavía no hay puntos de ayuda activos.",) for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "label" and element.args == ("Filtros",) for element in fake_ui.elements))
        visible_labels = [
            element.args[0]
            for element in fake_ui.elements
            if element.kind == "label" and element.args
        ]
        with self.subTest("single public title"):
            self.assertEqual(visible_labels.count("¿Dónde ayudo?"), 1)
            self.assertNotIn("Dónde Ayudo", visible_labels)
            self.assertNotIn("¿Dónde necesitan ayuda?", visible_labels)
        emergency_explanation = (
            "Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, "
            "Valle del Cauca, Risaralda y Quindío."
        )
        with self.subTest("earthquake context"):
            self.assertIn("Emergencia activa", visible_labels)
            self.assertIn("Respuesta al terremoto de Chocó", visible_labels)
            self.assertIn("Terremoto del 10 de agosto de 2026", visible_labels)
            self.assertIn(emergency_explanation, visible_labels)
        safety_warning = (
            "Verifica que la iniciativa siga activa y confirma la identidad "
            "de la persona coordinadora antes de compartir dinero, datos "
            "personales o comprometerte a ayudar."
        )
        with self.subTest("safety warning before trusting an initiative"):
            self.assertIn("Antes de ayudar", visible_labels)
            self.assertIn(safety_warning, visible_labels)

            def contains(parent, target):
                return any(
                    child is target or contains(child, target)
                    for child in parent.children
                )

            warning_label = next(
                e
                for e in fake_ui.elements
                if e.kind == "label" and e.args == ("Antes de ayudar",)
            )
            warning_card = next(
                element
                for element in fake_ui.elements
                if element.kind == "column"
                and "bg-white" in element.classes_value
                and contains(element, warning_label)
            )
            self.assertIn("border-l-4", warning_card.classes_value)
            self.assertIn("border-amber-500", warning_card.classes_value)
        self.assertTrue(any(element.kind == "label" and element.args == ("Explora el mapa o revisa la lista de puntos activos y ayudemos juntos a Colombia.",) for element in fake_ui.elements))
        with self.subTest("results heading with count badge, not a plain dashed string"):
            self.assertTrue(any(element.kind == "label" and element.args == ("Puntos que necesitan ayuda",) for element in fake_ui.elements))
            self.assertTrue(any(element.kind == "label" and element.args == ("0 resultados",) for element in fake_ui.elements))
            self.assertFalse(any(element.kind == "label" and element.args and "—" in element.args[0] for element in fake_ui.elements))
        self.assertEqual(rendered_map_points, [()])
        selects = [element for element in fake_ui.elements if element.kind == "select"]
        self.assertEqual(
            {element.kwargs["label"] for element in selects},
            {"Ciudad / Municipio", "Departamento"},
        )
        with self.subTest("category filter is a chip row, not a select"):
            category_chip_labels = {
                element.args[0]
                for element in fake_ui.elements
                if element.kind == "label" and element.args and element.args[0] == "Todas las categorías"
            }
            self.assertEqual(category_chip_labels, {"Todas las categorías"})
            for category in HelpPointCategory:
                self.assertTrue(
                    any(
                        element.kind == "label" and element.args == (category.value,)
                        for element in fake_ui.elements
                    )
                )
        with self.subTest("chips scroll horizontally on mobile, wrap on larger screens"):
            todas_label = next(
                element
                for element in fake_ui.elements
                if element.kind == "label" and element.args == ("Todas las categorías",)
            )
            todas_chip_row = next(
                element
                for element in fake_ui.elements
                if element.kind == "row" and todas_label in element.children
            )
            chips_container = next(
                element
                for element in fake_ui.elements
                if element.kind == "row" and todas_chip_row in element.children
            )
            self.assertIn("flex-nowrap", chips_container.classes_value)
            self.assertIn("overflow-x-auto", chips_container.classes_value)
            self.assertIn("sm:flex-wrap", chips_container.classes_value)
            self.assertIn("sm:overflow-visible", chips_container.classes_value)
            self.assertIn("shrink-0", todas_chip_row.classes_value)
        department = next(element for element in selects if element.kwargs["label"] == "Departamento")
        city = next(element for element in selects if element.kwargs["label"] == "Ciudad / Municipio")
        self.assertEqual(tuple(department.options)[1:], AFFECTED_DEPARTMENTS)
        self.assertEqual(
            city.options,
            {"": "Selecciona primero un departamento"},
        )
        self.assertEqual(department.value, "")
        self.assertEqual(city.value, "")
        self.assertFalse(city.enabled)
        self.assertNotIn("disable", city.props_value.split())
        self.assertEqual(city.disable_calls, 1)
        self.assertTrue(all("w-full" in element.classes_value for element in selects))
        with self.subTest("filled rounded selectors"):
            self.assertTrue(all("filled" in element.props_value for element in selects))
            self.assertTrue(all("rounded" in element.props_value for element in selects))
        self.assertFalse(any("dense" in element.props_value for element in selects))
        for select in selects:
            with self.subTest(select=select.kwargs["label"]):
                self.assertIn("behavior=menu", select.props_value)
                self.assertIn("transition-show=none", select.props_value)
                self.assertIn("transition-hide=none", select.props_value)
                self.assertIn(
                    'popup-content-style="max-height: 40vh !important; overflow-y: auto"',
                    select.props_value,
                )
                self.assertIn(
                    "popup-content-class=bounded-select-menu",
                    select.props_value,
                )
                self.assertNotIn("options-dense", select.props_value)
        self.assertFalse(any(element.kind == "button" and element.args == ("Aplicar filtros",) for element in fake_ui.elements))
        grid = next(element for element in fake_ui.elements if element.kind == "grid")
        self.assertNotIn("columns", grid.kwargs)
        with self.subTest("map is a fixed-width column, list gets the remaining space"):
            self.assertIn("lg:grid-cols-[380px_1fr]", grid.classes_value)
        self.assertTrue(any(element.kind == "column" and "min-h-screen" in element.classes_value for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "column" and "max-w-7xl" in element.classes_value for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "column" and "bg-white" in element.classes_value for element in fake_ui.elements))
        filter_heading = next(
            element
            for element in fake_ui.elements
            if element.kind == "label" and element.args == ("Filtros",)
        )

        def has_descendant(parent, target):
            return any(
                child is target or has_descendant(child, target)
                for child in parent.children
            )

        filter_panel = next(
            element
            for element in fake_ui.elements
            if element.kind == "column"
            and "bg-white" in element.classes_value
            and has_descendant(element, filter_heading)
        )
        with self.subTest("borderless white filter panel"):
            self.assertNotIn("border", filter_panel.classes_value.split())
            self.assertFalse(
                any(token.startswith("border-") for token in filter_panel.classes_value.split())
            )
            self.assertIn("shadow-sm", filter_panel.classes_value)
            self.assertIn("rounded-2xl", filter_panel.classes_value)
        with self.subTest("location filter caption clarifies it targets aid destination"):
            location_caption = next(
                element
                for element in fake_ui.elements
                if element.kind == "label"
                and element.args
                == (
                    "Busca por el departamento o ciudad hacia donde se "
                    "dirige la ayuda.",
                )
            )
            self.assertIn("text-xs", location_caption.classes_value)
            self.assertIn("text-slate-500", location_caption.classes_value)
            self.assertTrue(has_descendant(filter_panel, location_caption))
            department_select = next(
                element
                for element in fake_ui.elements
                if element.kind == "select" and element.kwargs.get("label") == "Departamento"
            )
            self.assertLess(
                fake_ui.elements.index(location_caption),
                fake_ui.elements.index(department_select),
            )
        with self.subTest("filter panel is the scroll target for the hero CTA"):
            self.assertIn("id=resultados", filter_panel.props_value)
        self.assertFalse(any("bg-emerald-50" in element.classes_value for element in fake_ui.elements))
        self.assertTrue(all("color=blue-grey-9" in element.props_value for element in selects))
        self.assertTrue(any(element.kind == "icon" and element.args == ("location_on",) for element in fake_ui.elements))
        find_cta = next(element for element in fake_ui.elements if element.kind == "link" and element.args == ("Encontrar cómo ayudar", "#resultados"))
        with self.subTest("primary hero CTA is finding help"):
            self.assertIn("bg-[#003893]", find_cta.classes_value)
        create_cta = next(element for element in fake_ui.elements if element.kind == "link" and element.args == ("Crear iniciativa", "/crear"))
        with self.subTest("both hero CTAs share the same solid brand color"):
            self.assertIn("bg-[#003893]", create_cta.classes_value)
            self.assertIn("text-white", create_cta.classes_value)
        with self.subTest("hero CTAs share the same fixed width"):
            find_width = [
                token for token in find_cta.classes_value.split() if token.startswith("sm:w-")
            ]
            create_width = [
                token for token in create_cta.classes_value.split() if token.startswith("sm:w-")
            ]
            self.assertEqual(find_width, create_width)
            self.assertNotEqual(find_width, ["sm:w-auto"])
        title = next(
            element
            for element in fake_ui.elements
            if element.kind == "label" and element.args == ("¿Dónde ayudo?",)
        )
        pin = next(
            element
            for element in fake_ui.elements
            if element.kind == "icon" and element.args == ("location_on",)
        )
        with self.subTest("Colombian flag stripe above everything else"):
            flag_stripe_colors = ("#FCD116", "#003893", "#CE1126")
            stripe_elements = [
                element
                for element in fake_ui.elements
                if element.kind == "row"
                and "h-1.5" in element.classes_value
                and any(color in element.classes_value for color in flag_stripe_colors)
            ]
            self.assertEqual(len(stripe_elements), 3)
            for color, element in zip(flag_stripe_colors, stripe_elements):
                self.assertIn(color, element.classes_value)
                self.assertIn("flex-1", element.classes_value)
            self.assertLess(
                max(fake_ui.elements.index(element) for element in stripe_elements),
                fake_ui.elements.index(title),
            )

        def has_descendant_of(parent, target):
            return any(
                child is target or has_descendant_of(child, target)
                for child in parent.children
            )

        hero = next(
            element
            for element in fake_ui.elements
            if element.kind == "column"
            and "bg-white" in element.classes_value
            and "border-b" in element.classes_value
            and has_descendant_of(element, title)
        )
        brand = next(
            (
                element
                for element in hero.children
                if element.kind == "column" and pin in element.children
            ),
            None,
        )
        with self.subTest("centered hero topology"):
            self.assertIn("items-center", hero.classes_value)
            self.assertIn("text-center", hero.classes_value)
            self.assertIsNotNone(brand)
            self.assertIn(title, brand.children)
            self.assertIn("items-center", brand.classes_value)
            self.assertLess(brand.children.index(pin), brand.children.index(title))
            cta_row = next(
                element
                for element in hero.children
                if element.kind == "row"
                and find_cta in element.children
                and create_cta in element.children
            )
            self.assertLess(
                cta_row.children.index(find_cta), cta_row.children.index(create_cta)
            )
            self.assertIn("text-2xl", title.classes_value)
            self.assertIn("sm:text-4xl", title.classes_value)
            self.assertIn("font-bold", title.classes_value)
            for cta in (find_cta, create_cta):
                self.assertIn("min-h-[48px]", cta.classes_value)
                self.assertIn("text-base", cta.classes_value)
                self.assertIn("px-6", cta.classes_value)
                self.assertIn("no-underline", cta.classes_value)
                self.assertIn("rounded-2xl", cta.classes_value)
            self.assertIn("bg-[#003893]", find_cta.classes_value)
            self.assertIn("text-white", find_cta.classes_value)
        with self.subTest("Colombian flag header icon"):
            self.assertIn("FCD116", pin.classes_value)
            self.assertIn("003893", pin.classes_value)
            self.assertIn("CE1126", pin.classes_value)
            self.assertIn("text-white", pin.classes_value)
        emergency_title = next(
            (
                element
                for element in fake_ui.elements
                if element.kind == "label"
                and element.args == ("Respuesta al terremoto de Chocó",)
            ),
            None,
        )
        context_panel = next(
            (
                element
                for element in fake_ui.elements
                if element.kind == "column" and emergency_title in element.children
            ),
            None,
        )
        with self.subTest("context panel"):
            self.assertIsNotNone(emergency_title)
            self.assertIsNotNone(context_panel)
            self.assertIn("rounded-2xl", context_panel.classes_value)
            self.assertIn("bg-white", context_panel.classes_value)
            self.assertIn("shadow-sm", context_panel.classes_value)
            self.assertIn("p-4", context_panel.classes_value)
            self.assertIn("border-l-4", context_panel.classes_value)
            self.assertIn("border-red-600", context_panel.classes_value)
        description_label = next(
            element
            for element in fake_ui.elements
            if element.kind == "label"
            and element.args == ("Explora el mapa o revisa la lista de puntos activos y ayudemos juntos a Colombia.",)
        )
        with self.subTest("section order: header, description, emergency, filters"):
            self.assertLess(
                fake_ui.elements.index(title),
                fake_ui.elements.index(description_label),
            )
            self.assertLess(
                fake_ui.elements.index(description_label),
                fake_ui.elements.index(context_panel),
            )
            self.assertLess(
                fake_ui.elements.index(context_panel),
                fake_ui.elements.index(filter_heading),
            )
        filters_row = next(
            element
            for element in fake_ui.elements
            if element.kind == "row"
            and department in element.children
            and city in element.children
        )
        self.assertIn("sm:flex-nowrap", filters_row.classes_value)
        self.assertIn("sm:w-auto", department.classes_value)
        self.assertIn("sm:flex-1", city.classes_value)

    def test_initial_map_and_compact_list_use_active_points_and_public_detail_links(self) -> None:
        category_id = uuid4()
        active = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(), name="Parque", description="Apoyo",
            locations=(
                HelpPointLocation(
                    id=uuid4(), address="Calle 5 # 10-20", city="Cali",
                    department="Valle del Cauca", latitude=3.4, longitude=-76.5,
                ),
            ),
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            coordinator_name="Ana", coordinator_contact="Contacto", active=True,
            needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, 10, 30, tzinfo=UTC),
        )
        inactive = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(), name="Cerrado", description="Cerrado",
            locations=(
                HelpPointLocation(
                    id=uuid4(), address=None, city="Bogotá",
                    department="Cundinamarca", latitude=4.6, longitude=-74.1,
                ),
            ),
            affected_areas=(AffectedArea(department="Quindío", city="Armenia"),),
            coordinator_name="Ana", coordinator_contact="Contacto", active=False,
            needs=(),
        )
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        mapped = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: mapped.append(tuple(points)),
                create=True,
            ):
                home.render_home(
                    (active, inactive),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
        finally:
            home.ui = original_ui

        self.assertEqual(mapped, [(active,)])
        self.assertTrue(any(element.kind == "link" and (element.kwargs.get("target") == f"/puntos/{active.id}" or element.args == ("Ver punto", f"/puntos/{active.id}")) for element in fake_ui.elements))
        self.assertFalse(any(element.kind == "link" and str(inactive.id) in repr((element.args, element.kwargs)) for element in fake_ui.elements))
        city = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Ciudad / Municipio")
        department = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Departamento")
        self.assertEqual(city.options, {"": "Selecciona primero un departamento"})
        self.assertEqual(tuple(department.options)[1:], AFFECTED_DEPARTMENTS)
        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        self.assertIn("📍 Roldanillo, Valle del Cauca", labels)
        self.assertIn("Labores de rescate", labels)
        self.assertIn("Publicado el 12 ago 2026", labels)
        with self.subTest("single aggregate activity indicator, not per card"):
            self.assertEqual(labels.count("Última actividad: el 1 ene 2020, 10:30"), 1)
            self.assertFalse(any(label.startswith("Actualizado") for label in labels))
            detail_link = next(
                element
                for element in fake_ui.elements
                if element.kind == "link"
                and element.kwargs.get("target") == f"/puntos/{active.id}"
            )
            card_descendants = []

            def collect(element):
                for child in element.children:
                    card_descendants.append(child)
                    collect(child)

            collect(detail_link)
            card_labels = [
                element.args[0] for element in card_descendants if element.kind == "label"
            ]
            self.assertFalse(any(label.startswith("Última actividad") for label in card_labels))
        with self.subTest("category chips list every category once"):
            todas_label = next(
                element
                for element in fake_ui.elements
                if element.kind == "label" and element.args == ("Todas las categorías",)
            )
            todas_chip_row = next(
                element
                for element in fake_ui.elements
                if element.kind == "row" and todas_label in element.children
            )
            chips_container = next(
                element
                for element in fake_ui.elements
                if element.kind == "row" and todas_chip_row in element.children
            )
            chip_descendants = []

            def collect_chip(element):
                for child in element.children:
                    chip_descendants.append(child)
                    collect_chip(child)

            collect_chip(chips_container)
            chip_labels = [
                element.args[0]
                for element in chip_descendants
                if element.kind == "label"
                and element.args
                and element.args[0] in {category.value for category in HelpPointCategory}
            ]
            self.assertEqual(len(chip_labels), len(HelpPointCategory))

    def test_result_row_shows_whole_department_when_city_is_none(self) -> None:
        category_id = uuid4()
        department_wide = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(), name="Parque", description="Apoyo",
            locations=(
                HelpPointLocation(
                    id=uuid4(), address="Calle 5 # 10-20", city="Cali",
                    department="Valle del Cauca", latitude=3.4, longitude=-76.5,
                ),
            ),
            affected_areas=(AffectedArea(department="Valle del Cauca", city=None),),
            coordinator_name="Ana", coordinator_contact="Contacto", active=True,
            needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
        )
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (department_wide,),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
        finally:
            home.ui = original_ui

        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        self.assertIn(
            "📍 Todo el departamento de Valle del Cauca", labels
        )
        self.assertFalse(any("None" in label for label in labels))

    def test_department_change_replaces_city_options_and_refreshes_map_immediately(self) -> None:
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        rendered_map_points = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: rendered_map_points.append(tuple(points)),
            ):
                points_test = PublicHelpPointFilteringTests()
                points_test.setUp()
                home.render_home(
                    points_test.points,
                    points_test.categories,
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
                department = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Departamento")
                city = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Ciudad / Municipio")
                department.value = "Valle del Cauca"
                department.on_change()
        finally:
            home.ui = original_ui

        self.assertEqual(
            city.options,
            {
                "": "Todas las ciudades / municipios",
                "Cali": "Cali",
                "Palmira": "Palmira",
                "Roldanillo": "Roldanillo",
            },
        )
        self.assertEqual(city.value, "")
        self.assertTrue(city.enabled)
        self.assertEqual(city.enable_calls, 1)
        self.assertEqual(city.update_calls, 1)
        self.assertEqual(rendered_map_points[-1], (points_test.cali_water,))

        city.value = "Cali"
        department.value = ""
        department.on_change()

        self.assertEqual(
            city.options,
            {"": "Selecciona primero un departamento"},
        )
        self.assertEqual(city.value, "")
        self.assertFalse(city.enabled)
        self.assertEqual(city.disable_calls, 2)

    def test_category_change_refreshes_map_to_only_that_category(self) -> None:
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        rendered_map_points = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: rendered_map_points.append(tuple(points)),
            ):
                points_test = PublicHelpPointFilteringTests()
                points_test.setUp()
                donation_point = points_test.point(
                    name="Punto de donaciones",
                    city="Cali",
                    department="Valle del Cauca",
                    affected_areas=(
                        AffectedArea(department="Valle del Cauca", city="Roldanillo"),
                    ),
                    active=True,
                    category_id=points_test.water_id,
                    category=HelpPointCategory.DONATION_COLLECTION,
                )
                home.render_home(
                    (*points_test.points, donation_point),
                    points_test.categories,
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
                click_category_chip(
                    fake_ui, HelpPointCategory.DONATION_COLLECTION.value
                )
        finally:
            home.ui = original_ui

        self.assertEqual(rendered_map_points[-1], (donation_point,))

    def test_search_query_refreshes_map_and_results_to_matching_points(self) -> None:
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        rendered_map_points = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: rendered_map_points.append(tuple(points)),
            ):
                points_test = PublicHelpPointFilteringTests()
                points_test.setUp()
                home.render_home(
                    points_test.points,
                    points_test.categories,
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
                search_input = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                )
                search_input.value = "parque"
                search_input.on_change()
        finally:
            home.ui = original_ui

        self.assertEqual(rendered_map_points[-1], (points_test.cali_water,))

    def test_activity_indicator_reflects_only_the_currently_filtered_points(self) -> None:
        category_id = uuid4()

        def point(name, category, updated_at):
            return PublicHelpPoint(category=category,
                id=uuid4(), name=name, description="Apoyo",
                locations=(
                    HelpPointLocation(
                        id=uuid4(), address="Calle 5", city="Cali",
                        department="Valle del Cauca", latitude=4.0, longitude=-75.0,
                    ),
                ),
                affected_areas=(
                    AffectedArea(department="Valle del Cauca", city="Roldanillo"),
                ),
                coordinator_name="Ana", coordinator_contact="Contacto", active=True,
                needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
                updated_at=updated_at,
            )

        old_donation = point(
            "Donaciones viejo",
            HelpPointCategory.DONATION_COLLECTION,
            datetime(2020, 1, 1, tzinfo=UTC),
        )
        new_rescue = point(
            "Rescate nuevo",
            HelpPointCategory.RESCUE_OPERATIONS,
            datetime(2020, 6, 1, tzinfo=UTC),
        )
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (old_donation, new_rescue),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )

                def activity_labels():
                    return [
                        element.args[0]
                        for element in fake_ui.elements
                        if element.kind == "label"
                        and element.args
                        and element.args[0].startswith("Última actividad")
                    ]

                self.assertEqual(activity_labels(), ["Última actividad: el 1 jun 2020, 00:00"])

                click_category_chip(
                    fake_ui, HelpPointCategory.DONATION_COLLECTION.value
                )

                self.assertEqual(activity_labels(), ["Última actividad: el 1 ene 2020, 00:00"])

                click_category_chip(fake_ui, HelpPointCategory.DEBRIS_REMOVAL.value)

                self.assertEqual(activity_labels(), [])
        finally:
            home.ui = original_ui

    def test_result_cards_render_in_a_responsive_multi_column_grid(self) -> None:
        category_id = uuid4()

        def point(name):
            return PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
                id=uuid4(), name=name, description="Apoyo",
                locations=(
                    HelpPointLocation(
                        id=uuid4(), address="Calle 5", city="Cali",
                        department="Valle del Cauca", latitude=4.0, longitude=-75.0,
                    ),
                ),
                affected_areas=(
                    AffectedArea(department="Valle del Cauca", city="Roldanillo"),
                ),
                coordinator_name="Ana", coordinator_contact="Contacto", active=True,
                needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
            )

        first, second = point("Primero"), point("Segundo")
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (first, second),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
        finally:
            home.ui = original_ui

        cards_grid = next(
            element
            for element in fake_ui.elements
            if element.kind == "grid" and "sm:grid-cols-2" in element.classes_value
        )
        card_links = [
            element
            for element in fake_ui.elements
            if element.kind == "link"
            and element.kwargs.get("target", "").startswith("/puntos/")
        ]
        self.assertEqual(len(card_links), 2)
        self.assertTrue(all(link in cards_grid.children for link in card_links))

    def test_result_row_shows_the_most_urgent_need_names_and_remainder_count(self) -> None:
        need_specs = [
            ("Cubierto B", NeedStatus.COVERED),
            ("En camino C", NeedStatus.HELP_ON_THE_WAY),
            ("Urgente Z", NeedStatus.NEEDS_HELP),
            ("Urgente A", NeedStatus.NEEDS_HELP),
        ]
        category_ids = [uuid4() for _ in need_specs]
        point = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(), name="Parque", description="Apoyo",
            locations=(
                HelpPointLocation(
                    id=uuid4(), address="Calle 5 # 10-20", city="Cali",
                    department="Valle del Cauca", latitude=3.4, longitude=-76.5,
                ),
            ),
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            coordinator_name="Ana", coordinator_contact="Contacto", active=True,
            needs=tuple(Need(id=uuid4(), category_id=category_id, status=status)
                        for category_id, (_, status) in zip(category_ids, need_specs)),
        )
        categories = {name: category_id for category_id, (name, _status) in zip(category_ids, need_specs)}
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (point,),
                    categories,
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
        finally:
            home.ui = original_ui

        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        with self.subTest("preview shows the two most urgent need names plus remainder"):
            self.assertIn("Necesita: Urgente A, Urgente Z +2 más", labels)
            for need_name, _status in need_specs:
                if need_name not in ("Urgente A", "Urgente Z"):
                    self.assertNotIn(need_name, labels)
        detail_link = next(
            element
            for element in fake_ui.elements
            if element.kind == "link"
            and element.kwargs.get("target") == f"/puntos/{point.id}"
        )
        self.assertIn("w-full", detail_link.classes_value)
        descendants = []

        def collect(element):
            for child in element.children:
                descendants.append(child)
                collect(child)

        collect(detail_link)
        wrapped_labels = [element.args[0] for element in descendants if element.kind == "label"]
        self.assertIn("Parque", wrapped_labels)
        self.assertIn("📍 Roldanillo, Valle del Cauca", wrapped_labels)
        self.assertTrue(
            any(element.kind == "icon" and element.args == ("chevron_right",) for element in descendants)
        )
        row = next(element for element in descendants if element.kind == "row")
        self.assertIn("bg-white", detail_link.classes_value + " " + row.classes_value)
        with self.subTest("card polish: rounder corners and hover lift"):
            self.assertIn("rounded-2xl", detail_link.classes_value)
            self.assertIn("hover:shadow-md", detail_link.classes_value)
            self.assertIn("transition-shadow", detail_link.classes_value)
        with self.subTest("card accent and badge match the map pin color"):
            color = category_pin_color(HelpPointCategory.RESCUE_OPERATIONS)
            self.assertIn(f"border-[{color}]", detail_link.classes_value)
            badge = next(
                element
                for element in descendants
                if element.kind == "label" and element.args == ("Labores de rescate",)
            )
            self.assertIn(f"bg-[{color}]", badge.classes_value)

    def test_consecutive_filter_changes_keep_map_links_and_count_synchronized_including_zero(self) -> None:
        category_id = uuid4()

        def point(name, city, department, affected_city, affected_department):
            return PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
                id=uuid4(), name=name, description="Apoyo",
                locations=(
                    HelpPointLocation(
                        id=uuid4(), address="Calle 5", city=city,
                        department=department, latitude=4.0, longitude=-75.0,
                    ),
                ),
                affected_areas=(
                    AffectedArea(
                        department=affected_department, city=affected_city
                    ),
                ),
                coordinator_name="Ana", coordinator_contact="Contacto", active=True,
                needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
            )

        cali = point("Cali", "Cali", "Valle del Cauca", "Roldanillo", "Valle del Cauca")
        palmira = point("Palmira", "Cali", "Valle del Cauca", "Palmira", "Valle del Cauca")
        medellin = point("Medellín", "Medellín", "Antioquia", "Quibdó", "Chocó")
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        mapped = []
        try:
            with patch.object(
                home,
                "render_help_point_map",
                side_effect=lambda points, _categories: mapped.append(tuple(points)),
            ):
                home.render_home(
                    (cali, palmira, medellin),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
                department = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Departamento")
                city = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs["label"] == "Ciudad / Municipio")

                def assert_visible(expected_points):
                    expected_ids = {str(item.id) for item in expected_points}
                    link_ids = {
                        element.kwargs["target"].rsplit("/", 1)[-1]
                        for element in fake_ui.elements
                        if element.kind == "link"
                        and element.kwargs.get("target", "").startswith("/puntos/")
                    }
                    count = next(
                        element.args[0]
                        for element in fake_ui.elements
                        if element.kind == "label"
                        and element.args[0].endswith(" resultados")
                    )
                    self.assertEqual({str(item.id) for item in mapped[-1]}, expected_ids)
                    self.assertEqual(link_ids, expected_ids)
                    self.assertEqual(count, f"{len(expected_ids)} resultados")

                assert_visible((cali, palmira, medellin))
                department.value = "Valle del Cauca"
                department.on_change()
                assert_visible((cali, palmira))
                city.value = "Palmira"
                city.on_change()
                assert_visible((palmira,))
                department.value = "Chocó"
                department.on_change()
                self.assertEqual(city.value, "")
                assert_visible((medellin,))
                city.value = "Cali"
                city.on_change()
                assert_visible(())
        finally:
            home.ui = original_ui

        self.assertTrue(
            any(
                element.kind == "label"
                and element.args
                == (
                    "No encontramos puntos con estos filtros. "
                    "Prueba con otro departamento, ciudad / municipio o categoría.",
                )
                for element in fake_ui.elements
            )
        )


if __name__ == "__main__":
    unittest.main()
