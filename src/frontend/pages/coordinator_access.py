"""Shared coordinator access page backed by the injected authorization service."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from nicegui import app, ui


COORDINATOR_AUTHORIZED_KEY = "coordinator_authorized"
AuthorizeCoordinatorAccess = Callable[[str], bool]


def is_coordinator_authorized(user_storage: Mapping[str, object]) -> bool:
    """Return whether the current user session has coordinator access."""
    return user_storage.get(COORDINATOR_AUTHORIZED_KEY) is True


def render_coordinator_access(authorize: AuthorizeCoordinatorAccess) -> None:
    """Render the shared-key access form using only the injected authorizer."""
    with ui.column().classes("w-full max-w-md mx-auto gap-3 p-4"):
        ui.label("Acceso para coordinadores").classes("text-h5")
        access_key = ui.input("Clave de acceso", password=True).classes("w-full")

        def submit() -> None:
            provided_key = access_key.value or ""
            if not authorize(provided_key):
                access_key.value = ""
                app.storage.user.pop(COORDINATOR_AUTHORIZED_KEY, None)
                ui.notify("No fue posible autorizar el acceso.", type="negative")
                return

            app.storage.user[COORDINATOR_AUTHORIZED_KEY] = True
            access_key.value = ""
            ui.navigate.to("/crear")

        ui.button("Continuar", on_click=submit).classes("w-full min-h-[44px]")
