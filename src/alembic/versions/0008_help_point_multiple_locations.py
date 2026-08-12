"""Move the single physical location into a 1..N locations table.

Creates `help_point_locations`, backfills one row per existing help point from its former
`direccion`/`ciudad`/`departamento`/`latitude`/`longitude` columns, then drops those columns from
`help_points`. `ciudad_afectada`/`departamento_afectado` (the affected area) are unrelated and
remain untouched.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_help_point_multiple_locations"
down_revision = "0007_help_point_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "help_point_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "help_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("help_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direccion", sa.String(240), nullable=True),
        sa.Column("ciudad", sa.String(120), nullable=False),
        sa.Column("departamento", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            sa.column("direccion").is_(None)
            | sa.func.char_length(sa.column("direccion")).between(1, 240),
            name="help_point_locations_direccion_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("ciudad")).between(1, 120),
            name="help_point_locations_ciudad_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("departamento")).between(1, 120),
            name="help_point_locations_departamento_check",
        ),
        sa.CheckConstraint(
            sa.column("latitude").between(-90, 90),
            name="help_point_locations_latitude_check",
        ),
        sa.CheckConstraint(
            sa.column("longitude").between(-180, 180),
            name="help_point_locations_longitude_check",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO help_point_locations "
            "(id, help_point_id, direccion, ciudad, departamento, latitude, longitude) "
            "SELECT gen_random_uuid(), id, direccion, ciudad, departamento, latitude, longitude "
            "FROM help_points"
        )
    )
    op.drop_constraint("help_points_latitude_check", "help_points", type_="check")
    op.drop_constraint("help_points_longitude_check", "help_points", type_="check")
    op.drop_constraint("help_points_ciudad_check", "help_points", type_="check")
    op.drop_constraint("help_points_departamento_check", "help_points", type_="check")
    op.drop_constraint("help_points_direccion_check", "help_points", type_="check")
    op.drop_column("help_points", "direccion")
    op.drop_column("help_points", "ciudad")
    op.drop_column("help_points", "departamento")
    op.drop_column("help_points", "latitude")
    op.drop_column("help_points", "longitude")


def downgrade() -> None:
    op.add_column("help_points", sa.Column("direccion", sa.String(240), nullable=True))
    op.add_column("help_points", sa.Column("ciudad", sa.String(120), nullable=True))
    op.add_column("help_points", sa.Column("departamento", sa.String(120), nullable=True))
    op.add_column("help_points", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("help_points", sa.Column("longitude", sa.Float(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE help_points AS hp SET "
            "direccion = loc.direccion, "
            "ciudad = loc.ciudad, "
            "departamento = loc.departamento, "
            "latitude = loc.latitude, "
            "longitude = loc.longitude "
            "FROM ("
            "SELECT DISTINCT ON (help_point_id) help_point_id, direccion, ciudad, "
            "departamento, latitude, longitude "
            "FROM help_point_locations ORDER BY help_point_id, id"
            ") AS loc "
            "WHERE loc.help_point_id = hp.id"
        )
    )
    op.alter_column("help_points", "ciudad", nullable=False)
    op.alter_column("help_points", "departamento", nullable=False)
    op.alter_column("help_points", "latitude", nullable=False)
    op.alter_column("help_points", "longitude", nullable=False)
    op.create_check_constraint(
        "help_points_ciudad_check",
        "help_points",
        sa.func.char_length(sa.column("ciudad")).between(1, 120),
    )
    op.create_check_constraint(
        "help_points_departamento_check",
        "help_points",
        sa.func.char_length(sa.column("departamento")).between(1, 120),
    )
    op.create_check_constraint(
        "help_points_direccion_check",
        "help_points",
        sa.column("direccion").is_(None)
        | sa.func.char_length(sa.column("direccion")).between(1, 240),
    )
    op.create_check_constraint(
        "help_points_latitude_check",
        "help_points",
        sa.column("latitude").between(-90, 90),
    )
    op.create_check_constraint(
        "help_points_longitude_check",
        "help_points",
        sa.column("longitude").between(-180, 180),
    )
    op.drop_table("help_point_locations")
