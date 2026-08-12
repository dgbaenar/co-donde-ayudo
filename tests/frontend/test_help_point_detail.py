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

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def classes(self, value): self.classes_value = value; return self


class RecordingUi:
    def __init__(self) -> None:
        self.elements = []

    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(kind, *args, **kwargs)
        self.elements.append(element)
        return element

    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)


class HelpPointDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.category_id = uuid4()
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
            needs=(Need(id=uuid4(), category_id=self.category_id, status=NeedStatus.NEEDS_HELP),),
        )
        self.fake_ui = RecordingUi()
        self.ui_patch = patch.object(help_point_detail, "ui", self.fake_ui)
        self.ui_patch.start()
        self.addCleanup(self.ui_patch.stop)

    def test_valid_uuid_loads_and_renders_public_detail_with_point_map(self) -> None:
        requested_ids = []

        with patch.object(help_point_detail, "render_help_point_map") as render_map:
            help_point_detail.render_help_point_detail_for_path(
                str(self.point.id),
                lambda point_id: requested_ids.append(point_id) or self.point,
                {"Agua": self.category_id},
            )

        self.assertEqual(requested_ids, [self.point.id])
        labels = [element.args[0] for element in self.fake_ui.elements if element.kind == "label"]
        self.assertIn("Parque Central", labels)
        self.assertIn("Ayuda destinada a: Roldanillo, Valle del Cauca", labels)
        self.assertIn(
            "Recibe ayuda en: Calle 5 # 10-20, Cali, Valle del Cauca",
            labels,
        )
        self.assertIn("Familias evacuadas reciben apoyo.", labels)
        self.assertIn("🔴 Se necesita Agua", labels)
        self.assertFalse(any("coordinator" in str(label).lower() or "token" in str(label).lower() for label in labels))
        render_map.assert_called_once_with(
            (self.point,),
            {"Agua": self.category_id},
            center=(3.4516, -76.532),
            zoom=15,
        )

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
