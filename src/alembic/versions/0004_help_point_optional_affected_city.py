"""Make the affected city/municipality optional on help points.

`ciudad_afectada` (`affected_city`) becomes nullable. `NULL` means "the whole affected
department", not a specific municipality. `departamento_afectado` (`affected_department`)
remains mandatory and is unchanged by this migration.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_help_point_optional_affected_city"
down_revision = "0003_help_point_additional_areas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        type_="check",
    )
    op.alter_column("help_points", "ciudad_afectada", nullable=True)
    op.create_check_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        sa.column("ciudad_afectada").is_(None)
        | sa.func.char_length(sa.column("ciudad_afectada")).between(1, 120),
    )


def downgrade() -> None:
    op.drop_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        type_="check",
    )
    op.alter_column("help_points", "ciudad_afectada", nullable=False)
    op.create_check_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        sa.func.char_length(sa.column("ciudad_afectada")).between(1, 120),
    )
