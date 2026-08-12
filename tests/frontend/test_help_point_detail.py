from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from backend.domain.models import Need, NeedStatus, PublicHelpPoint
from frontend.pages import help_point_detail


class RecordingElement:
    def __init__(self, kind, *args, **kwargs) -> None:
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.classes_value = ""
        self.props_value = ""

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def classes(self, value): self.classes_value = value; return self
    def props(self, value): self.props_value = value; return self


class RecordingUi:
    def __init__(self) -> None:
        self.elements = []

    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(kind, *args, **kwargs)
        self.elements.append(element)
        return element

    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def grid(self, *args, **kwargs): return self._record("grid", *args, **kwargs)
    def row(self, *args, **kwargs): return self._record("row", *args, **kwargs)
    def link(self, *args, **kwargs): return self._record("link", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def html(self, *args, **kwargs): return self._record("html", *args, **kwargs)


class HelpPointDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.water_category_id = uuid4()
        self.food_category_id = uuid4()
        self.shelter_category_id = uuid4()
        self.point = PublicHelpPoint(
            id=uuid4(),
            name="Parque Central",
            description="Familias evacuadas reciben apoyo.",
            city="Cali",
            department="Valle del Cauca",
            address="Calle 5 # 10-20",
            affected_city="Roldanillo",
            affected_department="Valle del Cauca",
            latitude=3.4516,
            longitude=-76.532,
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

    def test_valid_uuid_renders_semantic_sections_status_rows_and_point_map(self) -> None:
        requested_ids = []

        with patch.object(help_point_detail, "render_help_point_map") as render_map:
            help_point_detail.render_help_point_detail_for_path(
                str(self.point.id),
                lambda point_id: requested_ids.append(point_id) or self.point,
                self.categories,
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
        self.assertIn("Roldanillo, Valle del Cauca", labels)
        self.assertIn("Calle 5 # 10-20, Cali, Valle del Cauca", labels)
        self.assertFalse(any(label.startswith("También:") for label in labels))
        self.assertIn("🔴 Se necesita Agua", labels)
        self.assertIn(
            "🟡 Hay ayuda en camino — todavía se necesita Alimentos",
            labels,
        )
        self.assertIn("🟢 Cubierto — no enviar más Refugio", labels)
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
            if element.kind == "row" and "border" in element.classes_value
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
        point_with_extra_areas = PublicHelpPoint(
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            city=self.point.city,
            department=self.point.department,
            address=self.point.address,
            affected_city=self.point.affected_city,
            affected_department=self.point.affected_department,
            latitude=self.point.latitude,
            longitude=self.point.longitude,
            active=self.point.active,
            needs=self.point.needs,
            additional_affected_areas="Roldanillo y Zarzal",
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(point_with_extra_areas.id),
                lambda _point_id: point_with_extra_areas,
                self.categories,
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
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertFalse(any(label.startswith("También:") for label in labels))

    def test_affected_area_shows_whole_department_when_affected_city_is_none(
        self,
    ) -> None:
        department_wide_point = PublicHelpPoint(
            id=self.point.id,
            name=self.point.name,
            description=self.point.description,
            city=self.point.city,
            department=self.point.department,
            address=self.point.address,
            affected_city=None,
            affected_department=self.point.affected_department,
            latitude=self.point.latitude,
            longitude=self.point.longitude,
            active=self.point.active,
            needs=self.point.needs,
        )

        with patch.object(help_point_detail, "render_help_point_map"):
            help_point_detail.render_help_point_detail_for_path(
                str(department_wide_point.id),
                lambda _point_id: department_wide_point,
                self.categories,
            )

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Todo el departamento de Valle del Cauca", labels)
        self.assertFalse(any("None" in label for label in labels))

    def test_invalid_or_missing_point_shows_same_generic_message(self) -> None:
        for path_value, getter in (
            ("not-a-uuid", lambda _point_id: self.fail("invalid UUID must not reach backend")),
            (str(uuid4()), lambda _point_id: None),
        ):
            with self.subTest(path_value=path_value):
                self.fake_ui.elements.clear()
                with patch.object(help_point_detail, "render_help_point_map") as render_map:
                    help_point_detail.render_help_point_detail_for_path(path_value, getter, {})

                labels = [
                    element.args[0]
                    for element in self.fake_ui.elements
                    if element.kind == "label"
                ]
                self.assertEqual(labels, ["No fue posible encontrar este punto de ayuda."])
                render_map.assert_not_called()


if __name__ == "__main__":
    unittest.main()
