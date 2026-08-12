from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from backend.domain.models import Commitment, HelpPoint, Need, NeedStatus
from frontend.pages import manage_help_point
from frontend.pages.manage_help_point import (
    add_need_to_point,
    change_need_state,
    deactivate_point,
    remove_need_from_point,
    update_point_info,
)


class RecordingElement:
    def __init__(self, ui, kind, *args, **kwargs):
        self.ui = ui
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.value = kwargs.get("value")
        self.classes_value = ""
        self.props_value = ""
        self.children = []
    def __enter__(self): self.ui.context.append(self); return self
    def __exit__(self, *_args): self.ui.context.pop(); return False
    def classes(self, value): self.classes_value = value; return self
    def props(self, value): self.props_value = value; return self
    def clear(self):
        removed = set(descendants(self))
        self.ui.elements[:] = [
            element for element in self.ui.elements if element not in removed
        ]
        self.children.clear()


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
    def __init__(self):
        self.elements = []
        self.context = []
    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(self, kind, *args, **kwargs)
        self.elements.append(element)
        if self.context:
            self.context[-1].children.append(element)
        return element
    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def row(self, *args, **kwargs): return self._record("row", *args, **kwargs)
    def card(self, *args, **kwargs): return self._record("card", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def link(self, *args, **kwargs): return self._record("link", *args, **kwargs)
    def textarea(self, *args, **kwargs): return self._record("textarea", *args, **kwargs)
    def input(self, *args, **kwargs): return self._record("input", *args, **kwargs)
    def select(self, *args, **kwargs): return self._record("select", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def notify(self, *args, **kwargs): return self._record("notify", *args, **kwargs)
    def dialog(self, *args, **kwargs):
        element = RecordingDialog(self, *args, **kwargs)
        self.elements.append(element)
        if self.context:
            self.context[-1].children.append(element)
        return element


def descendants(element):
    for child in element.children:
        yield child
        yield from descendants(child)


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

    def test_update_info_delegates_name_description_contact_areas_and_token(self) -> None:
        calls = []

        def update_info(point, token, name, description, contact, additional_areas):
            calls.append((point, token, name, description, contact, additional_areas))
            return point

        updated = update_point_info(
            self.point,
            self.token,
            "Nuevo nombre",
            "Nueva descripción",
            "Nuevo contacto",
            "Roldanillo y Zarzal",
            update_info,
        )

        self.assertIs(updated, self.point)
        self.assertEqual(
            calls,
            [
                (
                    self.point,
                    self.token,
                    "Nuevo nombre",
                    "Nueva descripción",
                    "Nuevo contacto",
                    "Roldanillo y Zarzal",
                )
            ],
        )

    def test_update_info_delegates_none_additional_areas_when_absent(self) -> None:
        calls = []

        def update_info(point, token, name, description, contact, additional_areas):
            calls.append((point, token, name, description, contact, additional_areas))
            return point

        updated = update_point_info(
            self.point,
            self.token,
            "Nuevo nombre",
            "Nueva descripción",
            "Nuevo contacto",
            None,
            update_info,
        )

        self.assertIs(updated, self.point)
        self.assertEqual(
            calls,
            [(self.point, self.token, "Nuevo nombre", "Nueva descripción", "Nuevo contacto", None)],
        )


class ManageHelpPointInfoEditingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "private-token"
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
            needs=(),
            additional_affected_areas="Zarzal",
        )
        self.fake_ui = RecordingUi()
        self.original_ui = manage_help_point.ui
        manage_help_point.ui = self.fake_ui
        self.addCleanup(setattr, manage_help_point, "ui", self.original_ui)

    def _additional_areas_field(self):
        return next(
            element
            for element in self.fake_ui.elements
            if element.kind == "textarea"
            and element.args
            == ("¿Hay otras zonas que también recibirán ayuda? (opcional)",)
        )

    def _save_button(self):
        return next(
            element
            for element in self.fake_ui.elements
            if element.kind == "button" and element.args == ("Guardar información",)
        )

    def test_additional_areas_field_preloads_current_point_value(self) -> None:
        manage_help_point.render_manage_help_point(
            self.point,
            self.token,
            {},
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
        )

        self.assertEqual(self._additional_areas_field().value, "Zarzal")

    def test_name_field_preloads_current_value_and_enforces_max_length(self) -> None:
        manage_help_point.render_manage_help_point(
            self.point,
            self.token,
            {},
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
        )

        name_field = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "input" and element.args == ("Nombre del punto",)
        )
        self.assertEqual(name_field.value, "Parque Central")
        self.assertIn("maxlength=120", name_field.props_value)

    def test_description_field_enforces_generous_max_length(self) -> None:
        manage_help_point.render_manage_help_point(
            self.point,
            self.token,
            {},
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
        )

        description_field = next(
            element
            for element in self.fake_ui.elements
            if element.kind == "textarea"
            and element.args == ("¿Qué está pasando en este punto?",)
        )
        self.assertIn("maxlength=5000", description_field.props_value)

    def test_additional_areas_field_preloads_empty_string_when_point_has_none(
        self,
    ) -> None:
        point_without_extra_areas = HelpPoint(
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
            coordinator_name=self.point.coordinator_name,
            coordinator_contact=self.point.coordinator_contact,
            admin_token=self.point.admin_token,
            active=self.point.active,
            needs=self.point.needs,
        )

        manage_help_point.render_manage_help_point(
            point_without_extra_areas,
            self.token,
            {},
            lambda *_args: point_without_extra_areas,
            lambda *_args: point_without_extra_areas,
            lambda *_args: point_without_extra_areas,
            lambda *_args: point_without_extra_areas,
            lambda *_args: point_without_extra_areas,
        )

        self.assertEqual(self._additional_areas_field().value, "")

    def test_saving_sends_edited_additional_areas_value_to_backend_handler(self) -> None:
        calls = []

        def update_info(point, token, name, description, contact, additional_areas):
            calls.append((point, token, name, description, contact, additional_areas))
            return point

        manage_help_point.render_manage_help_point(
            self.point,
            self.token,
            {},
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            update_info,
        )

        self._additional_areas_field().value = "Roldanillo y Zarzal"
        self._save_button().kwargs["on_click"]()

        self.assertEqual(
            calls,
            [
                (
                    self.point,
                    self.token,
                    self.point.name,
                    self.point.description,
                    self.point.coordinator_contact,
                    "Roldanillo y Zarzal",
                )
            ],
        )

    def test_saving_with_blank_additional_areas_sends_none_to_backend_handler(
        self,
    ) -> None:
        calls = []

        def update_info(point, token, name, description, contact, additional_areas):
            calls.append((point, token, name, description, contact, additional_areas))
            return point

        manage_help_point.render_manage_help_point(
            self.point,
            self.token,
            {},
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            lambda *_args: self.point,
            update_info,
        )

        self._additional_areas_field().value = ""
        self._save_button().kwargs["on_click"]()

        self.assertIsNone(calls[0][-1])


class ManageHelpPointResponsivePresentationTests(unittest.TestCase):
    def test_category_name_resolves_known_id_and_falls_back(self) -> None:
        water_id = uuid4()
        self.assertEqual(manage_help_point.category_name({"Agua": water_id}, water_id), "Agua")
        self.assertEqual(manage_help_point.category_name({}, water_id), "Necesidad")

    def test_status_options_use_public_spanish_labels(self) -> None:
        self.assertEqual(
            manage_help_point.status_options(),
            {
                "Se necesita": NeedStatus.NEEDS_HELP,
                "Hay ayuda en camino — todavía se necesita": NeedStatus.HELP_ON_THE_WAY,
                "Cubierto — no enviar más": NeedStatus.COVERED,
            },
        )

    def test_renders_named_sections_action_palette_complete_statuses_and_menus(self) -> None:
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
                NeedStatus.HELP_ON_THE_WAY: "Hay ayuda en camino — todavía se necesita",
                NeedStatus.COVERED: "Cubierto — no enviar más",
            },
        )
        self.assertEqual(selector.kwargs["value"], NeedStatus.NEEDS_HELP)
        labels = [element.args[0] for element in fake_ui.elements if element.kind == "label"]
        self.assertIn("Parque", labels)
        self.assertTrue(
            any(
                element.kind == "link" and element.args == ("Volver al inicio", "/")
                for element in fake_ui.elements
            )
        )
        for section in (
            "Información pública",
            "Necesidades",
            "Agregar necesidad",
            "Zona de peligro",
        ):
            self.assertIn(section, labels)
        self.assertIn("Agua", labels)
        self.assertIn("Se necesita", labels)
        self.assertIn(
            "Quien confirma ayuda solo activa el estado amarillo. "
            "Solo quien tenga este enlace de administración puede "
            "marcar una necesidad como cubierto.",
            labels,
        )
        buttons = {
            element.args[0]: element
            for element in fake_ui.elements
            if element.kind == "button"
        }
        for text in (
            "Guardar información",
            "Guardar estado",
            "Agregar necesidad",
            "Quitar",
            "Desactivar punto",
        ):
            self.assertIn("min-h-[44px]", buttons[text].classes_value)
        for text in ("Guardar información", "Guardar estado"):
            self.assertIn("unelevated", buttons[text].props_value)
            self.assertIn("color=primary", buttons[text].props_value)
            self.assertNotIn("color=green-9", buttons[text].props_value)
        self.assertIn("unelevated", buttons["Agregar necesidad"].props_value)
        self.assertIn("color=primary", buttons["Agregar necesidad"].props_value)
        self.assertNotIn("color=green-9", buttons["Agregar necesidad"].props_value)
        self.assertIn("unelevated", buttons["Quitar"].props_value)
        self.assertIn("color=red-9", buttons["Quitar"].props_value)

        category_selector = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs.get("label") == "Agregar necesidad"
        )
        for current_selector in (selector, category_selector):
            self.assertIn("behavior=menu", current_selector.props_value)
            self.assertNotIn("options-dense", current_selector.props_value)
        self.assertIn(
            'popup-content-style="max-height: 40vh !important; overflow-y: auto"',
            category_selector.props_value,
        )
        self.assertIn(
            "popup-content-class=bounded-select-menu",
            category_selector.props_value,
        )
        self.assertNotIn(
            "popup-content-class=bounded-select-menu",
            selector.props_value,
        )

    def test_remove_and_deactivate_require_explicit_confirmation_without_token_copy(self) -> None:
        category_id, need_id = uuid4(), uuid4()
        token = "synthetic-private-token"
        point = HelpPoint(id=uuid4(), name="Parque", description="Apoyo", city="Cali", department="Valle", address="Calle 5", affected_city="Roldanillo", affected_department="Valle del Cauca", latitude=3.0, longitude=-76.0, coordinator_name="Ana", coordinator_contact="Contacto", admin_token=token, active=True, needs=(Need(id=need_id, category_id=category_id, status=NeedStatus.NEEDS_HELP),))
        remove_calls, deactivate_calls = [], []
        fake_ui = RecordingUi()
        original_ui = manage_help_point.ui
        manage_help_point.ui = fake_ui
        try:
            manage_help_point.render_manage_help_point(
                point,
                token,
                {"Agua": category_id},
                lambda *_args: point,
                lambda *args: remove_calls.append(args) or point,
                lambda *_args: point,
                lambda *args: deactivate_calls.append(args) or point,
                lambda *_args: point,
            )
            remove_launch = next(
                element
                for element in fake_ui.elements
                if element.kind == "button" and element.args == ("Quitar",)
            )
            deactivate_launch = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Desactivar punto",)
            )
            dialogs = [
                element for element in fake_ui.elements if element.kind == "dialog"
            ]
            self.assertEqual(len(dialogs), 2)
            remove_dialog, deactivate_dialog = dialogs

            remove_launch.kwargs["on_click"]()
            self.assertTrue(remove_dialog.opened)
            self.assertEqual(remove_calls, [])
            remove_cancel = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Cancelar",)
                and element in tuple(descendants(remove_dialog))
            )
            remove_cancel.kwargs["on_click"]()
            self.assertFalse(remove_dialog.opened)
            self.assertEqual(remove_calls, [])

            remove_launch.kwargs["on_click"]()
            remove_confirm = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Sí, quitar necesidad",)
            )
            remove_confirm.kwargs["on_click"]()
            self.assertEqual(remove_calls, [(point, token, need_id)])
            self.assertFalse(remove_dialog.opened)

            deactivate_launch = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Desactivar punto",)
            )
            current_dialogs = [
                element for element in fake_ui.elements if element.kind == "dialog"
            ]
            self.assertEqual(len(current_dialogs), 2)
            deactivate_dialog = current_dialogs[1]
            deactivate_launch.kwargs["on_click"]()
            self.assertTrue(deactivate_dialog.opened)
            self.assertEqual(deactivate_calls, [])
            deactivate_cancel = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Cancelar",)
                and element in tuple(descendants(deactivate_dialog))
            )
            deactivate_cancel.kwargs["on_click"]()
            self.assertEqual(deactivate_calls, [])

            deactivate_launch.kwargs["on_click"]()
            deactivate_confirm = next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Sí, desactivar punto",)
            )
            deactivate_confirm.kwargs["on_click"]()
        finally:
            manage_help_point.ui = original_ui

        self.assertEqual(deactivate_calls, [(point, token)])
        self.assertFalse(deactivate_dialog.opened)
        self.assertIn("unelevated", deactivate_confirm.props_value)
        self.assertIn("color=red-9", deactivate_confirm.props_value)
        visible_elements = [
            (
                element.kind,
                element.args,
                element.kwargs,
                element.classes_value,
                element.props_value,
            )
            for element in fake_ui.elements
        ]
        self.assertNotIn(token, repr(visible_elements))

    def test_handler_error_notification_is_generic_and_omits_token(self) -> None:
        token = "synthetic-private-token"
        point = HelpPoint(id=uuid4(), name="Parque", description="Apoyo", city="Cali", department="Valle", address="Calle 5", affected_city="Roldanillo", affected_department="Valle del Cauca", latitude=3.0, longitude=-76.0, coordinator_name="Ana", coordinator_contact="Contacto", admin_token=token, active=True, needs=())
        fake_ui = RecordingUi()
        original_ui = manage_help_point.ui
        manage_help_point.ui = fake_ui
        try:
            manage_help_point.render_manage_help_point(
                point,
                token,
                {},
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: (_ for _ in ()).throw(
                    PermissionError(f"invalid token {token}")
                ),
            )
            next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Guardar información",)
            ).kwargs["on_click"]()
        finally:
            manage_help_point.ui = original_ui

        notifications = [
            element.args[0]
            for element in fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(
            notifications,
            ["No fue posible actualizar el punto. Inténtalo de nuevo."],
        )
        self.assertNotIn(token, repr(notifications))

    def test_unexpected_handler_error_is_generic_and_does_not_propagate(self) -> None:
        token = "synthetic-private-token"
        point = HelpPoint(id=uuid4(), name="Parque", description="Apoyo", city="Cali", department="Valle", address="Calle 5", affected_city="Roldanillo", affected_department="Valle del Cauca", latitude=3.0, longitude=-76.0, coordinator_name="Ana", coordinator_contact="Contacto", admin_token=token, active=True, needs=())
        caught_errors = []
        fake_ui = RecordingUi()
        original_ui = manage_help_point.ui
        manage_help_point.ui = fake_ui
        try:
            manage_help_point.render_manage_help_point(
                point,
                token,
                {},
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: point,
                lambda *_args: (_ for _ in ()).throw(
                    RuntimeError(f"database unavailable {token}")
                ),
            )
            try:
                next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Guardar información",)
                ).kwargs["on_click"]()
            except RuntimeError as error:
                caught_errors.append(error)
        finally:
            manage_help_point.ui = original_ui

        self.assertEqual(caught_errors, [])
        notifications = [
            element.args[0]
            for element in fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(
            notifications,
            ["No fue posible actualizar el punto. Inténtalo de nuevo."],
        )
        self.assertNotIn(token, repr(notifications))
        self.assertNotIn("database unavailable", repr(notifications))


class ManageHelpPointCommitmentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_ui = RecordingUi()
        self.original_ui = manage_help_point.ui
        manage_help_point.ui = self.fake_ui
        self.addCleanup(setattr, manage_help_point, "ui", self.original_ui)

    def _render(self, point: HelpPoint) -> None:
        manage_help_point.render_manage_help_point(
            point,
            "private-token",
            {},
            lambda *_args: point,
            lambda *_args: point,
            lambda *_args: point,
            lambda *_args: point,
            lambda *_args: point,
        )

    def test_commitments_are_listed_with_name_and_note_when_present(self) -> None:
        need_id = uuid4()
        commitments = (
            Commitment(
                id=uuid4(),
                need_id=need_id,
                name="Ana",
                note="Voy para allá.",
                active=True,
                created_at=datetime(2026, 8, 11, tzinfo=UTC),
            ),
            Commitment(
                id=uuid4(),
                need_id=need_id,
                name="Luis",
                note=None,
                active=True,
                created_at=datetime(2026, 8, 11, tzinfo=UTC),
            ),
        )
        need = Need(
            id=need_id,
            category_id=uuid4(),
            status=NeedStatus.NEEDS_HELP,
            commitments=commitments,
        )
        point = HelpPoint(
            id=uuid4(),
            name="Parque",
            description="Apoyo",
            city="Cali",
            department="Valle",
            address="Calle 5",
            affected_city="Roldanillo",
            affected_department="Valle del Cauca",
            latitude=3.0,
            longitude=-76.0,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            admin_token="private-token",
            active=True,
            needs=(need,),
        )

        self._render(point)

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Confirmaron ayuda:", labels)
        self.assertIn("• Ana — Voy para allá.", labels)
        self.assertIn("• Luis", labels)

    def test_no_commitment_list_rendered_when_need_has_no_commitments(self) -> None:
        need = Need(
            id=uuid4(), category_id=uuid4(), status=NeedStatus.NEEDS_HELP
        )
        point = HelpPoint(
            id=uuid4(),
            name="Parque",
            description="Apoyo",
            city="Cali",
            department="Valle",
            address="Calle 5",
            affected_city="Roldanillo",
            affected_department="Valle del Cauca",
            latitude=3.0,
            longitude=-76.0,
            coordinator_name="Ana",
            coordinator_contact="Contacto",
            admin_token="private-token",
            active=True,
            needs=(need,),
        )

        self._render(point)

        labels = [
            element.args[0]
            for element in self.fake_ui.elements
            if element.kind == "label"
        ]
        self.assertFalse(any(label.startswith("•") for label in labels))


if __name__ == "__main__":
    unittest.main()
