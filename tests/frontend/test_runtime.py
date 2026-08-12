from __future__ import annotations

import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

from backend.infrastructure.locations.catalog import ColombiaLocationCatalog
from backend.infrastructure.geocoding.nominatim import NominatimGeocoder
from backend.domain.emergency_scope import list_affected_departments


class RuntimeTests(unittest.TestCase):
    def import_runtime(self):
        sys.modules.pop("frontend.runtime", None)
        return importlib.import_module("frontend.runtime")

    def test_import_does_not_build_runtime_or_start_server(self) -> None:
        with (
            patch("backend.infrastructure.postgres.database.create_session_factory") as create_session_factory,
            patch.object(ColombiaLocationCatalog, "from_package_data") as from_package_data,
            patch.object(NominatimGeocoder, "__init__", return_value=None) as geocoder_init,
            patch("nicegui.ui.run") as ui_run,
        ):
            self.import_runtime()

        create_session_factory.assert_not_called()
        from_package_data.assert_not_called()
        geocoder_init.assert_not_called()
        ui_run.assert_not_called()

    def test_build_runtime_wires_explicit_settings_repository_services_and_app(self) -> None:
        runtime = self.import_runtime()
        settings = MagicMock()
        settings.database_url.get_secret_value.return_value = (
            "postgresql://example.test/co_ayuda"
        )
        settings.coordinator_access_key.get_secret_value.return_value = "synthetic-access-key"
        settings.app_session_secret.get_secret_value.return_value = "synthetic-session-secret"
        settings.app_base_url = "https://dondeayudo.example/base"
        settings.session_cookie_https_only = True
        settings.port = 4321
        database_config = MagicMock()
        session_factory = MagicMock()
        repository = MagicMock()
        service = MagicMock()
        access_service = MagicMock()
        location_catalog = MagicMock()
        geocoder = MagicMock()
        database_ready = MagicMock()

        with (
            patch.object(
                runtime.DatabaseConfig,
                "from_url",
                return_value=database_config,
            ) as from_url,
            patch.object(runtime, "create_session_factory", return_value=session_factory) as create_factory,
            patch.object(
                runtime,
                "create_database_readiness_probe",
                return_value=database_ready,
            ) as create_readiness_probe,
            patch.object(runtime, "PostgresHelpPointRepository", return_value=repository) as repository_type,
            patch.object(runtime, "HelpPointService", return_value=service) as service_type,
            patch.object(runtime, "CoordinatorAccessService", return_value=access_service) as access_service_type,
            patch.object(
                ColombiaLocationCatalog,
                "from_package_data",
                return_value=location_catalog,
            ) as from_package_data,
            patch.object(runtime, "NominatimGeocoder", return_value=geocoder) as geocoder_type,
            patch.object(runtime, "create_app") as create_app,
        ):
            storage_secret, https_only = runtime.build_runtime(settings)

        from_url.assert_called_once_with("postgresql://example.test/co_ayuda")
        settings.database_url.get_secret_value.assert_called_once_with()
        settings.coordinator_access_key.get_secret_value.assert_called_once_with()
        settings.app_session_secret.get_secret_value.assert_called_once_with()
        create_factory.assert_called_once_with(database_config)
        create_readiness_probe.assert_called_once_with(session_factory)
        repository_type.assert_called_once_with(session_factory)
        service_type.assert_called_once_with(repository, location_catalog)
        access_service_type.assert_called_once_with("synthetic-access-key")
        from_package_data.assert_called_once_with()
        geocoder_type.assert_called_once_with()
        self.assertEqual(storage_secret, "synthetic-session-secret")
        self.assertTrue(https_only)
        create_app.assert_called_once_with(
            list_public_help_points=service.list_active_help_points,
            list_active_categories=service.list_active_categories,
            list_departments=location_catalog.list_departments,
            list_localities=location_catalog.list_localities,
            list_affected_departments=list_affected_departments,
            geocode_address=geocoder.search,
            app_base_url="https://dondeayudo.example/base",
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
            is_database_ready=database_ready,
            create_commitment=service.create_commitment,
        )

    def test_build_runtime_uses_http_cookie_policy_from_settings_without_recomputing_it(self) -> None:
        runtime = self.import_runtime()
        settings = MagicMock()
        settings.database_url.get_secret_value.return_value = (
            "postgresql://example.test/co_ayuda"
        )
        settings.coordinator_access_key.get_secret_value.return_value = "synthetic-access-key"
        settings.app_session_secret.get_secret_value.return_value = "synthetic-session-secret"
        settings.session_cookie_https_only = False

        with (
            patch.object(runtime.DatabaseConfig, "from_url", return_value=MagicMock()),
            patch.object(runtime, "create_session_factory", return_value=MagicMock()),
            patch.object(
                runtime,
                "create_database_readiness_probe",
                return_value=MagicMock(),
            ),
            patch.object(runtime, "PostgresHelpPointRepository", return_value=MagicMock()),
            patch.object(runtime, "HelpPointService", return_value=MagicMock()),
            patch.object(runtime, "CoordinatorAccessService", return_value=MagicMock()),
            patch.object(ColombiaLocationCatalog, "from_package_data", return_value=MagicMock()),
            patch.object(runtime, "NominatimGeocoder", return_value=MagicMock()),
            patch.object(runtime, "create_app"),
        ):
            storage_secret, https_only = runtime.build_runtime(settings)

        self.assertEqual(storage_secret, "synthetic-session-secret")
        self.assertFalse(https_only)

    def test_run_creates_settings_builds_runtime_and_preserves_ui_security_arguments(self) -> None:
        runtime = self.import_runtime()
        calls: list[str] = []
        settings = MagicMock()
        settings.port = 4321

        with (
            patch.object(
                runtime,
                "ApplicationSettings",
                side_effect=lambda: calls.append("settings") or settings,
            ) as settings_type,
            patch.object(
                runtime,
                "build_runtime",
                side_effect=lambda current_settings: calls.append("build")
                or ("synthetic-session-secret", True),
            ) as build_runtime,
            patch.object(runtime.ui, "run", side_effect=lambda **kwargs: calls.append("run")) as ui_run,
        ):
            runtime.run()

        self.assertEqual(calls, ["settings", "build", "run"])
        settings_type.assert_called_once_with()
        build_runtime.assert_called_once_with(settings)
        ui_run.assert_called_once_with(
            host="0.0.0.0",
            port=4321,
            show=False,
            reload=False,
            storage_secret="synthetic-session-secret",
            session_middleware_kwargs={"https_only": True},
        )


if __name__ == "__main__":
    unittest.main()
