from __future__ import annotations

import ast
import asyncio
import inspect
import json
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from backend.domain.models import CreatedHelpPoint, HelpPoint
from frontend.app import create_app
from frontend.pages import create_help_point
from frontend.pages.create_help_point import (
    FormValues,
    build_command,
    publish_help_point,
)


class RecordingElement:
    def __init__(self, kind, *args, **kwargs):
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.value = kwargs.get("value")
        self.options = kwargs.get("options", args[0] if args else None)
        self.on_change = kwargs.get("on_change")
        self.classes_value = ""
        self.props_value = ""
        self.visible = True
        self.enabled = True
        self.update_calls = 0
        self.enable_calls = 0
        self.disable_calls = 0
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def classes(self, value): self.classes_value = value; return self
    def props(self, value):
        self.props_value = value
        if "disable" in value.split():
            self.enabled = False
        return self
    def enable(self): self.enable_calls += 1; self.enabled = True
    def disable(self): self.disable_calls += 1; self.enabled = False
    def update(self): self.update_calls += 1
    def clear(self): return None


class RecordingUi:
    def __init__(self):
        self.elements = []
        self.javascript_calls = []
        self.javascript_results = []
        self.navigate = type("Navigation", (), {"paths": [], "to": lambda navigation, path: navigation.paths.append(path)})()
    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(kind, *args, **kwargs)
        self.elements.append(element)
        return element
    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def input(self, *args, **kwargs): return self._record("input", *args, **kwargs)
    def textarea(self, *args, **kwargs): return self._record("textarea", *args, **kwargs)
    def select(self, *args, **kwargs): return self._record("select", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def link(self, *args, **kwargs): return self._record("link", *args, **kwargs)
    def notify(self, *args, **kwargs): return self._record("notify", *args, **kwargs)
    async def run_javascript(self, script):
        self.javascript_calls.append(script)
        return self.javascript_results.pop(0)


class RecordingHandler:
    def __init__(self) -> None:
        self.command = None
        self.token = "private-token"

    def __call__(self, command):
        self.command = command
        return CreatedHelpPoint(point=self._point(command), admin_token=self.token)

    @staticmethod
    def _point(command) -> HelpPoint:
        return HelpPoint(
            id=uuid4(),
            name=command.name,
            description=command.description,
            affected_city=command.affected_city,
            affected_department=command.affected_department,
            city=command.city,
            department=command.department,
            address=command.address,
            latitude=command.latitude,
            longitude=command.longitude,
            coordinator_name=command.coordinator_name,
            coordinator_contact=command.coordinator_contact,
            admin_token="private-token",
            active=True,
            needs=(),
        )


class CreateHelpPointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.water_id = uuid4()
        self.blanket_id = uuid4()
        self.categories = {"Agua": self.water_id, "Cobijas": self.blanket_id}
        self.values = FormValues(
            name=" Parque Central ",
            description=" Familias evacuadas reciben apoyo. ",
            affected_city=" Roldanillo ",
            affected_department=" Valle del Cauca ",
            city=" Cali ",
            department=" Valle del Cauca ",
            address=" Calle 5 # 10-20 ",
            latitude=3.4516,
            longitude=-76.5320,
            coordinator_name=" Ana ",
            coordinator_contact=" Contacto local ",
        )

    def test_build_command_uses_all_form_values_and_selected_categories(self) -> None:
        command = build_command(self.values, ("Agua", "Cobijas"), self.categories)

        self.assertEqual(command.name, "Parque Central")
        self.assertEqual(command.description, "Familias evacuadas reciben apoyo.")
        self.assertEqual(command.affected_city, "Roldanillo")
        self.assertEqual(command.affected_department, "Valle del Cauca")
        self.assertEqual(command.city, "Cali")
        self.assertEqual(command.department, "Valle del Cauca")
        self.assertEqual(command.address, "Calle 5 # 10-20")
        self.assertEqual(command.latitude, 3.4516)
        self.assertEqual(command.longitude, -76.5320)
        self.assertEqual(command.coordinator_name, "Ana")
        self.assertEqual(command.coordinator_contact, "Contacto local")
        self.assertEqual(command.category_ids, (self.water_id, self.blanket_id))

    def test_build_admin_url_uses_only_configured_origin_and_private_path(self) -> None:
        self.assertEqual(
            create_help_point.build_admin_url(
                "https://dondeayudo.example/base/?x=1#fragment",
                "/administrar/synthetic-token",
            ),
            "https://dondeayudo.example/administrar/synthetic-token",
        )

    def test_publish_calls_injected_handler_and_returns_private_admin_path(self) -> None:
        handler = RecordingHandler()

        admin_path = publish_help_point(
            self.values,
            ("Agua",),
            self.categories,
            "",
            lambda _name: self.fail("empty custom category must not be created"),
            handler,
        )

        self.assertEqual(handler.command.category_ids, (self.water_id,))
        self.assertEqual(admin_path, "/administrar/private-token")

    def test_publish_creates_custom_category_and_includes_its_id_in_command(self) -> None:
        handler = RecordingHandler()
        custom_category_id = uuid4()
        created_names = []

        admin_path = publish_help_point(
            self.values,
            ("Agua",),
            self.categories,
            " Alimento para mascotas ",
            lambda name: created_names.append(name) or custom_category_id,
            handler,
        )

        self.assertEqual(created_names, ["Alimento para mascotas"])
        self.assertEqual(handler.command.category_ids, (self.water_id, custom_category_id))
        self.assertEqual(admin_path, "/administrar/private-token")

    def test_build_command_rejects_unknown_category_before_handler_invocation(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown category"):
            build_command(self.values, ("No existe",), self.categories)

    def test_publish_without_map_location_rejects_before_any_handler(self) -> None:
        values = FormValues(
            name="Parque", description="Apoyo",
            affected_city="Roldanillo", affected_department="Valle del Cauca",
            city="Cali", department="Valle", address="Calle 5",
            latitude=None, longitude=None, coordinator_name="Ana", coordinator_contact="Local",
        )
        custom_calls = []
        create_calls = []

        with self.assertRaisesRegex(ValueError, "ubicación"):
            publish_help_point(
                values,
                (),
                {},
                "Nueva categoría",
                lambda name: custom_calls.append(name) or uuid4(),
                lambda command: create_calls.append(command) or self.fail("must not create"),
            )

        self.assertEqual(custom_calls, [])
        self.assertEqual(create_calls, [])


class FrontendBoundaryTests(unittest.TestCase):
    def test_frontend_has_no_supabase_imports(self) -> None:
        root = Path(__file__).resolve().parents[2] / "src/frontend"
        imported_modules = set()
        for source_path in root.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module)

        self.assertFalse(any(module == "supabase" or module.startswith("supabase.") for module in imported_modules))

    def test_entrypoint_defines_create_route_and_never_runs_server_at_import(self) -> None:
        entrypoint = Path(__file__).resolve().parents[2] / "src/frontend/app.py"
        source = entrypoint.read_text(encoding="utf-8")

        self.assertEqual(
            tuple(inspect.signature(create_app).parameters),
            (
                "list_public_help_points",
                "list_active_categories",
                "list_departments",
                "list_localities",
                "list_affected_departments",
                "geocode_address",
                "app_base_url",
                "create_help_point",
                "get_managed_help_point",
                "add_need",
                "remove_need",
                "change_need_status",
                "deactivate_help_point",
                "create_custom_category",
                "update_help_point_info",
                "authorize_coordinator_access",
                "get_public_help_point",
            ),
        )
        self.assertIn('@ui.page("/", title="¿Dónde ayudo?")', source)
        self.assertIn('@ui.page("/crear")', source)
        self.assertIn('@ui.page("/puntos/{point_id}")', source)
        self.assertIn('@ui.page("/administrar/{admin_token}")', source)
        self.assertIn("from frontend.pages.manage_help_point import", source)
        self.assertNotIn("ui.run(", source)


class CreateHelpPointResponsivePresentationTests(unittest.TestCase):
    AFFECTED_DEPARTMENTS = (
        "Caldas",
        "Chocó",
        "Quindío",
        "Risaralda",
        "Valle del Cauca",
    )

    @staticmethod
    def list_localities(department: str) -> tuple[str, ...]:
        return {
            "Antioquia": ("Medellín",),
            "Valle del Cauca": ("Cali", "Palmira"),
        }.get(department, ())

    @staticmethod
    def fill_valid_form(fake_ui: RecordingUi, *, need: str | None = None) -> None:
        field_values = {
            "Nombre del lugar": "Parque Central",
            "Dirección o referencia del lugar": "Calle 5 # 10-20",
            "Nombre de la persona coordinadora": "Ana",
            "Contacto de la persona coordinadora": "Contacto local",
        }
        for element in fake_ui.elements:
            if element.kind == "input" and element.args:
                if element.args[0] in field_values:
                    element.value = field_values[element.args[0]]
            elif element.kind == "textarea":
                element.value = "Familias evacuadas reciben apoyo."

        select_values = {
            "Departamento afectado": "Valle del Cauca",
            "Ciudad / Municipio afectado": "Roldanillo",
            "Departamento del punto": "Valle del Cauca",
            "Ciudad / Municipio del punto": "Cali",
        }
        for element in fake_ui.elements:
            if element.kind != "select":
                continue
            label = element.kwargs.get("label")
            if label in select_values:
                element.value = select_values[label]
            elif label == "Necesidades" and need is not None:
                element.value = [need]

    def test_renders_full_width_fields_and_touch_sized_publish_action(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.45, longitude=-76.53),
                create=True,
            ) as render_picker:
                create_help_point.render_create_help_point(
                    {},
                    lambda _command: self.fail(),
                    lambda _name: self.fail(),
                    lambda: True,
                    lambda: ("Antioquia", "Valle del Cauca"),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run while rendering"),
                    "https://dondeayudo.example",
                )
        finally:
            create_help_point.ui = original_ui

        render_picker.assert_called_once_with()
        self.assertIn("w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4", next(element.classes_value for element in fake_ui.elements if element.kind == "column"))
        fields = [element for element in fake_ui.elements if element.kind in {"input", "textarea", "select"}]
        self.assertTrue(fields)
        self.assertFalse(any(element.args and element.args[0] in {"Latitud", "Longitud"} for element in fields))
        self.assertFalse(
            any(
                element.kind == "input"
                and element.args
                and element.args[0] in {"Ciudad", "Departamento"}
                for element in fields
            )
        )
        self.assertTrue(all("w-full" in element.classes_value for element in fields))
        self.assertIn("w-full min-h-[44px]", next(element for element in fake_ui.elements if element.kind == "button").classes_value)
        affected_department = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs.get("label") == "Departamento afectado"
        )
        affected_city = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs.get("label") == "Ciudad / Municipio afectado"
        )
        department = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs.get("label") == "Departamento del punto"
        )
        city = next(
            element
            for element in fake_ui.elements
            if element.kind == "select"
            and element.kwargs.get("label") == "Ciudad / Municipio del punto"
        )
        self.assertEqual(
            tuple(affected_department.options)[1:],
            self.AFFECTED_DEPARTMENTS,
        )
        self.assertEqual(
            affected_city.options,
            {"": "Selecciona primero un departamento"},
        )
        self.assertEqual(
            department.options,
            {
                "": "Selecciona un departamento",
                "Antioquia": "Antioquia",
                "Valle del Cauca": "Valle del Cauca",
            },
        )
        self.assertEqual(
            city.options,
            {"": "Selecciona primero un departamento"},
        )
        self.assertFalse(city.enabled)
        self.assertNotIn("disable", city.props_value.split())
        self.assertEqual(city.disable_calls, 1)
        self.assertIn("outlined", department.props_value)
        self.assertIn("dense", city.props_value)
        bounded_selects = (
            affected_department,
            affected_city,
            department,
            city,
            next(
                element
                for element in fake_ui.elements
                if element.kind == "select"
                and element.kwargs.get("label") == "Necesidades"
            ),
        )
        for select in bounded_selects:
            with self.subTest(select=select.kwargs["label"]):
                self.assertIn("behavior=menu", select.props_value)
                self.assertIn(
                    'popup-content-style="max-height: 40vh; overflow-y: auto"',
                    select.props_value,
                )
                self.assertNotIn("options-dense", select.props_value)

        department.value = "Valle del Cauca"
        department.on_change()

        self.assertEqual(
            city.options,
            {"": "Selecciona una ciudad / municipio", "Cali": "Cali", "Palmira": "Palmira"},
        )
        self.assertEqual(city.value, "")
        self.assertTrue(city.enabled)
        self.assertEqual(city.enable_calls, 1)

        city.value = "Cali"
        department.value = ""
        department.on_change()

        self.assertEqual(city.value, "")
        self.assertFalse(city.enabled)
        self.assertEqual(city.disable_calls, 2)
        self.assertEqual(city.options, {"": "Selecciona primero un departamento"})

        labels = [
            element.args[0]
            for element in fake_ui.elements
            if element.kind == "label"
        ]
        self.assertIn("Zona que recibirá la ayuda", labels)
        self.assertIn("Dónde se recibe o coordina la ayuda", labels)

    def test_address_search_geocodes_physical_location_and_updates_picker(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        geocode_calls = []
        coordinate_calls = []
        location = SimpleNamespace(
            latitude=None,
            longitude=None,
            set_coordinates=lambda latitude, longitude: coordinate_calls.append(
                (latitude, longitude)
            ),
        )

        async def geocode(address, city, department):
            geocode_calls.append((address, city, department))
            return SimpleNamespace(latitude=3.4372, longitude=-76.5225)

        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=location,
            ):
                create_help_point.render_create_help_point(
                    {},
                    lambda _command: self.fail("must not publish"),
                    lambda _name: self.fail("must not create category"),
                    lambda: True,
                    lambda: ("Antioquia", "Valle del Cauca"),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    geocode,
                    "https://dondeayudo.example",
                )
                department = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs.get("label") == "Departamento del punto"
                )
                city = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "select"
                    and element.kwargs.get("label") == "Ciudad / Municipio del punto"
                )
                address = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                    and element.args == ("Dirección o referencia del lugar",)
                )
                department.value = "Valle del Cauca"
                city.value = "Cali"
                address.value = "Calle 5 # 10-20"

                search = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button" and element.args == ("Buscar en el mapa",)
                )
                asyncio.run(search.kwargs["on_click"]())
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(
            geocode_calls,
            [("Calle 5 # 10-20", "Cali", "Valle del Cauca")],
        )
        self.assertEqual(coordinate_calls, [(3.4372, -76.5225)])
        self.assertEqual(address.value, "Calle 5 # 10-20")

    def test_address_search_none_or_error_keeps_address_and_shows_fallback(self) -> None:
        for provider_result in (None, RuntimeError("provider unavailable")):
            with self.subTest(provider_result=provider_result):
                fake_ui = RecordingUi()
                original_ui = create_help_point.ui
                create_help_point.ui = fake_ui

                async def geocode(_address, _city, _department):
                    if isinstance(provider_result, Exception):
                        raise provider_result
                    return provider_result

                try:
                    with patch.object(
                        create_help_point,
                        "render_location_picker",
                        return_value=SimpleNamespace(
                            latitude=None,
                            longitude=None,
                            set_coordinates=lambda *_coordinates: self.fail(
                                "missing geocode must not move picker"
                            ),
                        ),
                    ):
                        create_help_point.render_create_help_point(
                            {},
                            lambda _command: self.fail("must not publish"),
                            lambda _name: self.fail("must not create category"),
                            lambda: True,
                            lambda: ("Valle del Cauca",),
                            self.list_localities,
                            lambda: self.AFFECTED_DEPARTMENTS,
                            geocode,
                            "https://dondeayudo.example",
                        )
                        department = next(
                            element
                            for element in fake_ui.elements
                            if element.kind == "select"
                            and element.kwargs.get("label") == "Departamento del punto"
                        )
                        city = next(
                            element
                            for element in fake_ui.elements
                            if element.kind == "select"
                            and element.kwargs.get("label") == "Ciudad / Municipio del punto"
                        )
                        address = next(
                            element
                            for element in fake_ui.elements
                            if element.kind == "input"
                            and element.args == ("Dirección o referencia del lugar",)
                        )
                        department.value = "Valle del Cauca"
                        city.value = "Cali"
                        address.value = "Calle 5 # 10-20"
                        search = next(
                            element
                            for element in fake_ui.elements
                            if element.kind == "button"
                            and element.args == ("Buscar en el mapa",)
                        )
                        asyncio.run(search.kwargs["on_click"]())
                finally:
                    create_help_point.ui = original_ui

                self.assertEqual(address.value, "Calle 5 # 10-20")
                self.assertTrue(
                    any(
                        element.kind == "notify"
                        and element.args
                        == (
                            "No encontramos esa dirección. Ubícala tocando el mapa.",
                        )
                        for element in fake_ui.elements
                    )
                )

    def test_success_replaces_form_with_absolute_private_url_and_copy_feedback(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        create_calls = []
        category_id = uuid4()
        synthetic_admin_url = (
            "https://dondeayudo.example/administrar/synthetic-token"
        )
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.4516, longitude=-76.532),
            ):
                create_help_point.render_create_help_point(
                    {"Agua": category_id},
                    lambda command: create_calls.append(command)
                    or SimpleNamespace(admin_token="synthetic-token"),
                    lambda _name: self.fail("empty custom category must not be created"),
                    lambda: True,
                    lambda: ("Valle del Cauca",),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example/base/?x=1#fragment",
                )
                form_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-3"
                )
                success_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-4"
                )
                self.assertTrue(form_container.visible)
                self.assertFalse(success_container.visible)
                self.assertEqual(fake_ui.javascript_calls, [])
                self.fill_valid_form(fake_ui, need="Agua")

                publish = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                )
                publish.kwargs["on_click"]()

                expected_command = build_command(
                    FormValues(
                        name="Parque Central",
                        description="Familias evacuadas reciben apoyo.",
                        affected_city="Roldanillo",
                        affected_department="Valle del Cauca",
                        city="Cali",
                        department="Valle del Cauca",
                        address="Calle 5 # 10-20",
                        latitude=3.4516,
                        longitude=-76.532,
                        coordinator_name="Ana",
                        coordinator_contact="Contacto local",
                    ),
                    ("Agua",),
                    {"Agua": category_id},
                )
                self.assertEqual(create_calls, [expected_command])
                self.assertFalse(form_container.visible)
                self.assertTrue(success_container.visible)
                labels = [
                    element.args[0]
                    for element in fake_ui.elements
                    if element.kind == "label"
                ]
                self.assertIn("Punto de ayuda publicado", labels)
                self.assertIn(
                    "Este enlace es privado. Cópialo y guárdalo: lo necesitarás "
                    "para administrar el punto.",
                    labels,
                )
                url_input = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                    and element.args == ("Enlace privado de administración",)
                )
                self.assertEqual(url_input.value, synthetic_admin_url)
                self.assertIn("readonly", url_input.props_value)
                self.assertEqual(fake_ui.javascript_calls, [])
                self.assertTrue(
                    any(
                        element.kind == "link"
                        and element.args
                        == ("Abrir administración", synthetic_admin_url)
                        for element in fake_ui.elements
                    )
                )

                copy = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Copiar enlace",)
                )
                fake_ui.javascript_results.extend((True, False))
                asyncio.run(copy.kwargs["on_click"]())
                asyncio.run(copy.kwargs["on_click"]())
        finally:
            create_help_point.ui = original_ui

        expected_script = (
            "navigator.clipboard.writeText("
            + json.dumps(synthetic_admin_url)
            + ").then(() => true).catch(() => false)"
        )
        self.assertEqual(fake_ui.javascript_calls, [expected_script, expected_script])
        copy_notifications = [
            element
            for element in fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(
            [element.args[0] for element in copy_notifications],
            [
                "Enlace privado copiado.",
                "No se pudo copiar automáticamente. Mantén presionado el enlace "
                "y cópialo manualmente.",
            ],
        )
        self.assertNotIn(
            "synthetic-token",
            repr([(element.args, element.kwargs) for element in copy_notifications]),
        )

    def test_in_flight_and_published_guards_block_all_repeated_writes(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        custom_calls = []
        create_calls = []
        publish_callback = None

        def create_category(name):
            custom_calls.append(name)
            publish_callback()
            return uuid4()

        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.45, longitude=-76.53),
            ):
                create_help_point.render_create_help_point(
                    {},
                    lambda command: create_calls.append(command)
                    or SimpleNamespace(admin_token="synthetic-token"),
                    create_category,
                    lambda: True,
                    lambda: ("Valle del Cauca",),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
                next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                    and element.args == ("+ Agregar otra necesidad",)
                ).value = "Necesidad sintética"
                self.fill_valid_form(fake_ui)
                publish = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                )
                publish_callback = publish.kwargs["on_click"]

                publish_callback()
                publish_callback()
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(custom_calls, ["Necesidad sintética"])
        self.assertEqual(len(create_calls), 1)
        self.assertEqual(publish.disable_calls, 1)
        self.assertFalse(publish.enabled)

    def test_failed_write_reenables_visible_form_without_private_link(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        create_calls = []
        category_id = uuid4()
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.45, longitude=-76.53),
            ):
                create_help_point.render_create_help_point(
                    {"Agua": category_id},
                    lambda command: create_calls.append(command)
                    or (_ for _ in ()).throw(ValueError("synthetic failure")),
                    lambda _name: self.fail("empty custom category must not be created"),
                    lambda: True,
                    lambda: ("Valle del Cauca",),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
                form_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-3"
                )
                success_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-4"
                )
                publish = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                )
                self.fill_valid_form(fake_ui, need="Agua")
                publish.kwargs["on_click"]()
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(len(create_calls), 1)
        self.assertTrue(publish.enabled)
        self.assertEqual(publish.enable_calls, 1)
        self.assertTrue(form_container.visible)
        self.assertFalse(success_container.visible)
        self.assertFalse(
            any(
                element.kind == "input"
                and "readonly" in element.props_value
                for element in fake_ui.elements
            )
        )
        self.assertFalse(
            any(
                element.kind == "label"
                and element.args == ("Punto de ayuda publicado",)
                for element in fake_ui.elements
            )
        )

    def test_unexpected_handler_failure_is_generic_and_allows_retry(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        create_calls = []
        caught_errors = []
        category_id = uuid4()

        def fail_create(command):
            create_calls.append(command)
            raise RuntimeError("database failure synthetic-token")

        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.45, longitude=-76.53),
            ):
                create_help_point.render_create_help_point(
                    {"Agua": category_id},
                    fail_create,
                    lambda _name: self.fail("empty custom category must not be created"),
                    lambda: True,
                    lambda: ("Valle del Cauca",),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
                form_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-3"
                )
                success_container = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "column"
                    and element.classes_value == "w-full gap-4"
                )
                publish = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                )
                self.fill_valid_form(fake_ui, need="Agua")

                for _attempt in range(2):
                    try:
                        publish.kwargs["on_click"]()
                    except RuntimeError as error:
                        caught_errors.append(error)
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(caught_errors, [])
        self.assertEqual(len(create_calls), 2)
        self.assertTrue(publish.enabled)
        self.assertEqual(publish.disable_calls, 2)
        self.assertEqual(publish.enable_calls, 2)
        self.assertTrue(form_container.visible)
        self.assertFalse(success_container.visible)
        notifications = [
            element.args[0]
            for element in fake_ui.elements
            if element.kind == "notify"
        ]
        self.assertEqual(
            notifications,
            [
                "No fue posible publicar el punto. Inténtalo de nuevo.",
                "No fue posible publicar el punto. Inténtalo de nuevo.",
            ],
        )
        self.assertNotIn("database failure", repr(notifications))
        self.assertNotIn("synthetic-token", repr(notifications))

    def test_invalid_form_does_not_write_custom_category_or_point(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        custom_calls = []
        create_calls = []
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=3.45, longitude=-76.53),
            ):
                create_help_point.render_create_help_point(
                    {},
                    lambda command: create_calls.append(command),
                    lambda category_name: custom_calls.append(category_name) or uuid4(),
                    lambda: True,
                    lambda: ("Valle del Cauca",),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
                self.fill_valid_form(fake_ui)
                next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                    and element.args == ("Nombre del lugar",)
                ).value = ""
                next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "input"
                    and element.args == ("+ Agregar otra necesidad",)
                ).value = "Necesidad sintética"
                publish = next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                )

                publish.kwargs["on_click"]()
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(custom_calls, [])
        self.assertEqual(create_calls, [])
        self.assertTrue(publish.enabled)

    def test_revoked_session_blocks_publish_handler_at_click_time(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        authorized = [True]
        create_calls = []
        custom_category_calls = []
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=None, longitude=None),
                create=True,
            ):
                create_help_point.render_create_help_point(
                    {},
                    lambda command: create_calls.append(command) or self.fail("must not create"),
                    lambda name: custom_category_calls.append(name) or self.fail("must not create category"),
                    lambda: authorized[0],
                    lambda: ("Antioquia", "Valle del Cauca"),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
            authorized[0] = False

            next(
                element
                for element in fake_ui.elements
                if element.kind == "button"
                and element.args == ("Publicar punto de ayuda",)
            ).kwargs["on_click"]()
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(create_calls, [])
        self.assertEqual(custom_category_calls, [])
        self.assertEqual(fake_ui.navigate.paths, ["/acceso"])
        notification = next(element for element in fake_ui.elements if element.kind == "notify")
        self.assertNotIn("private", repr((notification.args, notification.kwargs)))

    def test_missing_map_selection_notifies_without_calling_handlers(self) -> None:
        fake_ui = RecordingUi()
        original_ui = create_help_point.ui
        create_help_point.ui = fake_ui
        create_calls = []
        custom_calls = []
        try:
            with patch.object(
                create_help_point,
                "render_location_picker",
                return_value=SimpleNamespace(latitude=None, longitude=None),
                create=True,
            ):
                create_help_point.render_create_help_point(
                    {},
                    lambda command: create_calls.append(command),
                    lambda name: custom_calls.append(name),
                    lambda: True,
                    lambda: ("Antioquia", "Valle del Cauca"),
                    self.list_localities,
                    lambda: self.AFFECTED_DEPARTMENTS,
                    lambda *_args: self.fail("geocoder must not run"),
                    "https://dondeayudo.example",
                )
                next(
                    element
                    for element in fake_ui.elements
                    if element.kind == "button"
                    and element.args == ("Publicar punto de ayuda",)
                ).kwargs["on_click"]()
        finally:
            create_help_point.ui = original_ui

        self.assertEqual(create_calls, [])
        self.assertEqual(custom_calls, [])
        self.assertTrue(any(element.kind == "notify" and "ubicación" in element.args[0] for element in fake_ui.elements))


if __name__ == "__main__":
    unittest.main()
