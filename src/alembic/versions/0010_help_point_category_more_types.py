"""Widen the help point category check constraint with six new aid types.

`categoria` (`category`) classifies the help point itself. This adds six new allowed values —
Psicológica, Médica, Vivienda y Albergues, Alimentación Comunitaria, Voluntariado, Donación de
sangre — alongside the three existing ones (Recolección de donaciones, Remoción de escombros,
Labores de rescate). No existing row's value changes; this only widens the `IN (...)` list that
`help_points_categoria_check` allows, so no backfill is needed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_help_point_category_more_types"
down_revision = "0009_help_point_multiple_affected_areas"
branch_labels = None
depends_on = None

OLD_CATEGORIES = ("Recolección de donaciones", "Remoción de escombros", "Labores de rescate")
NEW_CATEGORIES = OLD_CATEGORIES + (
    "Psicológica",
    "Médica",
    "Vivienda y Albergues",
    "Alimentación Comunitaria",
    "Voluntariado",
    "Donación de sangre",
)


def upgrade() -> None:
    op.drop_constraint("help_points_categoria_check", "help_points", type_="check")
    op.create_check_constraint(
        "help_points_categoria_check",
        "help_points",
        sa.column("categoria").in_(NEW_CATEGORIES),
    )


def downgrade() -> None:
    op.drop_constraint("help_points_categoria_check", "help_points", type_="check")
    op.create_check_constraint(
        "help_points_categoria_check",
        "help_points",
        sa.column("categoria").in_(OLD_CATEGORIES),
    )
