from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from backend.domain.models import (
    AffectedArea,
    HelpPointCategory,
    HelpPointLocation,
    Need,
    NeedStatus,
    PublicHelpPoint,
)
from frontend.pages import home
from frontend.pages.home import (
    affected_area_text,
    filter_public_help_points,
    location_filter_options,
    status_line,
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


class RecordingElement:
    def __init__(self, owner, kind, *args, **kwargs):
        self.owner = owner
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.children = []
        self.value = kwargs.get("value")
        self.options = kwargs.get("options", args[0] if args else None)
        self.on_change = kwargs.get("on_change")
        self.update_calls = 0
        self.classes_value = ""
        self.props_value = ""
        self.enabled = True
        self.enable_calls = 0
        self.disable_calls = 0

    def __enter__(self): self.owner.stack.append(self); return self
    def __exit__(self, *_args): self.owner.stack.pop(); return False
    def classes(self, value): self.classes_value = value; return self
    def props(self, value):
        self.props_value = value
        if "disable" in value.split():
            self.enabled = False
        return self
    def enable(self): self.enable_calls += 1; self.enabled = True
    def disable(self): self.disable_calls += 1; self.enabled = False
    def clear(self):
        def remove_descendants(element):
            for child in tuple(element.children):
                remove_descendants(child)
                if child in self.owner.elements:
                    self.owner.elements.remove(child)
            element.children.clear()

        remove_descendants(self)
    def update(self): self.update_calls += 1


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
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def select(self, *args, **kwargs): return self._record("select", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def link(self, *args, **kwargs): return self._record("link", *args, **kwargs)
    def icon(self, *args, **kwargs): return self._record("icon", *args, **kwargs)


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

        self.assertTrue(any(element.kind == "link" and element.args == ("Crear nuevo punto de ayuda o recolección", "/crear") for element in fake_ui.elements))
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
            self.assertIn(emergency_explanation, visible_labels)
        self.assertTrue(any(element.kind == "label" and element.args == ("Explora el mapa o revisa la lista de puntos activos.",) for element in fake_ui.elements))
        self.assertTrue(any(element.kind == "label" and element.args == ("Puntos que necesitan ayuda — 0 resultados",) for element in fake_ui.elements))
        self.assertEqual(rendered_map_points, [()])
        selects = [element for element in fake_ui.elements if element.kind == "select"]
        self.assertEqual(
            {element.kwargs["label"] for element in selects},
            {"Ciudad / Municipio", "Departamento", "Categoría del punto"},
        )
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
        with self.subTest("white rounded selectors"):
            self.assertTrue(all("bg-white" in element.classes_value for element in selects))
            self.assertTrue(all("rounded-lg" in element.classes_value for element in selects))
        self.assertTrue(all("outlined" in element.props_value for element in selects))
        self.assertTrue(all("dense" in element.props_value for element in selects))
        for select in selects:
            with self.subTest(select=select.kwargs["label"]):
                self.assertIn("behavior=menu", select.props_value)
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
        self.assertIn("lg:grid-cols-[3fr_2fr]", grid.classes_value)
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
            and "bg-slate-100" in element.classes_value
            and has_descendant(element, filter_heading)
        )
        with self.subTest("borderless slate filter panel"):
            self.assertNotIn("border", filter_panel.classes_value.split())
            self.assertFalse(
                any(token.startswith("border-") for token in filter_panel.classes_value.split())
            )
        self.assertFalse(any("bg-emerald-50" in element.classes_value for element in fake_ui.elements))
        self.assertTrue(all("color=blue-grey-9" in element.props_value for element in selects))
        self.assertTrue(any(element.kind == "icon" and element.args == ("location_on",) for element in fake_ui.elements))
        cta = next(element for element in fake_ui.elements if element.kind == "link" and element.args == ("Crear nuevo punto de ayuda o recolección", "/crear"))
        self.assertIn("bg-emerald-700", cta.classes_value)
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
        header = next(
            (
                element
                for element in fake_ui.elements
                if element.kind == "row" and cta in element.children
            ),
            None,
        )
        with self.subTest("brand topology"):
            self.assertIsNotNone(header)
            brand = next(
                (
                    element
                    for element in header.children
                    if element.kind == "row" and pin in element.children
                ),
                None,
            )
            self.assertIsNotNone(brand)
            self.assertIn(title, brand.children)
            self.assertIn(cta, header.children)
            self.assertIn("flex-wrap", header.classes_value)
            self.assertIn("sm:flex-nowrap", header.classes_value)
            self.assertIn("flex-1", brand.classes_value)
            self.assertIn("min-w-0", brand.classes_value)
            self.assertIn("flex-nowrap", brand.classes_value)
            self.assertIn("whitespace-nowrap", title.classes_value)
            self.assertIn("text-lg", title.classes_value)
            self.assertIn("sm:text-2xl", title.classes_value)
            self.assertIn("shrink-0", cta.classes_value)
            self.assertIn("w-full", cta.classes_value)
            self.assertIn("sm:w-auto", cta.classes_value)
            self.assertIn("min-h-[48px]", cta.classes_value)
            self.assertIn("text-base", cta.classes_value)
            self.assertIn("px-4", cta.classes_value)
            self.assertIn("bg-emerald-700", cta.classes_value)
            self.assertIn("text-white", cta.classes_value)
            self.assertIn("no-underline", cta.classes_value)
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
            self.assertIn("bg-slate-100", context_panel.classes_value)
            self.assertIn("p-4", context_panel.classes_value)
        if context_panel is not None:
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
        self.assertIn("Ayuda destinada a: Roldanillo, Valle del Cauca", labels)
        self.assertIn(
            "Recibe ayuda en: Calle 5 # 10-20, Cali, Valle del Cauca",
            labels,
        )
        self.assertIn("Labores de rescate", labels)
        self.assertIn("Publicado el 12 ago 2026", labels)
        self.assertIn("Actualizado el 1 ene 2020, 10:30", labels)
        category_select = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs["label"] == "Categoría del punto"
        )
        self.assertEqual(category_select.options[""], "Todas las categorías")
        self.assertEqual(len(category_select.options) - 1, len(HelpPointCategory))

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
            "Ayuda destinada a: Todo el departamento de Valle del Cauca", labels
        )
        self.assertFalse(any("None" in label for label in labels))

    def test_result_card_lists_every_location(self) -> None:
        category_id = uuid4()
        multi = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(), name="Parque", description="Apoyo",
            locations=(
                HelpPointLocation(
                    id=uuid4(), address="Calle 5 # 10-20", city="Cali",
                    department="Valle del Cauca", latitude=3.4, longitude=-76.5,
                ),
                HelpPointLocation(
                    id=uuid4(), address="Carrera 9 # 3-12", city="Palmira",
                    department="Valle del Cauca", latitude=3.5, longitude=-76.3,
                ),
            ),
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            coordinator_name="Ana", coordinator_contact="Contacto", active=True,
            needs=(Need(id=uuid4(), category_id=category_id, status=NeedStatus.NEEDS_HELP),),
        )
        fake_ui = RecordingUi()
        original_ui = home.ui
        home.ui = fake_ui
        try:
            with patch.object(home, "render_help_point_map"):
                home.render_home(
                    (multi,),
                    {"Agua": category_id},
                    lambda: AFFECTED_DEPARTMENTS,
                    list_localities,
                )
        finally:
            home.ui = original_ui

        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        self.assertEqual(
            labels.count("Recibe ayuda en: Calle 5 # 10-20, Cali, Valle del Cauca"),
            1,
        )
        self.assertEqual(
            labels.count("Recibe ayuda en: Carrera 9 # 3-12, Palmira, Valle del Cauca"),
            1,
        )

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
                category_select = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs["label"] == "Categoría del punto"
                )
                category_select.value = HelpPointCategory.DONATION_COLLECTION
                category_select.on_change()
        finally:
            home.ui = original_ui

        self.assertEqual(rendered_map_points[-1], (donation_point,))

    def test_result_row_shows_at_most_three_needs_and_remainder_count(self) -> None:
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
        need_labels = [label for label in labels if label.startswith(("🔴", "🟡", "🟢"))]
        self.assertEqual(
            need_labels,
            [
                "🔴 Urgente A",
                "🔴 Urgente Z",
                "🟡 En camino C",
            ],
        )
        self.assertIn("+1 necesidades", labels)
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
        self.assertIn("Ayuda destinada a: Roldanillo, Valle del Cauca", wrapped_labels)
        self.assertIn(
            "Recibe ayuda en: Calle 5 # 10-20, Cali, Valle del Cauca",
            wrapped_labels,
        )
        self.assertIn("Apoyo", wrapped_labels)
        self.assertTrue(
            any(element.kind == "icon" and element.args == ("chevron_right",) for element in descendants)
        )
        row = next(element for element in descendants if element.kind == "row")
        self.assertIn("bg-white", detail_link.classes_value + " " + row.classes_value)

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
                        and element.args[0].startswith("Puntos que necesitan ayuda —")
                    )
                    self.assertEqual({str(item.id) for item in mapped[-1]}, expected_ids)
                    self.assertEqual(link_ids, expected_ids)
                    self.assertEqual(count, f"Puntos que necesitan ayuda — {len(expected_ids)} resultados")

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
