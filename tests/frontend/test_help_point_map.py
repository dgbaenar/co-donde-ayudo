from __future__ import annotations

import unittest
from uuid import uuid4

from backend.domain.models import Need, NeedStatus, PublicHelpPoint
from frontend.components import help_point_map


class RecordingElement:
    def __init__(self) -> None:
        self.classes_value = ""

    def classes(self, value):
        self.classes_value = value
        return self


class RecordingMarker:
    def __init__(self, latlng) -> None:
        self.latlng = latlng
        self.method_calls = []

    def run_method(self, name, *args):
        self.method_calls.append((name, args))


class RecordingLeaflet(RecordingElement):
    def __init__(self, center, zoom) -> None:
        super().__init__()
        self.center = center
        self.zoom = zoom
        self.markers = []
        self.handlers = {}

    def on(self, event_name, handler):
        self.handlers[event_name] = handler
        return self

    def marker(self, *, latlng):
        marker = RecordingMarker(latlng)
        self.markers.append(marker)
        return marker


class RecordingUi:
    def __init__(self) -> None:
        self.maps = []

    def leaflet(self, *, center, zoom):
        map_element = RecordingLeaflet(center, zoom)
        self.maps.append(map_element)
        return map_element


class HelpPointMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.category_id = uuid4()

    def point(self, *, active=True, name="Parque Central") -> PublicHelpPoint:
        return PublicHelpPoint(
            id=uuid4(),
            name=name,
            description="Se requiere apoyo.",
            city="Cali & alrededores",
            department="Valle <del> Cauca",
            address="Calle 5 <principal>",
            affected_city="Roldanillo & norte",
            affected_department="Valle <afectado> Cauca",
            latitude=3.4516,
            longitude=-76.5320,
            active=active,
            needs=(
                Need(
                    id=uuid4(),
                    category_id=self.category_id,
                    status=NeedStatus.NEEDS_HELP,
                ),
            ),
        )

    def test_popup_escapes_all_dynamic_text_and_links_to_public_detail(self) -> None:
        point = self.point(name='<script>alert("x")</script>')

        popup = help_point_map.build_popup_html(
            point,
            {"<b>Agua</b>": self.category_id},
        )

        self.assertNotIn("<script>", popup)
        self.assertNotIn("<b>Agua</b>", popup)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", popup)
        self.assertIn("Cali &amp; alrededores", popup)
        self.assertIn("Valle &lt;del&gt; Cauca", popup)
        self.assertIn("Calle 5 &lt;principal&gt;", popup)
        self.assertIn("Roldanillo &amp; norte", popup)
        self.assertIn("Valle &lt;afectado&gt; Cauca", popup)
        self.assertIn("Ayuda destinada a:", popup)
        self.assertIn("Recibe ayuda en:", popup)
        self.assertNotIn("Ayuda para:", popup)
        self.assertNotIn("Punto de recepción:", popup)
        self.assertIn("&lt;b&gt;Agua&lt;/b&gt;", popup)
        self.assertIn("🔴 Se necesita", popup)
        self.assertIn(f'href="/puntos/{point.id}"', popup)

    def test_renders_colombia_map_with_one_popup_marker_per_active_point(self) -> None:
        fake_ui = RecordingUi()
        original_ui = help_point_map.ui
        help_point_map.ui = fake_ui
        active = self.point()
        inactive = self.point(active=False, name="Punto cerrado")
        try:
            map_element = help_point_map.render_help_point_map(
                (active, inactive),
                {"Agua": self.category_id},
            )
        finally:
            help_point_map.ui = original_ui

        self.assertEqual(map_element.center, (4.5709, -74.2973))
        self.assertEqual(map_element.zoom, 5)
        self.assertIn("w-full", map_element.classes_value)
        self.assertTrue(any(height in map_element.classes_value for height in ("h-80", "h-[")))
        self.assertIn("rounded-2xl", map_element.classes_value)
        self.assertIn("shadow-sm", map_element.classes_value)
        self.assertEqual([marker.latlng for marker in map_element.markers], [(3.4516, -76.532)])
        self.assertEqual(map_element.markers[0].method_calls, [])
        map_element.handlers["init"]()
        self.assertEqual(map_element.markers[0].method_calls[0][0], "bindPopup")


if __name__ == "__main__":
    unittest.main()
