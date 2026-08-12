from __future__ import annotations

import unittest
from uuid import uuid4

from backend.domain.models import HelpPoint, Need, NeedStatus
from frontend.pages import manage_help_point
from frontend.pages.manage_help_point import (
    add_need_to_point,
    change_need_state,
    deactivate_point,
    remove_need_from_point,
    update_point_info,
)


class RecordingElement:
    def __init__(self, kind, *args, **kwargs):
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.value = kwargs.get("value")
        self.classes_value = ""
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def classes(self, value): self.classes_value = value; return self
    def clear(self): return None


class RecordingUi:
    def __init__(self): self.elements = []
    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(kind, *args, **kwargs)
        self.elements.append(element)
        return element
    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def row(self, *args, **kwargs): return self._record("row", *args, **kwargs)
    def card(self, *args, **kwargs): return self._record("card", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def textarea(self, *args, **kwargs): return self._record("textarea", *args, **kwargs)
    def input(self, *args, **kwargs): return self._record("input", *args, **kwargs)
    def select(self, *args, **kwargs): return self._record("select", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def notify(self, *args, **kwargs): return self._record("notify", *args, **kwargs)


class ManageHelpPointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "private-token"
        self.need = Need(id=uuid4(), category_id=uuid4(), status=NeedStatus.NEEDS_HELP)
        self.point = HelpPoint(
            id=uuid4(),
            name="Parque Central",
            description="Familias evacuadas reciben apoyo.",
            city="Cali",
            department="Valle del Cauca",
            address="Calle 5 # 10-20",
            affected_city="Roldanillo",
            affected_department="Valle del Cauca",
            latitude=3.4516,
            longitude=-76.5320,
            coordinator_name="Ana",
            coordinator_contact="Contacto local",
            admin_token=self.token,
            active=True,
            needs=(self.need,),
        )

    def test_add_need_delegates_token_and_catalog_category_id(self) -> None:
        category_id = uuid4()
        calls = []

        def add_need(point, token, category):
            calls.append((point, token, category))
            return point

        updated = add_need_to_point(
            self.point,
            self.token,
            "Agua",
            {"Agua": category_id},
            add_need,
        )

        self.assertIs(updated, self.point)
        self.assertEqual(calls, [(self.point, self.token, category_id)])

    def test_add_need_rejects_category_absent_from_catalog(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown category"):
            add_need_to_point(self.point, self.token, "No existe", {}, lambda *_: self.point)

    def test_remove_need_delegates_token_and_need_id(self) -> None:
        calls = []

        def remove_need(point, token, need_id):
            calls.append((point, token, need_id))
            return point

        updated = remove_need_from_point(self.point, self.token, self.need.id, remove_need)

        self.assertIs(updated, self.point)
        self.assertEqual(calls, [(self.point, self.token, self.need.id)])

    def test_change_need_state_delegates_each_supported_status(self) -> None:
        calls = []

        def change_status(point, token, need_id, status):
            calls.append((point, token, need_id, status))
            return point

        for status in NeedStatus:
            self.assertIs(
                change_need_state(self.point, self.token, self.need.id, status, change_status),
                self.point,
            )

        self.assertEqual(
            calls,
            [(self.point, self.token, self.need.id, status) for status in NeedStatus],
        )

    def test_deactivate_delegates_token(self) -> None:
        calls = []

        def deactivate(point, token):
            calls.append((point, token))
            return point

        updated = deactivate_point(self.point, self.token, deactivate)

        self.assertIs(updated, self.point)
        self.assertEqual(calls, [(self.point, self.token)])

    def test_update_info_delegates_description_contact_and_token(self) -> None:
        calls = []

        def update_info(point, token, description, contact):
            calls.append((point, token, description, contact))
            return point

        updated = update_point_info(
            self.point,
            self.token,
            "Nueva descripción",
            "Nuevo contacto",
            update_info,
        )

        self.assertIs(updated, self.point)
        self.assertEqual(
            calls,
            [(self.point, self.token, "Nueva descripción", "Nuevo contacto")],
        )


class ManageHelpPointResponsivePresentationTests(unittest.TestCase):
    def test_category_name_resolves_known_id_and_falls_back(self) -> None:
        water_id = uuid4()
        self.assertEqual(manage_help_point.category_name({"Agua": water_id}, water_id), "Agua")
        self.assertEqual(manage_help_point.category_name({}, water_id), "Necesidad")

    def test_status_options_use_public_spanish_labels(self) -> None:
        self.assertEqual(manage_help_point.status_options(), {"Se necesita": NeedStatus.NEEDS_HELP, "Hay ayuda en camino": NeedStatus.HELP_ON_THE_WAY, "Cubierto": NeedStatus.COVERED})

    def test_state_selector_uses_selected_public_status_and_full_width_actions(self) -> None:
        category_id, need_id = uuid4(), uuid4()
        point = HelpPoint(id=uuid4(), name="Parque", description="Apoyo", city="Cali", department="Valle", address="Calle 5 # 10-20", affected_city="Roldanillo", affected_department="Valle del Cauca", latitude=3.0, longitude=-76.0, coordinator_name="Ana", coordinator_contact="Contacto", admin_token="private-token", active=True, needs=(Need(id=need_id, category_id=category_id, status=NeedStatus.NEEDS_HELP),))
        calls, fake_ui = [], RecordingUi()
        original_ui = manage_help_point.ui
        manage_help_point.ui = fake_ui
        try:
            manage_help_point.render_manage_help_point(point, "private-token", {"Agua": category_id}, lambda *_args: point, lambda *_args: point, lambda *_args: calls.append(_args) or point, lambda *_args: point, lambda *_args: point)
            selector = next(element for element in fake_ui.elements if element.kind == "select" and element.kwargs.get("label") == "Estado")
            selector.value = NeedStatus.COVERED
            save = next(element for element in fake_ui.elements if element.kind == "button" and element.args[0] == "Guardar estado")
            save.kwargs["on_click"]()
        finally:
            manage_help_point.ui = original_ui

        self.assertEqual(calls, [(point, "private-token", need_id, NeedStatus.COVERED)])
        self.assertEqual(
            selector.kwargs["options"],
            {
                NeedStatus.NEEDS_HELP: "Se necesita",
                NeedStatus.HELP_ON_THE_WAY: "Hay ayuda en camino",
                NeedStatus.COVERED: "Cubierto",
            },
        )
        self.assertEqual(selector.kwargs["value"], NeedStatus.NEEDS_HELP)
        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        self.assertIn("Agua", labels)
        self.assertIn("Se necesita", labels)
        for text in ("Guardar información", "Guardar estado", "Agregar necesidad", "Desactivar punto"):
            self.assertIn("w-full min-h-[44px]", next(element for element in fake_ui.elements if element.kind == "button" and element.args[0] == text).classes_value)


if __name__ == "__main__":
    unittest.main()
