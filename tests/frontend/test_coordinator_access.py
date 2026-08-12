from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from frontend import app as frontend_app
from frontend.pages import coordinator_access


class RecordingElement:
    def __init__(self, kind, *args, **kwargs):
        self.kind, self.args, self.kwargs = kind, args, kwargs
        self.value = kwargs.get("value")
        self.classes_value = ""

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def classes(self, value): self.classes_value = value; return self


class RecordingNavigation:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.on_navigate = lambda _path: None

    def to(self, path: str) -> None:
        self.on_navigate(path)
        self.paths.append(path)


class RecordingUi:
    def __init__(self) -> None:
        self.elements = []
        self.navigate = RecordingNavigation()
        self.pages = {}
        self.on_notify = lambda: None

    def _record(self, kind, *args, **kwargs):
        element = RecordingElement(kind, *args, **kwargs)
        self.elements.append(element)
        return element

    def page(self, path, **_kwargs):
        def register(handler):
            self.pages[path] = handler
            return handler

        return register

    def column(self, *args, **kwargs): return self._record("column", *args, **kwargs)
    def label(self, *args, **kwargs): return self._record("label", *args, **kwargs)
    def input(self, *args, **kwargs): return self._record("input", *args, **kwargs)
    def button(self, *args, **kwargs): return self._record("button", *args, **kwargs)
    def notify(self, *args, **kwargs):
        self.on_notify()
        return self._record("notify", *args, **kwargs)


class RecordingAuthorizer:
    def __init__(self, accepted_key: str) -> None:
        self.accepted_key = accepted_key
        self.calls: list[str] = []

    def __call__(self, provided_key: str) -> bool:
        self.calls.append(provided_key)
        return provided_key == self.accepted_key


class CoordinatorAccessPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_ui = RecordingUi()
        self.user_storage = {}
        self.fake_app = SimpleNamespace(storage=SimpleNamespace(user=self.user_storage))

    def render(self, authorizer) -> None:
        self.ui_patch = patch.object(coordinator_access, "ui", self.fake_ui)
        self.app_patch = patch.object(coordinator_access, "app", self.fake_app)
        self.ui_patch.start()
        self.app_patch.start()
        self.addCleanup(self.ui_patch.stop)
        self.addCleanup(self.app_patch.stop)
        coordinator_access.render_coordinator_access(authorizer)

    def test_wrong_key_is_checked_by_authorizer_cleared_and_rejected_generically(self) -> None:
        authorizer = RecordingAuthorizer("synthetic-correct-key")
        self.render(authorizer)
        key_input = next(element for element in self.fake_ui.elements if element.kind == "input")
        key_input.value = "synthetic-wrong-key"
        self.user_storage[coordinator_access.COORDINATOR_AUTHORIZED_KEY] = True
        storage_when_notified = []
        self.fake_ui.on_notify = lambda: storage_when_notified.append(dict(self.user_storage))

        next(element for element in self.fake_ui.elements if element.kind == "button").kwargs[
            "on_click"
        ]()

        self.assertEqual(authorizer.calls, ["synthetic-wrong-key"])
        self.assertEqual(key_input.value, "")
        self.assertEqual(self.user_storage, {})
        self.assertEqual(storage_when_notified, [{}])
        self.assertEqual(self.fake_ui.navigate.paths, [])
        self.assertTrue(key_input.kwargs["password"])
        notification = next(element for element in self.fake_ui.elements if element.kind == "notify")
        rendered_notification = repr((notification.args, notification.kwargs))
        self.assertNotIn("synthetic-wrong-key", rendered_notification)
        self.assertNotIn("synthetic-correct-key", rendered_notification)

    def test_correct_key_sets_boolean_session_authorization_and_navigates_to_create(self) -> None:
        authorizer = RecordingAuthorizer("synthetic-correct-key")
        self.render(authorizer)
        key_input = next(element for element in self.fake_ui.elements if element.kind == "input")
        key_input.value = "synthetic-correct-key"
        input_values_when_navigating = []
        self.fake_ui.navigate.on_navigate = (
            lambda _path: input_values_when_navigating.append(key_input.value)
        )

        next(element for element in self.fake_ui.elements if element.kind == "button").kwargs[
            "on_click"
        ]()

        self.assertEqual(
            self.user_storage,
            {coordinator_access.COORDINATOR_AUTHORIZED_KEY: True},
        )
        self.assertEqual(key_input.value, "")
        self.assertEqual(input_values_when_navigating, [""])
        self.assertEqual(self.fake_ui.navigate.paths, ["/crear"])


class CoordinatorAccessRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_ui = RecordingUi()
        self.user_storage = {}
        self.fake_app = SimpleNamespace(storage=SimpleNamespace(user=self.user_storage))
        async def geocode_address(_address, _city, _department):
            return None

        self.dependencies = {
            "list_public_help_points": lambda: (),
            "list_active_categories": lambda: {},
            "list_departments": lambda: ("Valle del Cauca",),
            "list_localities": lambda _department: ("Cali",),
            "list_affected_departments": lambda: ("Valle del Cauca",),
            "geocode_address": geocode_address,
            "create_help_point": lambda _command: self.fail("must not create"),
            "get_managed_help_point": lambda _token: object(),
            "add_need": lambda *_args: object(),
            "remove_need": lambda *_args: object(),
            "change_need_status": lambda *_args: object(),
            "deactivate_help_point": lambda *_args: object(),
            "create_custom_category": lambda _name: self.fail("must not create category"),
            "update_help_point_info": lambda *_args: object(),
            "authorize_coordinator_access": lambda _key: False,
            "get_public_help_point": lambda _point_id: None,
        }

    def register_routes(self) -> None:
        self.ui_patch = patch.object(frontend_app, "ui", self.fake_ui)
        self.app_patch = patch.object(frontend_app, "app", self.fake_app)
        self.ui_patch.start()
        self.app_patch.start()
        self.addCleanup(self.ui_patch.stop)
        self.addCleanup(self.app_patch.stop)
        frontend_app.create_app(**self.dependencies)

    def test_create_without_session_redirects_before_rendering_form(self) -> None:
        self.register_routes()

        with patch.object(frontend_app, "render_create_help_point") as render:
            self.fake_ui.pages["/crear"]()

        render.assert_not_called()
        self.assertEqual(self.fake_ui.navigate.paths, ["/acceso"])

    def test_access_route_renders_with_injected_authorizer(self) -> None:
        self.register_routes()

        with patch.object(frontend_app, "render_coordinator_access") as render:
            self.fake_ui.pages["/acceso"]()

        render.assert_called_once_with(self.dependencies["authorize_coordinator_access"])

    def test_create_with_session_renders_form(self) -> None:
        self.user_storage[coordinator_access.COORDINATOR_AUTHORIZED_KEY] = True
        self.register_routes()

        with patch.object(frontend_app, "render_create_help_point") as render:
            self.fake_ui.pages["/crear"]()

        render.assert_called_once()
        self.assertEqual(self.fake_ui.navigate.paths, [])
        current_authorization = render.call_args.args[3]
        self.assertIs(
            render.call_args.args[4],
            self.dependencies["list_departments"],
        )
        self.assertIs(
            render.call_args.args[5],
            self.dependencies["list_localities"],
        )
        self.assertIs(
            render.call_args.args[6],
            self.dependencies["list_affected_departments"],
        )
        self.assertIs(
            render.call_args.args[7],
            self.dependencies["geocode_address"],
        )
        self.user_storage.clear()
        self.assertFalse(current_authorization())

    def test_public_and_private_admin_routes_do_not_require_coordinator_session(self) -> None:
        self.register_routes()

        with (
            patch.object(frontend_app, "render_home") as render_home,
            patch.object(frontend_app, "render_manage_help_point") as render_manage,
        ):
            self.fake_ui.pages["/"]()
            self.fake_ui.pages["/administrar/{admin_token}"]("private-admin-token")

        render_home.assert_called_once_with(
            (),
            {},
            self.dependencies["list_affected_departments"],
            self.dependencies["list_localities"],
        )
        render_manage.assert_called_once()
        self.assertEqual(self.fake_ui.navigate.paths, [])


if __name__ == "__main__":
    unittest.main()
