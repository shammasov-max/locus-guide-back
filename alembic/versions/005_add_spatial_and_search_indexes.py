"""add spatial and search indexes

Revision ID: 005_add_spatial_and_search_indexes
Revises: 004_add_user_roles
Create Date: 2025-12-25

"""
from alembic import op


revision = '005_add_spatial_and_search_indexes'
down_revision = '004_add_user_roles'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create spatial index on checkpoint location for efficient nearby search
    op.execute("""
        CREATE INDEX idx_checkpoints_location
        ON checkpoints
        USING GIST (location)
    """)

    # Create GIN indexes on HSTORE columns for faster text search
    op.execute("""
        CREATE INDEX idx_route_versions_title_gin
        ON route_versions
        USING GIN (title_i18n)
    """)

    op.execute("""
        CREATE INDEX idx_route_versions_summary_gin
        ON route_versions
        USING GIN (summary_i18n)
    """)


def downgrade() -> None:
    op.drop_index('idx_route_versions_summary_gin', table_name='route_versions')
    op.drop_index('idx_route_versions_title_gin', table_name='route_versions')
    op.drop_index('idx_checkpoints_location', table_name='checkpoints')
