"""Widen alembic_version.version_num so long revision slugs fit.

Alembic's default version_num column is VARCHAR(32). This project's revision
IDs are the full descriptive filename slug (e.g.
`0004_help_point_optional_affected_city`, 38 characters), which exceeds that
default and made the `0003 -> 0004` upgrade fail in production with
`StringDataRightTruncation` on the `alembic_version` bookkeeping table itself
(not on any application table). Widening once, generously, avoids hitting
this again as migration names grow.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_widen_alembic_version"
down_revision = "0003_help_point_additional_areas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(32),
        type_=sa.String(500),
    )


def downgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(500),
        type_=sa.String(32),
    )
