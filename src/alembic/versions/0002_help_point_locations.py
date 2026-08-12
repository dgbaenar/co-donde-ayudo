"""Add help-point locations and safely promote emergency categories.

Category policy: upgrade upserts by name without replacing an existing row's ID. Downgrade removes
only the deterministic IDs introduced by this migration when no need references them; name
collisions with another ID and referenced deterministic rows are preserved.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision = "0002_help_point_locations"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

_CATEGORY_NAMES = (
    ("Remoción de escombros", "Apoyo"),
    ("Maquinaria pesada", "Apoyo"),
)
NEW_CATEGORIES = [
    {
        "id": uuid5(NAMESPACE_URL, f"donde-ayudo/category/{name}"),
        "nombre": name,
        "grupo": group,
        "es_global": True,
        "activo": True,
    }
    for name, group in _CATEGORY_NAMES
]


def category_upsert() -> sa.TextClause:
    values = ", ".join(
        f"('{category['id']}'::uuid, '{category['nombre']}', "
        f"'{category['grupo']}', TRUE, TRUE)"
        for category in NEW_CATEGORIES
    )
    return sa.text(
        "INSERT INTO need_categories (id, nombre, grupo, es_global, activo) "
        f"VALUES {values} "
        "ON CONFLICT (nombre) DO UPDATE SET "
        "grupo = EXCLUDED.grupo, es_global = TRUE, activo = TRUE"
    )


def upgrade() -> None:
    op.add_column(
        "help_points",
        sa.Column("direccion", sa.String(240), nullable=True),
    )
    op.add_column(
        "help_points",
        sa.Column("ciudad_afectada", sa.String(120), nullable=True),
    )
    op.add_column(
        "help_points",
        sa.Column("departamento_afectado", sa.String(120), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE help_points "
            "SET ciudad_afectada = ciudad, departamento_afectado = departamento"
        )
    )
    op.alter_column("help_points", "ciudad_afectada", nullable=False)
    op.alter_column("help_points", "departamento_afectado", nullable=False)
    op.create_check_constraint(
        "help_points_direccion_check",
        "help_points",
        sa.column("direccion").is_(None)
        | sa.func.char_length(sa.column("direccion")).between(1, 240),
    )
    op.create_check_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        sa.func.char_length(sa.column("ciudad_afectada")).between(1, 120),
    )
    op.create_check_constraint(
        "help_points_departamento_afectado_check",
        "help_points",
        sa.func.char_length(sa.column("departamento_afectado")).between(1, 120),
    )
    op.execute(category_upsert())


def downgrade() -> None:
    category_ids = ", ".join(
        f"'{category['id']}'::uuid" for category in NEW_CATEGORIES
    )
    op.execute(
        sa.text(
            "DELETE FROM need_categories AS category "
            f"WHERE category.id IN ({category_ids}) "
            "AND NOT EXISTS ("
            "SELECT 1 FROM needs WHERE needs.category_id = category.id"
            ")"
        )
    )
    op.drop_constraint(
        "help_points_departamento_afectado_check",
        "help_points",
        type_="check",
    )
    op.drop_constraint(
        "help_points_ciudad_afectada_check",
        "help_points",
        type_="check",
    )
    op.drop_constraint(
        "help_points_direccion_check",
        "help_points",
        type_="check",
    )
    op.drop_column("help_points", "departamento_afectado")
    op.drop_column("help_points", "ciudad_afectada")
    op.drop_column("help_points", "direccion")
