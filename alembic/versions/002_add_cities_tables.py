"""Add cities tables for autocomplete

Revision ID: 002_cities
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "002_cities"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.ForeignKeyConstraint(["country_code"], ["countries.iso"]),
        sa.PrimaryKeyConstraint("geonameid"),
    )
    op.create_index("idx_cities_geom", "cities", ["geom"], postgresql_using="gist")
    op.create_index("idx_cities_country", "cities", ["country_code"])
    op.create_index("idx_cities_population", "cities", ["population"], postgresql_ops={"population": "DESC"})

    # Create alternate_names table
    op.create_table(
        "alternate_names",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("geonameid", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(7), nullable=False),
        sa.Column("name", sa.String(400), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("is_short", sa.Boolean(), server_default="false", nullable=True),
        sa.ForeignKeyConstraint(["geonameid"], ["cities.geonameid"], ondelete="CASCADE"),
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
        sa.ForeignKeyConstraint(["geonameid"], ["cities.geonameid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_search_geonameid", "city_search_index", ["geonameid"])
    # Create text_pattern_ops index for prefix search
    op.execute(
        "CREATE INDEX idx_search_prefix ON city_search_index (search_term_lower text_pattern_ops)"
    )


def downgrade() -> None:
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
