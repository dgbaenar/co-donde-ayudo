"""NiceGUI application entrypoint assembled from injected dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID

from nicegui import app, ui
from starlette.responses import PlainTextResponse

from backend.domain.models import HelpPoint
from frontend.pages.create_help_point import (
    CreateCustomCategoryHandler,
    CreateHelpPointHandler,
    GeocodeAddress,
    render_create_help_point,
)
from frontend.pages.coordinator_access import (
    AuthorizeCoordinatorAccess,
    render_coordinator_access,
)
from frontend.pages.home import (
    AbortPublicHomeRefresh,
    BeginPublicHomeRefresh,
    FinishPublicHomeRefresh,
    GetCachedPublicHome,
    ListDepartments,
    ListLocalities,
    ListPublicHelpPointsPage,
    OpenPublicHelpPointsSnapshot,
    WaitForCachedPublicHome,
    render_home,
)
from frontend.pages.help_point_detail import (
    CreateCommitmentHandler,
    GetCachedPublicHelpPoint,
    RefreshPublicHelpPoint,
    render_cached_help_point_detail_for_path,
)
from frontend.pages.manage_help_point import (
    AddNeedHandler,
    ChangeNeedStatusHandler,
    DeactivateHelpPointHandler,
    RemoveNeedHandler,
    UpdateHelpPointAffectedAreasHandler,
    UpdateHelpPointCategoryHandler,
    UpdateHelpPointInfoHandler,
    UpdateHelpPointLinksHandler,
    UpdateHelpPointLocationsHandler,
    render_manage_help_point,
)


def create_app(
    open_active_help_points_snapshot: OpenPublicHelpPointsSnapshot,
    list_active_help_points_page: ListPublicHelpPointsPage,
    list_active_categories: Callable[[], Mapping[str, UUID]],
    get_cached_public_home: GetCachedPublicHome,
    begin_public_home_refresh: BeginPublicHomeRefresh,
    finish_public_home_refresh: FinishPublicHomeRefresh,
    abort_public_home_refresh: AbortPublicHomeRefresh,
    wait_for_cached_public_home: WaitForCachedPublicHome,
    list_departments: ListDepartments,
    list_localities: ListLocalities,
    list_affected_departments: ListDepartments,
    geocode_address: GeocodeAddress,
    app_base_url: str,
    create_help_point: CreateHelpPointHandler,
    get_managed_help_point: Callable[[str], HelpPoint],
    add_need: AddNeedHandler,
    remove_need: RemoveNeedHandler,
    change_need_status: ChangeNeedStatusHandler,
    deactivate_help_point: DeactivateHelpPointHandler,
    create_custom_category: CreateCustomCategoryHandler,
    update_help_point_info: UpdateHelpPointInfoHandler,
    update_help_point_category: UpdateHelpPointCategoryHandler,
    update_help_point_links: UpdateHelpPointLinksHandler,
    update_help_point_locations: UpdateHelpPointLocationsHandler,
    update_help_point_affected_areas: UpdateHelpPointAffectedAreasHandler,
    authorize_coordinator_access: AuthorizeCoordinatorAccess,
    get_cached_public_help_point: GetCachedPublicHelpPoint,
    refresh_public_help_point: RefreshPublicHelpPoint,
    is_database_ready: Callable[[], bool],
    create_commitment: CreateCommitmentHandler,
) -> None:
    """Register routes without creating external clients or starting a server."""
    @app.get("/healthz")
    def health() -> PlainTextResponse:
        return PlainTextResponse("ok", status_code=200)

    @app.get("/readyz")
    def readiness() -> PlainTextResponse:
        if is_database_ready():
            return PlainTextResponse("ready", status_code=200)
        return PlainTextResponse("not ready", status_code=503)

    ui.add_css(
        ".bounded-select-menu { max-height: 40vh !important; "
        "overflow-y: auto !important; }",
        shared=True,
    )
    app.colors(primary="#047857", secondary="#003893")

    @ui.page("/", title="¿Dónde ayudo?")
    def home_page() -> None:
        render_home(
            (),
            {},
            list_affected_departments,
            list_localities,
            list_active_categories=list_active_categories,
            open_public_help_points_snapshot=open_active_help_points_snapshot,
            list_public_help_points_page=list_active_help_points_page,
            get_cached_public_home=get_cached_public_home,
            begin_public_home_refresh=begin_public_home_refresh,
            finish_public_home_refresh=finish_public_home_refresh,
            abort_public_home_refresh=abort_public_home_refresh,
            wait_for_cached_public_home=wait_for_cached_public_home,
        )

    @ui.page("/acceso")
    def coordinator_access_page() -> None:
        render_coordinator_access(authorize_coordinator_access)

    @ui.page("/puntos/{point_id}")
    def help_point_detail_page(point_id: str) -> None:
        render_cached_help_point_detail_for_path(
            point_id,
            get_cached_public_help_point,
            refresh_public_help_point,
            create_commitment,
        )

    @ui.page("/crear")
    def create_page() -> None:
        render_create_help_point(
            list_active_categories(),
            create_help_point,
            create_custom_category,
            list_departments,
            list_localities,
            list_affected_departments,
            geocode_address,
            app_base_url,
        )

    @ui.page("/administrar/{admin_token}")
    def manage_page(admin_token: str) -> None:
        try:
            point = get_managed_help_point(admin_token)
        except PermissionError:
            ui.label("Este enlace de administración no es válido.")
            return
        render_manage_help_point(
            point,
            admin_token,
            list_active_categories(),
            add_need,
            remove_need,
            change_need_status,
            deactivate_help_point,
            update_help_point_info,
            update_help_point_category,
            update_help_point_links,
            update_help_point_locations,
            update_help_point_affected_areas,
            geocode_address,
        )
