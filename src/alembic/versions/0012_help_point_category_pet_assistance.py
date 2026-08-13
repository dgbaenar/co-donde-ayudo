"""Widen the help point category check constraint with pet assistance.

`categoria` (`category`) classifies the help point itself. This adds one new allowed value —
Ayuda para mascotas — alongside the ten existing ones. No existing row's value changes; this only
widens the `IN (...)` list that `help_points_categoria_check` allows, so no backfill is needed.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_help_point_category_pet_assistance"
down_revision = "0011_help_point_category_money_donation"
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
    "Donación de dinero",
)
NEW_CATEGORIES = OLD_CATEGORIES + ("Ayuda para mascotas",)


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
