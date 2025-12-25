"""add user roles

Revision ID: 004_add_user_roles
Revises: 003_add_routes_tables
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa


revision = '004_add_user_roles'
down_revision = '003_add_routes_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_role enum
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'editor', 'admin')")

    # Add role column with default 'user'
    op.add_column('app_user',
        sa.Column('role', sa.Enum('user', 'editor', 'admin', name='user_role'),
                  nullable=False, server_default='user')
    )

    # Create index on role for filtering
    op.create_index('idx_app_user_role', 'app_user', ['role'])


def downgrade() -> None:
    op.drop_index('idx_app_user_role', table_name='app_user')
    op.drop_column('app_user', 'role')
    op.execute("DROP TYPE user_role")
