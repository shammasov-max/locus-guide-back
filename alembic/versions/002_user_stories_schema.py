"""Add user stories schema requirements

Revision ID: 002_user_stories
Revises: 001_initial
Create Date: 2025-12-30

Implements:
- US-033: Draft GeoJSON for trips
- US-040: Audio URLs for checkpoints
- US-041: Languages as HSTORE (ready/not ready)
- US-011i: Selected character for users
- US-030: Notification preferences for wishes
- US-013b: User purchases table
- US-025-028: Achievements tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, HSTORE, UUID


# revision identifiers, used by Alembic.
revision: str = "002_user_stories"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== EXISTING TABLE MODIFICATIONS ====================

    # 1. routes.draft_geojson (US-033)
    op.add_column("routes", sa.Column("draft_geojson", JSONB(), nullable=True))

    # 2. route_versions.languages: TEXT[] -> HSTORE (US-041)
    # Convert existing array to HSTORE with all languages as "true"
    # Note: route_versions table represents versioned Route entities
    op.execute("""
        ALTER TABLE route_versions
        ALTER COLUMN languages TYPE HSTORE
        USING (
            CASE
                WHEN languages IS NULL THEN NULL::hstore
                ELSE (
                    SELECT hstore(array_agg(lang), array_agg('true'))
                    FROM unnest(languages) AS lang
                )
            END
        )
    """)

    # 3. checkpoints.audio_urls (US-040)
    op.add_column("checkpoints", sa.Column("audio_urls", HSTORE(), nullable=True))

    # 4. app_user.selected_character (US-011i)
    op.add_column(
        "app_user",
        sa.Column("selected_character", sa.Text(), server_default="cat", nullable=False),
    )

    # 5. wished_routes.notify_on_publish (US-030)
    # Note: wished_routes table represents user wishes for Trip entities
    op.add_column(
        "wished_routes",
        sa.Column("notify_on_publish", sa.Boolean(), server_default="true", nullable=False),
    )

    # 6. wanted_cities.notify_on_first_route (US-030)
    # Note: notify_on_first_route means notification when first Trip is published for wanted city
    op.add_column(
        "wanted_cities",
        sa.Column("notify_on_first_route", sa.Boolean(), server_default="true", nullable=False),
    )

    # ==================== NEW TABLES ====================

    # 7. user_purchases table (US-013b)
    # Note: route_id foreign key references trips (routes table represents Trip entities)
    op.create_table(
        "user_purchases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_transaction_id", sa.Text(), nullable=True),
        sa.Column("store_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "purchased_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "route_id", name="uq_user_purchase"),
    )
    op.create_index("idx_purchases_user", "user_purchases", ["user_id"])
    op.create_index("idx_purchases_route", "user_purchases", ["route_id"])

    # 8. achievements table (US-025-028)
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title_i18n", HSTORE(), nullable=False),
        sa.Column("description_i18n", HSTORE(), nullable=True),
        sa.Column("icon_url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_achievement_code"),
    )
    op.create_index("idx_achievements_category", "achievements", ["category"])

    # 9. user_achievements table (US-025-028)
    op.create_table(
        "user_achievements",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "achievement_id"),
    )
    op.create_index("idx_user_achievements_user", "user_achievements", ["user_id"])

    # ==================== SEED ACHIEVEMENTS DATA ====================
    # Note: Achievement descriptions reference "trips" conceptually (category='routes' is the table name)
    op.execute("""
        INSERT INTO achievements (code, title_i18n, description_i18n, category, threshold) VALUES
        ('first_steps', 'en => "First Steps", ru => "Первые шаги"', 'en => "Complete your first trip", ru => "Завершите свой первый маршрут"', 'routes', 1),
        ('curious', 'en => "Curious", ru => "Любопытный"', 'en => "Complete 5 trips", ru => "Завершите 5 маршрутов"', 'routes', 5),
        ('explorer', 'en => "Explorer", ru => "Исследователь"', 'en => "Complete 15 trips", ru => "Завершите 15 маршрутов"', 'routes', 15),
        ('traveler', 'en => "Traveler", ru => "Путешественник"', 'en => "Complete 30 trips", ru => "Завершите 30 маршрутов"', 'routes', 30),
        ('nomad', 'en => "Nomad", ru => "Номад"', 'en => "Complete 50 trips", ru => "Завершите 50 маршрутов"', 'routes', 50),
        ('road_legend', 'en => "Road Legend", ru => "Легенда дорог"', 'en => "Complete 100 trips", ru => "Завершите 100 маршрутов"', 'routes', 100),
        ('tourist', 'en => "Tourist", ru => "Турист"', 'en => "Visit 3 cities", ru => "Посетите 3 города"', 'cities', 3),
        ('cosmopolitan', 'en => "Cosmopolitan", ru => "Космополит"', 'en => "Visit 10 cities", ru => "Посетите 10 городов"', 'cities', 10),
        ('world_citizen', 'en => "World Citizen", ru => "Гражданин мира"', 'en => "Visit 25 cities", ru => "Посетите 25 городов"', 'cities', 25),
        ('city_collector', 'en => "City Collector", ru => "Коллекционер городов"', 'en => "Visit 50 cities", ru => "Посетите 50 городов"', 'cities', 50)
    """)


def downgrade() -> None:
    # Drop new tables
    op.drop_index("idx_user_achievements_user", table_name="user_achievements")
    op.drop_table("user_achievements")

    op.drop_index("idx_achievements_category", table_name="achievements")
    op.drop_table("achievements")

    op.drop_index("idx_purchases_route", table_name="user_purchases")
    op.drop_index("idx_purchases_user", table_name="user_purchases")
    op.drop_table("user_purchases")

    # Remove added columns
    op.drop_column("wanted_cities", "notify_on_first_route")
    op.drop_column("wished_routes", "notify_on_publish")
    op.drop_column("app_user", "selected_character")
    op.drop_column("checkpoints", "audio_urls")

    # Convert languages back to TEXT[]
    op.execute("""
        ALTER TABLE route_versions
        ALTER COLUMN languages TYPE TEXT[]
        USING (
            CASE
                WHEN languages IS NULL THEN NULL::text[]
                ELSE akeys(languages)
            END
        )
    """)

    op.drop_column("routes", "draft_geojson")
