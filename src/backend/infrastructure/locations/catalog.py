from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
from types import MappingProxyType
from typing import Mapping
import unicodedata


_INTERMEDIATE_LOWERCASE_WORDS = frozenset({"de", "del", "la", "las", "los", "y"})
_DISPLAY_NAME_OVERRIDES = {"SANTIAGO DE CALI": "Cali"}


def display_name(source_name: str) -> str:
    override = _DISPLAY_NAME_OVERRIDES.get(source_name)
    if override is not None:
        return override

    words = source_name.lower().title().split()
    return " ".join(
        word.lower()
        if index > 0 and word.casefold() in _INTERMEDIATE_LOWERCASE_WORDS
        else word
        for index, word in enumerate(words)
    )


def alphabetical_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


@dataclass(frozen=True, slots=True)
class ColombiaLocationCatalog:
    _departments: tuple[str, ...]
    _localities_by_department: Mapping[str, tuple[str, ...]]

    @classmethod
    def from_package_data(cls) -> "ColombiaLocationCatalog":
        snapshot = files("backend.infrastructure.locations").joinpath(
            "divipola_mgn_2025.json"
        )
        rows = json.loads(snapshot.read_text(encoding="utf-8"))["rows"]
        grouped_localities: dict[str, list[str]] = {}
        for row in rows:
            department = display_name(row["department_name"])
            locality = display_name(row["locality_name"])
            grouped_localities.setdefault(department, []).append(locality)

        localities_by_department = {
            department: tuple(sorted(localities, key=alphabetical_key))
            for department, localities in grouped_localities.items()
        }
        departments = tuple(sorted(localities_by_department, key=alphabetical_key))
        return cls(
            _departments=departments,
            _localities_by_department=MappingProxyType(localities_by_department),
        )

    def list_departments(self) -> tuple[str, ...]:
        return self._departments

    def list_localities(self, department: str) -> tuple[str, ...]:
        return self._localities_by_department.get(department, ())
