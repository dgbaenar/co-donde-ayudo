from __future__ import annotations


AFFECTED_DEPARTMENTS = (
    "Caldas",
    "Chocó",
    "Quindío",
    "Risaralda",
    "Valle del Cauca",
)


def list_affected_departments() -> tuple[str, ...]:
    return AFFECTED_DEPARTMENTS
