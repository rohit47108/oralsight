"""Represent user-selected observation pairs without inventing model evidence.

Revision ID: 20260808_0005
Revises: 20260806_0004
Create Date: 2026-08-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260808_0005"
down_revision = "20260806_0004"
branch_labels = None
depends_on = None


proposal_origin = sa.Enum(
    "automatic_model",
    "user_selected",
    name="match_proposal_origin",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    with op.batch_alter_table("match_proposals") as batch:
        batch.add_column(
            sa.Column(
                "proposal_origin",
                proposal_origin,
                nullable=False,
                server_default="automatic_model",
            )
        )
        batch.alter_column("score", existing_type=sa.Float(), nullable=True)
        batch.alter_column("rank", existing_type=sa.Integer(), nullable=True)
        batch.create_check_constraint(
            "ck_match_proposal_origin_evidence",
            "(proposal_origin = 'automatic_model' AND score IS NOT NULL AND rank IS NOT NULL) "
            "OR (proposal_origin = 'user_selected' AND score IS NULL AND rank IS NULL)",
        )


def downgrade() -> None:
    match_proposals = sa.table(
        "match_proposals",
        sa.column("proposal_origin", sa.String(32)),
        sa.column("score", sa.Float()),
        sa.column("rank", sa.Integer()),
        sa.column("model_versions", sa.JSON()),
    )
    op.execute(
        match_proposals.update()
        .where(match_proposals.c.proposal_origin == "user_selected")
        .values(
            score=0.0,
            rank=1,
            model_versions={"selection": "user-selected-v1"},
        )
    )
    with op.batch_alter_table("match_proposals") as batch:
        batch.drop_constraint("ck_match_proposal_origin_evidence", type_="check")
        batch.alter_column("score", existing_type=sa.Float(), nullable=False)
        batch.alter_column("rank", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("proposal_origin")
