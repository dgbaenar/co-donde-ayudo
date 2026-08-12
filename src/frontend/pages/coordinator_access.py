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
    with ui.column().classes("w-full min-h-screen bg-slate-50 p-4"):
        with ui.card().classes(
            "w-full max-w-md mx-auto gap-4 p-5 md:p-6 bg-white "
            "border border-slate-200 rounded-2xl shadow-none"
        ):
            ui.label("Acceso para coordinadores").classes(
                "text-2xl font-semibold text-slate-900"
            )
            ui.label(
                "Si coordinas un punto de ayuda o de recolección, ingresa la clave "
                "compartida para crear y publicar el punto."
            ).classes("text-sm leading-relaxed text-slate-600")
            access_key = ui.input("Clave de acceso", password=True).classes("w-full")
            ui.label(
                "¿No tienes una clave o necesitas ayuda? "
                "Contacto por WhatsApp: dan.barod"
            ).classes("text-sm leading-relaxed text-slate-600")

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

            ui.button("Continuar", on_click=submit).classes(
                "w-full min-h-[48px] text-base"
            ).props("unelevated color=green-9")
