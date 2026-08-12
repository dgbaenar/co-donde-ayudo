"""Add an optional free-text field for additional affected areas.

This field is a plain string describing other zones the help point's aid may reach besides the
primary affected department/municipality, which remain mandatory (`affected_department` and
`affected_city` are unchanged by this migration). No structure, filtering, or second map is
introduced.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_help_point_additional_areas"
down_revision = "0002_help_point_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "help_points",
        sa.Column("zonas_adicionales", sa.String(500), nullable=True),
    )
    op.create_check_constraint(
        "help_points_zonas_adicionales_check",
        "help_points",
        sa.column("zonas_adicionales").is_(None)
        | sa.func.char_length(sa.column("zonas_adicionales")).between(1, 500),
    )


def downgrade() -> None:
    op.drop_constraint(
        "help_points_zonas_adicionales_check",
        "help_points",
        type_="check",
    )
    op.drop_column("help_points", "zonas_adicionales")
