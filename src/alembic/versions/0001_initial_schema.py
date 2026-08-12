"""Create the initial Dónde Ayudo PostgreSQL schema."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

NEED_STATUSES = ("NEEDS_HELP", "HELP_ON_THE_WAY", "COVERED")
_CATEGORY_NAMES = (
    ("Agua", "Alimentos y bebidas"),
    ("Bebidas hidratantes / electrolitos", "Alimentos y bebidas"),
    ("Alimentos", "Alimentos y bebidas"),
    ("Comida preparada", "Alimentos y bebidas"),
    ("Rescatistas", "Rescate y salud"),
    ("Personal médico", "Rescate y salud"),
    ("Primeros auxilios", "Rescate y salud"),
    ("Tapabocas", "Rescate y salud"),
    ("Guantes", "Rescate y salud"),
    ("Cascos", "Rescate y salud"),
    ("Linternas", "Rescate y salud"),
    ("Palas / picas", "Rescate y salud"),
    ("Herramientas de rescate", "Rescate y salud"),
    ("Cobijas", "Refugio"),
    ("Colchonetas", "Refugio"),
    ("Ropa", "Refugio"),
    ("Elementos de aseo", "Refugio"),
    ("Pañales", "Refugio"),
    ("Alojamiento", "Refugio"),
    ("Voluntarios", "Apoyo"),
    ("Transporte", "Apoyo"),
    ("Vehículos", "Apoyo"),
    ("Cargadores / baterías", "Apoyo"),
)
INITIAL_CATEGORIES = [
    {
        "id": uuid5(NAMESPACE_URL, f"donde-ayudo/category/{name}"),
        "nombre": name,
        "grupo": group,
        "es_global": True,
        "activo": True,
    }
    for name, group in _CATEGORY_NAMES
]


def uuid_column(name: str = "id") -> sa.Column[object]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=name == "id", nullable=False)


def upgrade() -> None:
    op.create_table(
        "help_points",
        uuid_column(),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("ciudad", sa.String(120), nullable=False),
        sa.Column("departamento", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("nombre_coordinador", sa.String(120), nullable=False),
        sa.Column("contacto_coordinador", sa.String(240), nullable=False),
        sa.Column("admin_token", sa.Text(), nullable=False, unique=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(sa.column("latitude").between(-90, 90), name="help_points_latitude_check"),
        sa.CheckConstraint(sa.column("longitude").between(-180, 180), name="help_points_longitude_check"),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("nombre")).between(1, 120),
            name="help_points_nombre_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("descripcion")).between(1, 1000),
            name="help_points_descripcion_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("ciudad")).between(1, 120),
            name="help_points_ciudad_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("departamento")).between(1, 120),
            name="help_points_departamento_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("nombre_coordinador")).between(1, 120),
            name="help_points_nombre_coordinador_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("contacto_coordinador")).between(1, 240),
            name="help_points_contacto_coordinador_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("admin_token")) >= 40,
            name="help_points_admin_token_check",
        ),
    )
    op.create_table(
        "need_categories",
        uuid_column(),
        sa.Column("nombre", sa.String(120), nullable=False, unique=True),
        sa.Column("grupo", sa.String(120), nullable=False),
        sa.Column("es_global", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("nombre")).between(1, 120),
            name="need_categories_nombre_check",
        ),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("grupo")).between(1, 120),
            name="need_categories_grupo_check",
        ),
    )
    op.create_table(
        "needs",
        uuid_column(),
        sa.Column("help_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("help_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("need_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("estado", sa.String(32), nullable=False, server_default=NEED_STATUSES[0]),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(sa.column("estado").in_(NEED_STATUSES), name="needs_estado_check"),
        sa.UniqueConstraint("help_point_id", "category_id", name="needs_help_point_category_unique"),
    )
    op.create_table(
        "commitments",
        uuid_column(),
        sa.Column("need_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("needs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("nota", sa.String(500), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            sa.func.char_length(sa.column("nombre")).between(1, 120),
            name="commitments_nombre_check",
        ),
        sa.CheckConstraint(
            sa.column("nota").is_(None) | (sa.func.char_length(sa.column("nota")) <= 500),
            name="commitments_nota_check",
        ),
    )
    op.create_index("help_points_activo_idx", "help_points", ["activo"])
    op.create_index("needs_help_point_id_idx", "needs", ["help_point_id"])
    op.create_index("needs_estado_idx", "needs", ["estado"])
    op.create_index("commitments_need_id_idx", "commitments", ["need_id"])
    op.bulk_insert(
        sa.table(
            "need_categories",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("nombre", sa.String()),
            sa.column("grupo", sa.String()),
            sa.column("es_global", sa.Boolean()),
            sa.column("activo", sa.Boolean()),
        ),
        INITIAL_CATEGORIES,
    )


def downgrade() -> None:
    op.drop_index("commitments_need_id_idx", table_name="commitments")
    op.drop_index("needs_estado_idx", table_name="needs")
    op.drop_index("needs_help_point_id_idx", table_name="needs")
    op.drop_index("help_points_activo_idx", table_name="help_points")
    op.drop_table("commitments")
    op.drop_table("needs")
    op.drop_table("need_categories")
    op.drop_table("help_points")
