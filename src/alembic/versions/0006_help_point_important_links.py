"""Add a list of important links (URLs only) to help points.

`enlaces_importantes` (`important_links`) is a plain array of URLs the coordinator can define
when creating the help point, shown as-is on the public view. Domain validation (in
`backend.domain.models.CreateHelpPoint`) already restricts entries to `http://`/`https://` URLs
between 1 and 500 characters, so no database-level check constraint is added here.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_help_point_important_links"
down_revision = "0005_help_point_optional_affected_city"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "help_points",
        sa.Column(
            "enlaces_importantes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("help_points", "enlaces_importantes")
