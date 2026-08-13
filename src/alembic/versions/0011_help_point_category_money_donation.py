"""Widen the help point category check constraint with money donation.

`categoria` (`category`) classifies the help point itself. This adds one new allowed value —
Donación de dinero — alongside the nine existing ones. No existing row's value changes; this only
widens the `IN (...)` list that `help_points_categoria_check` allows, so no backfill is needed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_help_point_category_money_donation"
down_revision = "0010_help_point_category_more_types"
branch_labels = None
depends_on = None

OLD_CATEGORIES = (
    "Recolección de donaciones",
    "Remoción de escombros",
    "Labores de rescate",
    "Psicológica",
    "Médica",
    "Vivienda y Albergues",
    "Alimentación Comunitaria",
    "Voluntariado",
    "Donación de sangre",
)
NEW_CATEGORIES = OLD_CATEGORIES + ("Donación de dinero",)


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
