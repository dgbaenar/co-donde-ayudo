from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from datetime import UTC, datetime
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
from frontend.pages import help_point_detail


class RecordingElement:
    def __init__(self, ui, kind, *args, **kwargs):
        self.ui = ui
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.value = kwargs.get("value")
        self.classes_value = ""
        self.props_value = ""
        self.children = []

    def __enter__(self):
        self.ui.context.append(self)
        return self

    def __exit__(self, *_args):
        self.ui.context.pop()
        return False

    def classes(self, value):
        self.classes_value = value
        return self

    def props(self, value):
        self.props_value = value
        return self

    def clear(self):
        removed = set(_descendants(self))
        self.ui.elements[:] = [
            element for element in self.ui.elements if element not in removed
        ]
        self.children.clear()

    def set_text(self, value):
        self.args = (value,)
        return self


class RecordingDialog(RecordingElement):
    def __init__(self, ui, *args, **kwargs):
        super().__init__(ui, "dialog", *args, **kwargs)
        self.opened = False
        self.open_calls = 0
        self.close_calls = 0

    def open(self):
        self.opened = True
        self.open_calls += 1

    def close(self):
        self.opened = False
        self.close_calls += 1


class RecordingUi:
    def __init__(self) -> None:
        self.elements = []
        self.context = []

    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(self, kind, *args, **kwargs)
        self.elements.append(element)
        if self.context:
            self.context[-1].children.append(element)
        return element

    def column(self, *args, **kwargs):
        return self._record("column", *args, **kwargs)

    def grid(self, *args, **kwargs):
        return self._record("grid", *args, **kwargs)

    def row(self, *args, **kwargs):
        return self._record("row", *args, **kwargs)

    def link(self, *args, **kwargs):
        return self._record("link", *args, **kwargs)

    def label(self, *args, **kwargs):
        return self._record("label", *args, **kwargs)

    def html(self, *args, **kwargs):
        return self._record("html", *args, **kwargs)

    def card(self, *args, **kwargs):
        return self._record("card", *args, **kwargs)

    def input(self, *args, **kwargs):
        return self._record("input", *args, **kwargs)

    def textarea(self, *args, **kwargs):
        return self._record("textarea", *args, **kwargs)

    def button(self, *args, **kwargs):
        return self._record("button", *args, **kwargs)

    def icon(self, *args, **kwargs):
        return self._record("icon", *args, **kwargs)

    def notify(self, *args, **kwargs):
        return self._record("notify", *args, **kwargs)

    def dialog(self, *args, **kwargs):
        element = RecordingDialog(self, *args, **kwargs)
        self.elements.append(element)
        if self.context:
            self.context[-1].children.append(element)
        return element

    def timer(self, *args, **kwargs):
        return self._record("timer", *args, **kwargs)


def _descendants(element):
    for child in element.children:
        yield child
        yield from _descendants(child)


class HelpPointDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.water_category_id = uuid4()
        self.food_category_id = uuid4()
        self.shelter_category_id = uuid4()
        self.point = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(),
            name="Parque Central",
            description="Familias evacuadas reciben apoyo.",
            locations=(
                HelpPointLocation(
                    id=uuid4(),
                    address="Calle 5 # 10-20",
                    city="Cali",
                    department="Valle del Cauca",
                    latitude=3.4516,
                    longitude=-76.532,
                ),
            ),
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=True,
            needs=(
                Need(
                    id=uuid4(),
                    category_id=self.water_category_id,
                    status=NeedStatus.NEEDS_HELP,
                ),
                Need(
                    id=uuid4(),
                    category_id=self.food_category_id,
                    status=NeedStatus.HELP_ON_THE_WAY,
                ),
                Need(
                    id=uuid4(),
                    category_id=self.shelter_category_id,
                    status=NeedStatus.COVERED,
                ),
            ),
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
        )
        self.categories = {
            "Agua": self.water_category_id,
            "Alimentos": self.food_category_id,
            "Refugio": self.shelter_category_id,
        }
        self.fake_ui = RecordingUi()
        self.ui_patch = patch.object(help_point_detail, "ui", self.fake_ui)
        self.ui_patch.start()
        self.addCleanup(self.ui_patch.stop)
        self.no_op_create_commitment = lambda *_args: object()

    def test_cached_detail_renders_immediately_without_database_refresh(self) -> None:
        cached = SimpleNamespace(
            point=self.point,
            categories=self.categories,
            stale=False,
        )
        refresh_calls = []

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_cached_help_point_detail_for_path(
                str(self.point.id),
                lambda _point_id: cached,
                lambda point_id: refresh_calls.append(point_id),
                self.no_op_create_commitment,
            )

        self.assertIn(
            self.point.name,
            [
                element.args[0]
                for element in self.fake_ui.elements
                if element.kind == "label"
            ],
        )
        self.assertEqual(refresh_calls, [])
        self.assertFalse(
            any(element.kind == "timer" for element in self.fake_ui.elements)
        )

    def test_stale_detail_renders_immediately_and_refreshes_in_background(self) -> None:
        cached = SimpleNamespace(
            point=self.point,
            categories=self.categories,
            stale=True,
        )
        refresh_calls = []

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_cached_help_point_detail_for_path(
                str(self.point.id),
                lambda _point_id: cached,
                lambda point_id: refresh_calls.append(point_id) or cached,
                self.no_op_create_commitment,
            )

        timer = next(
            element for element in self.fake_ui.elements if element.kind == "timer"
        )
        self.assertIn(
            self.point.name,
            [
                element.args[0]
                for element in self.fake_ui.elements
                if element.kind == "label"
            ],
        )

        asyncio.run(timer.args[1]())

        self.assertEqual(refresh_calls, [self.point.id])

    def test_cold_detail_shows_loading_then_renders_direct_lookup(self) -> None:
        refreshed = SimpleNamespace(
            point=self.point,
            categories=self.categories,
            stale=False,
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_cached_help_point_detail_for_path(
                str(self.point.id),
                lambda _point_id: None,
                lambda _point_id: refreshed,
                self.no_op_create_commitment,
            )
            labels_before = [
                element.args[0]
                for element in self.fake_ui.elements
                if element.kind == "label"
            ]
            timer = next(
                element for element in self.fake_ui.elements if element.kind == "timer"
            )
            asyncio.run(timer.args[1]())

        self.assertIn("Cargando punto de ayuda…", labels_before)
        labels_after = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn(self.point.name, labels_after)
        self.assertNotIn("Cargando punto de ayuda…", labels_after)

    def test_valid_uuid_renders_semantic_sections_status_rows_and_point_map(self) -> None:
        requested_ids = []

        with patch.object(help_point_detail, "render_help_point_map") as render_map:
            help_point_detail.render_help_point_detail_for_path(
                str(self.point.id),
                lambda point_id: requested_ids.append(point_id) or self.point,
                self.categories,
                self.no_op_create_commitment,
            )

        self.assertEqual(requested_ids, [self.point.id])
        self.assertTrue(
            any(
                element.kind == "column"
                and "bg-slate-50" in element.classes_value
                for element in self.fake_ui.elements
            )
        )
        self.assertTrue(
            any(
                element.kind == "column"
                and "max-w-4xl" in element.classes_value
                for element in self.fake_ui.elements
            )
        )
        self.assertTrue(
            any(
                element.kind == "link"
                and element.args == ("Volver al mapa", "/")
                for element in self.fake_ui.elements
            )
        )
        headings = [
            element
            for element in self.fake_ui.elements
            if element.kind == "label" and "role=heading" in element.props_value
        ]
        level_one = [
            element.args[0]
            for element in headings
            if "aria-level=1" in element.props_value
        ]
        level_two = [
            element.args[0]
            for element in headings
            if "aria-level=2" in element.props_value
        ]
        self.assertEqual(level_one, ["Parque Central"])
        self.assertEqual(
            level_two,
            [
                "Ayuda destinada a",
                "Recibe ayuda en",
                "Necesidades actuales",
                "Ubicación del punto de recepción",
            ],
        )
        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Familias evacuadas reciben apoyo.", labels)
        self.assertIn("Coordina: Ana", labels)
        self.assertIn("Contacto: Contacto", labels)
        self.assertIn(
            "Verifica la identidad de esta persona antes de confiarle dinero "
            "o datos personales, y confirma que esta iniciativa siga activa.",
            labels,
        )
        self.assertIn("Publicado el 12 ago 2026", labels)
        self.assertIn("Roldanillo, Valle del Cauca", labels)
        self.assertIn("Calle 5 # 10-20, Cali, Valle del Cauca", labels)
        self.assertFalse(any(label.startswith("También:") for label in labels))
        self.assertIn("Se necesita", labels)
        self.assertIn("En camino", labels)
        self.assertIn("Cubierto", labels)
        self.assertIn("Agua", labels)
        self.assertIn("Alimentos", labels)
        self.assertIn("Refugio", labels)
        self.assertIn(
            "Marca \"Voy a ayudar\" solo si de verdad vas a cumplir con esa "
            "necesidad. Si no vas a poder, por favor no la marques.",
            labels,
        )
        with self.subTest("category badge and matching colored accent"):
            from frontend.components.help_point_map import category_pin_color

            self.assertIn("Labores de rescate", labels)
            main_card = next(
                element
                for element in self.fake_ui.elements
                if element.kind == "column" and level_one[0]
                and any(
                    child.args and child.args[0] == level_one[0]
                    for child in element.children
                    if child.kind == "label"
                )
            )
            color = category_pin_color(HelpPointCategory.RESCUE_OPERATIONS)
            self.assertIn(f"border-[{color}]", main_card.classes_value)
            self.assertIn("border-l-4", main_card.classes_value)
        self.assertIn(
            "El amarillo se activa automáticamente al confirmar ayuda. "
            "Solo quien coordina este punto puede marcarlo como cubierto "
            "(verde).",
            labels,
        )
        self.assertFalse(
            any(element.kind == "html" for element in self.fake_ui.elements)
        )
        location_grid = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "grid"
        )
        self.assertIn("grid-cols-1", location_grid.classes_value)
        self.assertIn("md:grid-cols-2", location_grid.classes_value)
        status_rows = [
            element
            for element in self.fake_ui.elements
            if element.kind in ("row", "column")
            and "border-l-4" in element.classes_value
            and any(
                token in element.classes_value
                for token in ("border-l-red-500", "border-l-amber-500", "border-l-emerald-500")
            )
        ]
        self.assertEqual(len(status_rows), 3)
        self.assertTrue(
            any("red" in element.classes_value for element in status_rows)
        )
        self.assertTrue(
            any("amber" in element.classes_value for element in status_rows)
        )
        self.assertTrue(
            any("emerald" in element.classes_value for element in status_rows)
        )
        self.assertFalse(
            any(
                "coordinator" in str(label).lower()
                or "token" in str(label).lower()
                for label in labels
            )
        )
        render_map.assert_called_once_with(
            (self.point,),
            self.categories,
            center=(3.4516, -76.532),
            zoom=15,
        )

    def test_additional_affected_areas_renders_as_second_line_when_present(self) -> None:
        point_with_extra_areas = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            locations=self.point.locations,
            affected_areas=self.point.affected_areas,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=self.point.active,
            needs=self.point.needs,
            additional_affected_areas="Roldanillo y Zarzal",
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(point_with_extra_areas.id),
                lambda _point_id: point_with_extra_areas,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("También: Roldanillo y Zarzal", labels)

    def test_additional_affected_areas_renders_nothing_when_none(self) -> None:
        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(self.point.id),
                lambda _point_id: self.point,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertFalse(any(label.startswith("También:") for label in labels))

    def test_affected_area_shows_whole_department_when_city_is_none(
        self,
    ) -> None:
        department_wide_point = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            locations=self.point.locations,
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city=None),
            ),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=self.point.active,
            needs=self.point.needs,
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(department_wide_point.id),
                lambda _point_id: department_wide_point,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Todo el departamento de Valle del Cauca", labels)
        self.assertFalse(any("None" in label for label in labels))

    def test_affected_area_lists_multiple_departments_and_groups_their_cities(
        self,
    ) -> None:
        multi_area_point = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            locations=self.point.locations,
            affected_areas=(
                AffectedArea(department="Chocó", city="Quibdó"),
                AffectedArea(department="Chocó", city="Istmina"),
                AffectedArea(department="Caldas", city=None),
            ),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=self.point.active,
            needs=self.point.needs,
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(multi_area_point.id),
                lambda _point_id: multi_area_point,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn(
            "Quibdó, Istmina, Chocó; Todo el departamento de Caldas", labels
        )

    def test_important_links_section_renders_each_link_when_present(self) -> None:
        point_with_links = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            locations=self.point.locations,
            affected_areas=self.point.affected_areas,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=self.point.active,
            needs=self.point.needs,
            important_links=(
                "https://example.com/donaciones",
                "https://redsocial.example/punto",
            ),
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(point_with_links.id),
                lambda _point_id: point_with_links,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Enlaces importantes", labels)
        link_elements = [
            element for element in self.fake_ui.elements if element.kind == "link"
        ]
        self.assertTrue(
            any(
                element.args
                == (
                    "https://example.com/donaciones",
                    "https://example.com/donaciones",
                )
                for element in link_elements
            )
        )
        self.assertTrue(
            any(
                element.args
                == (
                    "https://redsocial.example/punto",
                    "https://redsocial.example/punto",
                )
                for element in link_elements
            )
        )

    def test_important_links_section_absent_when_empty(self) -> None:
        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(self.point.id),
                lambda _point_id: self.point,
                self.categories,
                self.no_op_create_commitment,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertNotIn("Enlaces importantes", labels)

    def test_invalid_or_missing_point_shows_same_generic_message(self) -> None:
        for path_value, getter in (
            ("not-a-uuid", lambda _point_id: self.fail("invalid UUID must not reach backend")),
            (str(uuid4()), lambda _point_id: None),
        ):
            with self.subTest(path_value=path_value):
                self.fake_ui.elements.clear()
                with patch.object(help_point_detail, "render_help_point_map") as render_map:
                    help_point_detail.render_help_point_detail_for_path(
                        path_value, getter, {}, self.no_op_create_commitment
                    )

                labels = [
                    element.args[0]
                    for element in self.fake_ui.elements
                    if element.kind == "label"
                ]
                self.assertEqual(labels, ["No fue posible encontrar este punto de ayuda."])
                render_map.assert_not_called()


class VoyAAyudarDialogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.category_id = uuid4()
        self.covered_category_id = uuid4()
        self.needs_help_id = uuid4()
        self.help_on_the_way_id = uuid4()
        self.covered_id = uuid4()
        self.point = PublicHelpPoint(category=HelpPointCategory.RESCUE_OPERATIONS,
            id=uuid4(),
            name="Parque Central",
            description="Familias evacuadas reciben apoyo.",
            locations=(
                HelpPointLocation(
                    id=uuid4(),
                    address="Calle 5 # 10-20",
                    city="Cali",
                    department="Valle del Cauca",
                    latitude=3.4516,
                    longitude=-76.532,
                ),
            ),
            affected_areas=(
                AffectedArea(department="Valle del Cauca", city="Roldanillo"),
            ),
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            active=True,
            needs=(
                Need(
                    id=self.needs_help_id,
                    category_id=self.category_id,
                    status=NeedStatus.NEEDS_HELP,
                ),
                Need(
                    id=self.help_on_the_way_id,
                    category_id=self.category_id,
                    status=NeedStatus.HELP_ON_THE_WAY,
                ),
                Need(
                    id=self.covered_id,
                    category_id=self.covered_category_id,
                    status=NeedStatus.COVERED,
                ),
            ),
        )
        self.categories = {"Agua": self.category_id, "Refugio": self.covered_category_id}
        self.fake_ui = RecordingUi()
        self.ui_patch = patch.object(help_point_detail, "ui", self.fake_ui)
        self.ui_patch.start()
        self.addCleanup(self.ui_patch.stop)
        self.map_patch = patch.object(help_point_detail, "render_help_point_map")
        self.map_patch.start()
        self.addCleanup(self.map_patch.stop)

    def _render(self, create_commitment) -> None:
        help_point_detail.render_help_point_detail(
            self.point, self.categories, create_commitment
        )

    def _trigger_buttons(self):
        return [
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Voy a ayudar",)
        ]

    def test_button_appears_only_on_needs_that_are_not_covered(self) -> None:
        self._render(lambda *_args: object())

        self.assertEqual(len(self._trigger_buttons()), 2)

    def test_all_buttons_use_the_same_pill_shape(self) -> None:
        self._render(lambda *_args: object())

        buttons = [element for element in self.fake_ui.elements if element.kind == "button"]
        self.assertTrue(buttons)
        for button in buttons:
            with self.subTest(button=button.args[0] if button.args else None):
                self.assertIn("rounded-2xl", button.classes_value)

    def test_button_opens_dialog_with_required_name_and_optional_note_fields(self) -> None:
        self._render(lambda *_args: object())

        dialog = next(element for element in self.fake_ui.elements if element.kind == "dialog")
        trigger = self._trigger_buttons()[0]
        self.assertEqual(trigger.kwargs["on_click"], dialog.open)

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        note_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "textarea" and element.args == ("Nota (opcional)",)
        )
        self.assertEqual(note_input.kwargs.get("placeholder"), "Ej: Voy para allá.")
        self.assertIsNotNone(name_input)

    def test_confirm_calls_handler_with_need_id_name_and_none_note_when_note_blank(
        self,
    ) -> None:
        calls = []

        def create_commitment(need_id, name, note):
            calls.append((need_id, name, note))
            return Need(
                id=need_id, category_id=self.category_id, status=NeedStatus.HELP_ON_THE_WAY
            )

        self._render(create_commitment)

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        self.assertEqual(calls, [(self.needs_help_id, "Ana", None)])

    def test_confirm_calls_handler_with_stripped_name_and_note_when_both_provided(
        self,
    ) -> None:
        calls = []

        def create_commitment(need_id, name, note):
            calls.append((need_id, name, note))
            return Need(
                id=need_id, category_id=self.category_id, status=NeedStatus.HELP_ON_THE_WAY
            )

        self._render(create_commitment)

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        note_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "textarea" and element.args == ("Nota (opcional)",)
        )
        name_input.value = "  Ana  "
        note_input.value = "Voy para allá."
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        self.assertEqual(calls, [(self.needs_help_id, "Ana", "Voy para allá.")])

    def test_confirm_without_a_name_shows_negative_notice_and_never_calls_handler(
        self,
    ) -> None:
        calls = []

        def create_commitment(*args):
            calls.append(args)
            return object()

        self._render(create_commitment)

        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        self.assertEqual(calls, [])
        notifications = [
            element
            for element in self.fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].kwargs.get("type"), "negative")

    def test_confirm_success_shows_exact_thanks_message(self) -> None:
        self._render(
            lambda need_id, *_args: Need(
                id=need_id, category_id=self.category_id, status=NeedStatus.HELP_ON_THE_WAY
            )
        )

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn(
            "Gracias. Las personas que coordinan este punto podrán ver "
            "que hay ayuda en camino.",
            labels,
        )

    def test_confirm_failure_shows_generic_negative_notice_without_exposing_error(
        self,
    ) -> None:
        def create_commitment(*_args):
            raise ValueError("need is covered")

        self._render(create_commitment)

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        notifications = [
            element
            for element in self.fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].kwargs.get("type"), "negative")
        self.assertNotIn("covered", str(notifications[0].args).lower())
        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertFalse(any(label.startswith("Gracias.") for label in labels))

    def test_dialog_and_thanks_message_survive_the_status_row_refresh(self) -> None:
        """Regression: confirming must not erase the dialog it lives in."""
        self._render(
            lambda need_id, *_args: Need(
                id=need_id,
                category_id=self.category_id,
                status=NeedStatus.HELP_ON_THE_WAY,
            )
        )

        dialog = next(
            element for element in self.fake_ui.elements if element.kind == "dialog"
        )
        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        self.assertIn(dialog, self.fake_ui.elements)
        dialog_descendants = list(_descendants(dialog))
        thanks_labels = [
            element
            for element in dialog_descendants
            if element.kind == "label"
            and element.args
            and element.args[0].startswith("Gracias.")
        ]
        self.assertEqual(len(thanks_labels), 1)
        close_buttons = [
            element
            for element in dialog_descendants
            if element.kind == "button" and element.args == ("Cerrar",)
        ]
        self.assertEqual(len(close_buttons), 1)

    def test_status_row_updates_color_and_text_after_confirming_without_reload(
        self,
    ) -> None:
        def status_boxes():
            return [
                element
                for element in self.fake_ui.elements
                if element.kind in ("row", "column")
                and "border-l-4" in element.classes_value
            ]

        self._render(
            lambda need_id, *_args: Need(
                id=need_id,
                category_id=self.category_id,
                status=NeedStatus.HELP_ON_THE_WAY,
            )
        )

        labels_before = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertEqual(labels_before.count("Se necesita"), 1)
        self.assertEqual(labels_before.count("En camino"), 1)
        self.assertEqual(labels_before.count("Agua"), 2)
        self.assertEqual(sum("red" in box.classes_value for box in status_boxes()), 1)

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        labels_after = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertEqual(labels_after.count("Se necesita"), 0)
        self.assertEqual(labels_after.count("En camino"), 2)
        self.assertEqual(sum("red" in box.classes_value for box in status_boxes()), 0)
        self.assertEqual(
            sum("amber" in box.classes_value for box in status_boxes()), 2
        )

    def test_zero_active_commitment_count_shows_no_counter_label(self) -> None:
        self._render(lambda *_args: object())

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertFalse(
            any(
                "confirmó ayuda" in label or "confirmaron ayuda" in label
                for label in labels
            )
        )

    def test_singular_commitment_count_label(self) -> None:
        self._render(
            lambda need_id, *_args: Need(
                id=need_id,
                category_id=self.category_id,
                status=NeedStatus.HELP_ON_THE_WAY,
                active_commitment_count=1,
            )
        )

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("1 persona confirmó ayuda", labels)

    def test_plural_commitment_count_label(self) -> None:
        self._render(
            lambda need_id, *_args: Need(
                id=need_id,
                category_id=self.category_id,
                status=NeedStatus.HELP_ON_THE_WAY,
                active_commitment_count=3,
            )
        )

        name_input = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre",)
        )
        name_input.value = "Ana"
        confirm_button = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Confirmar",)
        )
        confirm_button.kwargs["on_click"]()

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("3 personas confirmaron ayuda", labels)


if __name__ == "__main__":
    unittest.main()
