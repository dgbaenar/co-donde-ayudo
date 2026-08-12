"""Add a required category classification to the help point itself.

`categoria` (`category`) classifies the help point itself (recolección de donaciones, remoción de
escombros, or labores de rescate) — a fixed, single-value field distinct from `need_categories`,
which classifies individual needs and is unaffected by this migration. Existing rows predate this
field, so this migration backfills every pre-existing row with "Labores de rescate" before
enforcing NOT NULL, following the same add-column/backfill/alter-column-not-null sequence used by
`0002_help_point_locations` for `ciudad_afectada`/`departamento_afectado`.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_help_point_category"
down_revision = "0006_help_point_important_links"
branch_labels = None
depends_on = None

CATEGORIES = ("Recolección de donaciones", "Remoción de escombros", "Labores de rescate")
BACKFILL_CATEGORY = "Labores de rescate"


def upgrade() -> None:
    op.add_column(
        "help_points",
        sa.Column("categoria", sa.String(50), nullable=True),
    )
    op.execute(
        sa.text(f"UPDATE help_points SET categoria = '{BACKFILL_CATEGORY}' WHERE categoria IS NULL")
    )
    op.alter_column("help_points", "categoria", nullable=False)
    op.create_check_constraint(
        "help_points_categoria_check",
        "help_points",
        sa.column("categoria").in_(CATEGORIES),
    )


def downgrade() -> None:
    op.drop_constraint(
        "help_points_categoria_check",
        "help_points",
        type_="check",
    )
    op.drop_column("help_points", "categoria")
