"""NiceGUI application entrypoint assembled from injected dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from uuid import UUID

from nicegui import app, ui

from backend.domain.models import HelpPoint, PublicHelpPoint
from frontend.pages.create_help_point import (
    CreateCustomCategoryHandler,
    CreateHelpPointHandler,
    GeocodeAddress,
    render_create_help_point,
)
from frontend.pages.coordinator_access import (
    AuthorizeCoordinatorAccess,
    is_coordinator_authorized,
    render_coordinator_access,
)
from frontend.pages.home import ListDepartments, ListLocalities, render_home
from frontend.pages.help_point_detail import (
    GetPublicHelpPoint,
    render_help_point_detail_for_path,
)
from frontend.pages.manage_help_point import (
    AddNeedHandler,
    ChangeNeedStatusHandler,
    DeactivateHelpPointHandler,
    RemoveNeedHandler,
    UpdateHelpPointInfoHandler,
    render_manage_help_point,
)


def create_app(
    list_public_help_points: Callable[[], Sequence[PublicHelpPoint]],
    list_active_categories: Callable[[], Mapping[str, UUID]],
    list_departments: ListDepartments,
    list_localities: ListLocalities,
    list_affected_departments: ListDepartments,
    geocode_address: GeocodeAddress,
    create_help_point: CreateHelpPointHandler,
    get_managed_help_point: Callable[[str], HelpPoint],
    add_need: AddNeedHandler,
    remove_need: RemoveNeedHandler,
    change_need_status: ChangeNeedStatusHandler,
    deactivate_help_point: DeactivateHelpPointHandler,
    create_custom_category: CreateCustomCategoryHandler,
    update_help_point_info: UpdateHelpPointInfoHandler,
    authorize_coordinator_access: AuthorizeCoordinatorAccess,
    get_public_help_point: GetPublicHelpPoint,
) -> None:
    """Register routes without creating external clients or starting a server."""

    @ui.page("/", title="¿Dónde ayudo?")
    def home_page() -> None:
        render_home(
            list_public_help_points(),
            list_active_categories(),
            list_affected_departments,
            list_localities,
        )

    @ui.page("/acceso")
    def coordinator_access_page() -> None:
        render_coordinator_access(authorize_coordinator_access)

    @ui.page("/puntos/{point_id}")
    def help_point_detail_page(point_id: str) -> None:
        render_help_point_detail_for_path(
            point_id,
            get_public_help_point,
            list_active_categories(),
        )

    @ui.page("/crear")
    def create_page() -> None:
        if not is_coordinator_authorized(app.storage.user):
            ui.navigate.to("/acceso")
            return

        render_create_help_point(
            list_active_categories(),
            create_help_point,
            create_custom_category,
            lambda: is_coordinator_authorized(app.storage.user),
            list_departments,
            list_localities,
            list_affected_departments,
            geocode_address,
        )

    @ui.page("/administrar/{admin_token}")
    def manage_page(admin_token: str) -> None:
        render_manage_help_point(
            get_managed_help_point(admin_token),
            admin_token,
            list_active_categories(),
            add_need,
            remove_need,
            change_need_status,
            deactivate_help_point,
            update_help_point_info,
        )
