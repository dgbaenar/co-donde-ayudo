"""Composition root for the NiceGUI application."""

from __future__ import annotations

from nicegui import ui

from backend.application.coordinator_access import CoordinatorAccessService
from backend.application.services import HelpPointService
from backend.core.config import ApplicationSettings
from backend.domain.emergency_scope import list_affected_departments
from backend.infrastructure.geocoding.nominatim import NominatimGeocoder
from backend.infrastructure.locations.catalog import ColombiaLocationCatalog
from backend.infrastructure.postgres.config import DatabaseConfig
from backend.infrastructure.postgres.database import create_session_factory
from backend.infrastructure.postgres.repository import PostgresHelpPointRepository
from frontend.app import create_app


def build_runtime(settings: ApplicationSettings) -> tuple[str, bool]:
    """Build application dependencies and register routes from explicit configuration."""
    config = DatabaseConfig.from_url(settings.database_url.get_secret_value())
    session_factory = create_session_factory(config)
    repository = PostgresHelpPointRepository(session_factory)
    location_catalog = ColombiaLocationCatalog.from_package_data()
    service = HelpPointService(repository, location_catalog)
    access_service = CoordinatorAccessService(
        settings.coordinator_access_key.get_secret_value()
    )
    geocoder = NominatimGeocoder()
    create_app(
        list_public_help_points=service.list_active_help_points,
        list_active_categories=service.list_active_categories,
        list_departments=location_catalog.list_departments,
        list_localities=location_catalog.list_localities,
        list_affected_departments=list_affected_departments,
        geocode_address=geocoder.search,
        app_base_url=settings.app_base_url,
        create_help_point=service.create_help_point,
        create_custom_category=service.create_custom_category,
        get_managed_help_point=service.get_managed_help_point,
        add_need=service.add_need,
        remove_need=service.remove_need,
        change_need_status=service.change_need_status,
        update_help_point_info=service.update_help_point_info,
        deactivate_help_point=service.deactivate_help_point,
        authorize_coordinator_access=access_service.authorize,
        get_public_help_point=service.get_public_help_point,
    )
    return (
        settings.app_session_secret.get_secret_value(),
        settings.session_cookie_https_only,
    )


def run() -> None:
    """Build the configured application and start the NiceGUI server."""
    storage_secret, https_only = build_runtime(ApplicationSettings())
    ui.run(
        reload=False,
        storage_secret=storage_secret,
        session_middleware_kwargs={"https_only": https_only},
    )
