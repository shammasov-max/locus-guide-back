"""Initial auth tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create app_user table
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("locale_pref", sa.Text(), nullable=True),
        sa.Column("ui_lang", sa.Text(), nullable=True),
        sa.Column("audio_lang", sa.Text(), nullable=True),
        sa.Column("units", sa.Text(), server_default="metric", nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("units IN ('metric', 'imperial')", name="check_units"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)

    # Create auth_identity table
    op.create_table(
        "auth_identity",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column(
            "email_verified", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("provider IN ('google', 'email')", name="check_provider"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
    )
    op.create_index("idx_auth_identity_user", "auth_identity", ["user_id"])

    # Create refresh_token table
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_refresh_token_user", "refresh_token", ["user_id"])
    op.create_index("idx_refresh_token_expires", "refresh_token", ["expires_at"])

    # Create password_reset_token table
    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("identity_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["auth_identity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("password_reset_token")
    op.drop_table("refresh_token")
    op.drop_index("idx_auth_identity_user", table_name="auth_identity")
    op.drop_table("auth_identity")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_table("app_user")
