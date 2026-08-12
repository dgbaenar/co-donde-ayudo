from __future__ import annotations

from types import SimpleNamespace
import unittest

from frontend.components import location_picker


class RecordingElement:
    def __init__(self, kind, *args, **kwargs) -> None:
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.classes_value = ""

    def classes(self, value):
        self.classes_value = value
        return self


class RecordingMarker:
    def __init__(self, latlng) -> None:
        self.latlng = latlng
        self.moves = []

    def move(self, lat, lng) -> None:
        self.latlng = (lat, lng)
        self.moves.append((lat, lng))


class RecordingLeaflet(RecordingElement):
    def __init__(self, center, zoom) -> None:
        super().__init__("leaflet")
        self.center = center
        self.zoom = zoom
        self.handlers = {}
        self.markers = []
        self.map_method_calls = []

    def on(self, event_name, handler):
        self.handlers[event_name] = handler
        return self

    def marker(self, *, latlng):
        marker = RecordingMarker(latlng)
        self.markers.append(marker)
        return marker

    def run_map_method(self, name, *args):
        self.map_method_calls.append((name, args))


class RecordingUi:
    def __init__(self) -> None:
        self.elements = []
        self.map = None

    def label(self, *args, **kwargs):
        element = RecordingElement("label", *args, **kwargs)
        self.elements.append(element)
        return element

    def notify(self, *args, **kwargs):
        element = RecordingElement("notify", *args, **kwargs)
        self.elements.append(element)
        return element

    def leaflet(self, *, center, zoom):
        self.map = RecordingLeaflet(center, zoom)
        return self.map


class LocationPickerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_ui = RecordingUi()
        self.original_ui = location_picker.ui
        location_picker.ui = self.fake_ui
        self.addCleanup(setattr, location_picker, "ui", self.original_ui)

    def test_click_stores_float_coordinates_and_moves_one_marker(self) -> None:
        selection = location_picker.render_location_picker()
        click = self.fake_ui.map.handlers["map-click"]

        click(SimpleNamespace(args={"latlng": {"lat": "4.61", "lng": "-74.08"}}))
        first_marker = self.fake_ui.map.markers[0]
        click(SimpleNamespace(args={"latlng": {"lat": 3.45, "lng": -76.53}}))

        self.assertEqual((selection.latitude, selection.longitude), (3.45, -76.53))
        self.assertEqual(len(self.fake_ui.map.markers), 1)
        self.assertEqual(first_marker.moves, [(3.45, -76.53)])
        self.assertEqual(self.fake_ui.map.center, (4.5709, -74.2973))
        self.assertEqual(self.fake_ui.map.zoom, 5)
        self.assertIn("w-full", self.fake_ui.map.classes_value)
        self.assertTrue(
            any(
                element.kind == "label"
                and element.args == ("Toca el mapa para marcar la ubicación",)
                for element in self.fake_ui.elements
            )
        )

    def test_set_coordinates_updates_state_single_marker_and_local_map_view(self) -> None:
        selection = location_picker.render_location_picker()

        selection.set_coordinates(4.711, -74.072)
        marker = self.fake_ui.map.markers[0]
        selection.set_coordinates(3.4516, -76.532)

        self.assertEqual((selection.latitude, selection.longitude), (3.4516, -76.532))
        self.assertEqual(len(self.fake_ui.map.markers), 1)
        self.assertEqual(marker.moves, [(3.4516, -76.532)])
        self.assertEqual(
            self.fake_ui.map.map_method_calls,
            [
                ("setView", ([4.711, -74.072], 15)),
                ("setView", ([3.4516, -76.532], 15)),
            ],
        )

    def test_set_coordinates_rejects_out_of_range_values_without_mutating_state(self) -> None:
        selection = location_picker.render_location_picker()

        with self.assertRaisesRegex(ValueError, "coordinates out of range"):
            selection.set_coordinates(91, -74.0)

        self.assertIsNone(selection.latitude)
        self.assertIsNone(selection.longitude)
        self.assertEqual(self.fake_ui.map.markers, [])

    def test_malformed_click_is_rejected_without_changing_selection(self) -> None:
        selection = location_picker.render_location_picker()

        self.fake_ui.map.handlers["map-click"](SimpleNamespace(args={"latlng": {"lat": "x"}}))

        self.assertIsNone(selection.latitude)
        self.assertIsNone(selection.longitude)
        self.assertEqual(self.fake_ui.map.markers, [])
        self.assertTrue(any(element.kind == "notify" for element in self.fake_ui.elements))


if __name__ == "__main__":
    unittest.main()
