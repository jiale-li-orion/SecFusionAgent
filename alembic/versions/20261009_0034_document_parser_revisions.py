"""Allow immutable parser revisions for one fixed source observation.

Revision ID: 20261009_0034
Revises: 20261009_0033
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261009_0034"
down_revision: str | None = "20261009_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_document_revision_observation", "document_revisions", type_="unique")
    op.create_unique_constraint(
        "uq_document_revision_observation_parser",
        "document_revisions",
        ["observation_id", "parser_name", "parser_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_document_revision_observation_parser", "document_revisions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_document_revision_observation", "document_revisions", ["observation_id"]
    )
