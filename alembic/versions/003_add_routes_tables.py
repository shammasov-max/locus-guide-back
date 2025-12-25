"""Add routes tables

Revision ID: 003_routes
Revises: 002_cities
Create Date: 2025-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import HSTORE, JSONB, ARRAY, UUID


# revision identifiers, used by Alembic.
revision: str = "003_routes"
down_revision: Union[str, None] = "002_cities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable HSTORE extension
    op.execute("CREATE EXTENSION IF NOT EXISTS hstore")

    # Create ENUM types
    op.execute(
        "CREATE TYPE route_status AS ENUM ('draft', 'published', 'coming_soon', 'archived')"
    )
    op.execute(
        "CREATE TYPE route_version_status AS ENUM ('draft', 'review', 'published', 'superseded')"
    )
    op.execute(
        "CREATE TYPE audio_listen_status AS ENUM ('none', 'started', 'completed')"
    )
    op.execute(
        "CREATE TYPE completion_type AS ENUM ('manual', 'automatic')"
    )

    # Create routes table
    op.create_table(
        "routes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("city_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "coming_soon", "archived", name="route_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("published_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.geonameid"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("city_id", "slug"),
    )
    op.create_index("idx_routes_city_id", "routes", ["city_id"])
    op.create_index("idx_routes_status", "routes", ["status"])

    # Create route_versions table
    op.create_table(
        "route_versions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "review", "published", "superseded", name="route_version_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("title_i18n", HSTORE(), nullable=False),
        sa.Column("summary_i18n", HSTORE(), nullable=True),
        sa.Column("languages", ARRAY(sa.Text()), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("ascent_m", sa.Integer(), nullable=True),
        sa.Column("descent_m", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("path", Geography(geometry_type="LINESTRING", srid=4326), nullable=True),
        sa.Column("geojson", JSONB(), nullable=True),
        sa.Column("bbox", Geography(geometry_type="POLYGON", srid=4326), nullable=True),
        sa.Column("free_checkpoint_limit", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("price_currency", sa.String(3), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "version_no"),
    )
    op.create_index("idx_route_versions_path", "route_versions", ["path"], postgresql_using="gist")
    op.create_index("idx_route_versions_bbox", "route_versions", ["bbox"], postgresql_using="gist")

    # Add FK from routes.published_version_id to route_versions.id
    op.create_foreign_key(
        "fk_routes_published_version_id",
        "routes",
        "route_versions",
        ["published_version_id"],
        ["id"],
    )

    # Create checkpoints table
    op.create_table(
        "checkpoints",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("route_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("display_number", sa.Integer(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("source_point_id", sa.Integer(), nullable=True),
        sa.Column("title_i18n", HSTORE(), nullable=False),
        sa.Column("description_i18n", HSTORE(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("trigger_radius_m", sa.Integer(), server_default="25", nullable=False),
        sa.Column("is_free_preview", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["route_version_id"], ["route_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_version_id", "seq_no"),
    )
    op.create_index("idx_checkpoints_location", "checkpoints", ["location"], postgresql_using="gist")

    # Create visited_points table
    op.create_table(
        "visited_points",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("checkpoint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("visited", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("visited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "audio_status",
            sa.Enum("none", "started", "completed", name="audio_listen_status"),
            server_default="none",
            nullable=False,
        ),
        sa.Column("audio_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("audio_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "checkpoint_id"),
    )
    op.create_index(
        "idx_visited_points_user_updated",
        "visited_points",
        ["user_id", sa.text("updated_at DESC")],
    )
    op.create_index("idx_visited_points_checkpoint", "visited_points", ["checkpoint_id"])

    # Create user_active_routes table
    op.create_table(
        "user_active_routes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("locked_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "completion_type",
            sa.Enum("manual", "automatic", name="completion_type"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_version_id"], ["route_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "route_id"),
    )
    op.create_index("idx_user_active_routes_user_id", "user_active_routes", ["user_id"])
    op.create_index("idx_user_active_routes_route_id", "user_active_routes", ["route_id"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index("idx_user_active_routes_route_id", table_name="user_active_routes")
    op.drop_index("idx_user_active_routes_user_id", table_name="user_active_routes")
    op.drop_table("user_active_routes")

    op.drop_index("idx_visited_points_checkpoint", table_name="visited_points")
    op.drop_index("idx_visited_points_user_updated", table_name="visited_points")
    op.drop_table("visited_points")

    op.drop_index("idx_checkpoints_location", table_name="checkpoints")
    op.drop_table("checkpoints")

    # Drop FK constraint before dropping route_versions
    op.drop_constraint("fk_routes_published_version_id", "routes", type_="foreignkey")

    op.drop_index("idx_route_versions_bbox", table_name="route_versions")
    op.drop_index("idx_route_versions_path", table_name="route_versions")
    op.drop_table("route_versions")

    op.drop_index("idx_routes_status", table_name="routes")
    op.drop_index("idx_routes_city_id", table_name="routes")
    op.drop_table("routes")

    # Drop ENUM types
    op.execute("DROP TYPE completion_type")
    op.execute("DROP TYPE audio_listen_status")
    op.execute("DROP TYPE route_version_status")
    op.execute("DROP TYPE route_status")
