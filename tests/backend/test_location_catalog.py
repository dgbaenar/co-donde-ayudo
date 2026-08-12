from __future__ import annotations

import hashlib
from importlib.resources import files
import json

import pytest

from backend.infrastructure.locations.catalog import ColombiaLocationCatalog


@pytest.fixture(scope="module")
def catalog() -> ColombiaLocationCatalog:
    return ColombiaLocationCatalog.from_package_data()


def test_catalog_contains_all_departments_and_localities(
    catalog: ColombiaLocationCatalog,
) -> None:
    departments = catalog.list_departments()

    assert len(departments) == 33
    assert sum(len(catalog.list_localities(name)) for name in departments) == 1_122


def test_catalog_preserves_known_department_locality_relationships(
    catalog: ColombiaLocationCatalog,
) -> None:
    assert "Medellín" in catalog.list_localities("Antioquia")
    assert "San Andrés de Cuerquía" in catalog.list_localities("Antioquia")
    assert "Cali" in catalog.list_localities("Valle del Cauca")
    assert "Bogotá, D.C." in catalog.list_localities("Bogotá, D.C.")
    assert "Cali" not in catalog.list_localities("Antioquia")


def test_catalog_returns_alphabetical_immutable_results(
    catalog: ColombiaLocationCatalog,
) -> None:
    departments = catalog.list_departments()
    antioquia_localities = catalog.list_localities("Antioquia")

    assert isinstance(departments, tuple)
    assert isinstance(antioquia_localities, tuple)
    assert departments.index("Amazonas") < departments.index("Antioquia")
    assert antioquia_localities.index("Abejorral") < antioquia_localities.index("Medellín")


@pytest.mark.parametrize("department", ["", "Departamento inexistente"])
def test_catalog_returns_empty_tuple_for_unknown_department(
    catalog: ColombiaLocationCatalog, department: str
) -> None:
    assert catalog.list_localities(department) == ()


def test_snapshot_manifest_matches_canonical_rows_and_counts() -> None:
    package = files("backend.infrastructure.locations")
    snapshot = json.loads(
        package.joinpath("divipola_mgn_2025.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        package.joinpath("divipola_mgn_2025.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rows = snapshot["rows"]
    canonical_rows = json.dumps(
        rows,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    assert manifest["source"]["version"] == "2025"
    assert manifest["source"]["retrieved_at"] == "2026-08-11"
    assert manifest["source"]["url"].startswith(
        "https://geoportal.dane.gov.co/mparcgis/rest/services/Divipola/"
    )
    assert manifest["canonical_rows_sha256"] == hashlib.sha256(
        canonical_rows
    ).hexdigest()
    assert manifest["counts"] == {
        "departments": 33,
        "islands": 1,
        "localities": 1_122,
        "municipalities": 1_103,
        "non_municipalized_areas": 18,
    }


def test_snapshot_codes_are_strings_and_locality_rows_are_unique() -> None:
    package = files("backend.infrastructure.locations")
    rows = json.loads(
        package.joinpath("divipola_mgn_2025.json").read_text(encoding="utf-8")
    )["rows"]
    keys = [(row["department_code"], row["locality_code"]) for row in rows]

    assert all(
        isinstance(row["department_code"], str)
        and isinstance(row["locality_code"], str)
        for row in rows
    )
    assert len(keys) == len(set(keys)) == 1_122
    assert any(
        row["department_name"] == "ANTIOQUIA"
        and row["locality_name"] == "SAN ANDRÉS DE CUERQUÍA"
        for row in rows
    )


def test_snapshot_has_no_duplicate_raw_names_within_a_department() -> None:
    package = files("backend.infrastructure.locations")
    rows = json.loads(
        package.joinpath("divipola_mgn_2025.json").read_text(encoding="utf-8")
    )["rows"]
    names_by_department: dict[str, list[str]] = {}
    for row in rows:
        names_by_department.setdefault(row["department_code"], []).append(
            row["locality_name"]
        )

    assert all(
        len(names) == len(set(names)) for names in names_by_department.values()
    )


def test_catalog_has_no_duplicate_display_names_within_a_department(
    catalog: ColombiaLocationCatalog,
) -> None:
    for department in catalog.list_departments():
        localities = catalog.list_localities(department)

        assert len(localities) == len(set(localities)), department
