"""Map-based location picker component."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nicegui import ui

from frontend.components.help_point_map import COLOMBIA_CENTER, apply_modern_basemap


@dataclass(slots=True)
class LocationSelection:
    _map_element: Any = field(repr=False)
    latitude: float | None = None
    longitude: float | None = None
    _marker: Any = field(default=None, repr=False)

    def set_coordinates(self, latitude: float, longitude: float) -> None:
        latitude = float(latitude)
        longitude = float(longitude)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("coordinates out of range")

        self.latitude = latitude
        self.longitude = longitude
        if self._marker is None:
            self._marker = self._map_element.marker(latlng=(latitude, longitude))
        else:
            self._marker.move(latitude, longitude)
        self._map_element.run_map_method("setView", [latitude, longitude], 15)


def coordinates_from_event(event) -> tuple[float, float]:
    latitude = float(event.args["latlng"]["lat"])
    longitude = float(event.args["latlng"]["lng"])
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("coordinates out of range")
    return latitude, longitude


def render_location_picker() -> LocationSelection:
    """Render a map which stores the latest clicked location."""
    ui.label("Toca el mapa para marcar la ubicación")
    map_element = ui.leaflet(center=COLOMBIA_CENTER, zoom=5).classes(
        "w-full h-80 md:h-[28rem] rounded-2xl overflow-hidden shadow-sm"
    )
    apply_modern_basemap(map_element)
    selection = LocationSelection(map_element)

    def select_location(event) -> None:
        try:
            latitude, longitude = coordinates_from_event(event)
            selection.set_coordinates(latitude, longitude)
        except (KeyError, TypeError, ValueError):
            ui.notify("No fue posible seleccionar la ubicación.", type="negative")
            return

    map_element.on("map-click", select_location)
    return selection
