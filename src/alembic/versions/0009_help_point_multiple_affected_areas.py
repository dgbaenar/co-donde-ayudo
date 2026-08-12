"""Move the affected destination area into a 1..N affected-areas table.

A help point may now target several affected areas at once, where each area pairs a required
department with an optional municipality/city (a null city means "the whole department"). Creates
`help_point_affected_areas`, backfills one row per existing help point from its former
`departamento_afectado`/`ciudad_afectada` columns, then drops those columns from `help_points`.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_help_point_multiple_affected_areas"
down_revision = "0008_help_point_multiple_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "help_point_affected_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "help_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("help_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("departamento", sa.String(120), nullable=False),
        sa.Column("municipio", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("departamento")).between(1, 120),
            name="help_point_affected_areas_departamento_check",
        ),
        sa.CheckConstraint(
            sa.column("municipio").is_(None)
            | sa.func.char_length(sa.column("municipio")).between(1, 120),
            name="help_point_affected_areas_municipio_check",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO help_point_affected_areas "
            "(id, help_point_id, departamento, municipio) "
            "SELECT gen_random_uuid(), id, departamento_afectado, ciudad_afectada "
            "FROM help_points"
        )
    )
    op.drop_constraint(
        "help_points_departamento_afectado_check", "help_points", type_="check"
    )
    op.drop_constraint(
        "help_points_ciudad_afectada_check", "help_points", type_="check"
    )
    op.drop_column("help_points", "departamento_afectado")
    op.drop_column("help_points", "ciudad_afectada")


def downgrade() -> None:
    op.add_column("help_points", sa.Column("departamento_afectado", sa.String(120), nullable=True))
    op.add_column("help_points", sa.Column("ciudad_afectada", sa.String(120), nullable=True))
    op.execute(
        sa.text(
            "UPDATE help_points AS hp SET "
            "departamento_afectado = area.departamento, "
            "ciudad_afectada = area.municipio "
            "FROM ("
            "SELECT DISTINCT ON (help_point_id) help_point_id, departamento, municipio "
            "FROM help_point_affected_areas ORDER BY help_point_id, id"
            ") AS area "
            "WHERE area.help_point_id = hp.id"
        )
    )
    op.alter_column("help_points", "departamento_afectado", nullable=False)
    op.create_check_constraint(
        "help_points_departamento_afectado_check",
        "help_points",
        sa.func.char_length(sa.column("departamento_afectado")).between(1, 120),
    )
    op.create_check_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        sa.column("ciudad_afectada").is_(None)
        | sa.func.char_length(sa.column("ciudad_afectada")).between(1, 120),
    )
    op.drop_table("help_point_affected_areas")
