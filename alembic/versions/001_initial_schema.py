"""Initial schema - squashed from all migrations

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry, Geography
from sqlalchemy.dialects.postgresql import HSTORE, JSONB, ARRAY, UUID, ENUM


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS hstore")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create ENUM types explicitly before tables
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'editor', 'admin')")
    op.execute("CREATE TYPE route_status AS ENUM ('draft', 'published', 'coming_soon', 'archived')")
    op.execute("CREATE TYPE route_version_status AS ENUM ('draft', 'review', 'published', 'superseded')")
    op.execute("CREATE TYPE audio_listen_status AS ENUM ('none', 'started', 'completed')")
    op.execute("CREATE TYPE completion_type AS ENUM ('manual', 'automatic')")

    # ==================== AUTH TABLES ====================

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
        sa.Column(
            "role",
            ENUM("user", "editor", "admin", name="user_role", create_type=False),
            server_default="user",
            nullable=False,
        ),
        sa.CheckConstraint("units IN ('metric', 'imperial')", name="check_units"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)
    op.create_index("idx_app_user_role", "app_user", ["role"])

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
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_subject", name="uq_provider_subject"
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
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

    # ==================== CITIES TABLES ====================

    # Create countries table
    op.create_table(
        "countries",
        sa.Column("iso", sa.String(2), nullable=False),
        sa.Column("iso3", sa.String(3), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capital", sa.String(200), nullable=True),
        sa.Column("continent", sa.String(2), nullable=True),
        sa.PrimaryKeyConstraint("iso"),
    )

    # Create cities table with PostGIS geometry
    op.create_table(
        "cities",
        sa.Column("geonameid", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asciiname", sa.String(200), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("admin1_code", sa.String(20), nullable=True),
        sa.Column("population", sa.Integer(), server_default="0", nullable=True),
        sa.Column("timezone", sa.String(40), nullable=True),
        sa.Column(
            "geom", Geometry(geometry_type="POINT", srid=4326), nullable=False
        ),
        sa.ForeignKeyConstraint(["country_code"], ["countries.iso"]),
        sa.PrimaryKeyConstraint("geonameid"),
    )
    # Note: GeoAlchemy2 may auto-create spatial indexes; using IF NOT EXISTS
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cities_geom ON cities USING GIST (geom)"
    )
    op.create_index("idx_cities_country", "cities", ["country_code"])
    op.create_index(
        "idx_cities_population",
        "cities",
        ["population"],
        postgresql_ops={"population": "DESC"},
    )

    # Create alternate_names table
    op.create_table(
        "alternate_names",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("geonameid", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(7), nullable=False),
        sa.Column("name", sa.String(400), nullable=False),
        sa.Column(
            "is_preferred", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("is_short", sa.Boolean(), server_default="false", nullable=True),
        sa.ForeignKeyConstraint(
            ["geonameid"], ["cities.geonameid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alt_names_geonameid", "alternate_names", ["geonameid"])
    op.create_index("idx_alt_names_language", "alternate_names", ["language"])

    # Create city_search_index table
    op.create_table(
        "city_search_index",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("geonameid", sa.Integer(), nullable=False),
        sa.Column("search_term", sa.String(400), nullable=False),
        sa.Column("search_term_lower", sa.String(400), nullable=False),
        sa.Column("language", sa.String(7), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(
            ["geonameid"], ["cities.geonameid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_search_geonameid", "city_search_index", ["geonameid"])
    op.execute(
        "CREATE INDEX idx_search_prefix ON city_search_index (search_term_lower text_pattern_ops)"
    )

    # ==================== ROUTES TABLES ====================

    # Create routes table
    op.create_table(
        "routes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("city_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "status",
            ENUM("draft", "published", "coming_soon", "archived", name="route_status", create_type=False),
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
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            ENUM("draft", "review", "published", "superseded", name="route_version_status", create_type=False),
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
        sa.Column(
            "path", Geography(geometry_type="LINESTRING", srid=4326), nullable=True
        ),
        sa.Column("geojson", JSONB(), nullable=True),
        sa.Column(
            "bbox", Geography(geometry_type="POLYGON", srid=4326), nullable=True
        ),
        sa.Column(
            "free_checkpoint_limit", sa.Integer(), server_default="0", nullable=False
        ),
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
    # GeoAlchemy2 may auto-create spatial indexes; using IF NOT EXISTS
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_route_versions_path ON route_versions USING GIST (path)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_route_versions_bbox ON route_versions USING GIST (bbox)"
    )
    op.execute(
        "CREATE INDEX idx_route_versions_title_gin ON route_versions USING GIN (title_i18n)"
    )
    op.execute(
        "CREATE INDEX idx_route_versions_summary_gin ON route_versions USING GIN (summary_i18n)"
    )

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
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("route_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("display_number", sa.Integer(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("source_point_id", sa.Integer(), nullable=True),
        sa.Column("title_i18n", HSTORE(), nullable=False),
        sa.Column("description_i18n", HSTORE(), nullable=True),
        sa.Column(
            "location", Geography(geometry_type="POINT", srid=4326), nullable=False
        ),
        sa.Column(
            "trigger_radius_m", sa.Integer(), server_default="25", nullable=False
        ),
        sa.Column(
            "is_free_preview", sa.Boolean(), server_default="false", nullable=False
        ),
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
        sa.ForeignKeyConstraint(
            ["route_version_id"], ["route_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_version_id", "seq_no"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_checkpoints_location ON checkpoints USING GIST (location)"
    )

    # Create visited_points table
    op.create_table(
        "visited_points",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("checkpoint_id", UUID(as_uuid=True), nullable=False),
        sa.Column("visited", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("visited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "audio_status",
            ENUM("none", "started", "completed", name="audio_listen_status", create_type=False),
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
        sa.ForeignKeyConstraint(
            ["checkpoint_id"], ["checkpoints.id"], ondelete="CASCADE"
        ),
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
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
            ENUM("manual", "automatic", name="completion_type", create_type=False),
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

    # ==================== WISHES TABLES ====================

    # Create wished_routes table
    op.create_table(
        "wished_routes",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "route_id"),
    )
    op.execute(
        "CREATE INDEX idx_wished_routes_route_active ON wished_routes (route_id) WHERE is_active = true"
    )
    op.execute(
        "CREATE INDEX idx_wished_routes_user_active ON wished_routes (user_id) WHERE is_active = true"
    )

    # Create wanted_cities table
    op.create_table(
        "wanted_cities",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("geonameid", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["geonameid"], ["cities.geonameid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "geonameid"),
    )
    op.execute(
        "CREATE INDEX idx_wanted_cities_city_active ON wanted_cities (geonameid) WHERE is_active = true"
    )
    op.execute(
        "CREATE INDEX idx_wanted_cities_user_active ON wanted_cities (user_id) WHERE is_active = true"
    )


def downgrade() -> None:
    # Drop wishes tables
    op.drop_index("idx_wanted_cities_user_active", table_name="wanted_cities")
    op.drop_index("idx_wanted_cities_city_active", table_name="wanted_cities")
    op.drop_table("wanted_cities")

    op.drop_index("idx_wished_routes_user_active", table_name="wished_routes")
    op.drop_index("idx_wished_routes_route_active", table_name="wished_routes")
    op.drop_table("wished_routes")

    # Drop routes tables
    op.drop_index("idx_user_active_routes_route_id", table_name="user_active_routes")
    op.drop_index("idx_user_active_routes_user_id", table_name="user_active_routes")
    op.drop_table("user_active_routes")

    op.drop_index("idx_visited_points_checkpoint", table_name="visited_points")
    op.drop_index("idx_visited_points_user_updated", table_name="visited_points")
    op.drop_table("visited_points")

    op.drop_index("idx_checkpoints_location", table_name="checkpoints")
    op.drop_table("checkpoints")

    op.drop_constraint("fk_routes_published_version_id", "routes", type_="foreignkey")

    op.drop_index("idx_route_versions_summary_gin", table_name="route_versions")
    op.drop_index("idx_route_versions_title_gin", table_name="route_versions")
    op.drop_index("idx_route_versions_bbox", table_name="route_versions")
    op.drop_index("idx_route_versions_path", table_name="route_versions")
    op.drop_table("route_versions")

    op.drop_index("idx_routes_status", table_name="routes")
    op.drop_index("idx_routes_city_id", table_name="routes")
    op.drop_table("routes")

    # Drop cities tables
    op.drop_index("idx_search_prefix", table_name="city_search_index")
    op.drop_index("idx_search_geonameid", table_name="city_search_index")
    op.drop_table("city_search_index")

    op.drop_index("idx_alt_names_language", table_name="alternate_names")
    op.drop_index("idx_alt_names_geonameid", table_name="alternate_names")
    op.drop_table("alternate_names")

    op.drop_index("idx_cities_population", table_name="cities")
    op.drop_index("idx_cities_country", table_name="cities")
    op.drop_index("idx_cities_geom", table_name="cities")
    op.drop_table("cities")

    op.drop_table("countries")

    # Drop auth tables
    op.drop_table("password_reset_token")
    op.drop_table("refresh_token")
    op.drop_index("idx_auth_identity_user", table_name="auth_identity")
    op.drop_table("auth_identity")
    op.drop_index("idx_app_user_role", table_name="app_user")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_table("app_user")

    # Drop ENUM types
    op.execute("DROP TYPE completion_type")
    op.execute("DROP TYPE audio_listen_status")
    op.execute("DROP TYPE route_version_status")
    op.execute("DROP TYPE route_status")
    op.execute("DROP TYPE user_role")
