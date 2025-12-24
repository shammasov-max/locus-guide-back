from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.database import Base


class Country(Base):
    """Country information from countryInfo.txt"""
    __tablename__ = "countries"

    iso = Column(String(2), primary_key=True)
    iso3 = Column(String(3))
    name = Column(String(200), nullable=False)
    capital = Column(String(200))
    continent = Column(String(2))

    # Relationships
    cities = relationship("City", back_populates="country")


class City(Base):
    """Main city data from cities15000.txt"""
    __tablename__ = "cities"

    geonameid = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    asciiname = Column(String(200))
    country_code = Column(String(2), ForeignKey("countries.iso"), nullable=False)
    admin1_code = Column(String(20))
    population = Column(Integer, default=0)
    timezone = Column(String(40))
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    # Relationships
    country = relationship("Country", back_populates="cities")
    alternate_names = relationship("AlternateName", back_populates="city", lazy="selectin")
    search_index = relationship("CitySearchIndex", back_populates="city")

    __table_args__ = (
        Index("idx_cities_country", "country_code"),
        Index("idx_cities_population", population.desc()),
    )


class AlternateName(Base):
    """Alternate names for cities in different languages"""
    __tablename__ = "alternate_names"

    id = Column(Integer, primary_key=True)
    geonameid = Column(Integer, ForeignKey("cities.geonameid", ondelete="CASCADE"), nullable=False)
    language = Column(String(7), nullable=False)
    name = Column(String(400), nullable=False)
    is_preferred = Column(Boolean, default=False)
    is_short = Column(Boolean, default=False)

    # Relationships
    city = relationship("City", back_populates="alternate_names")

    __table_args__ = (
        Index("idx_alt_names_geonameid", "geonameid"),
        Index("idx_alt_names_language", "language"),
    )


class CitySearchIndex(Base):
    """Denormalized search index for fast prefix matching"""
    __tablename__ = "city_search_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    geonameid = Column(Integer, ForeignKey("cities.geonameid", ondelete="CASCADE"), nullable=False)
    search_term = Column(String(400), nullable=False)
    search_term_lower = Column(String(400), nullable=False)
    language = Column(String(7))
    source = Column(String(20))  # 'name', 'asciiname', 'alternate'

    # Relationships
    city = relationship("City", back_populates="search_index")

    __table_args__ = (
        Index("idx_search_geonameid", "geonameid"),
        Index("idx_search_prefix", "search_term_lower", postgresql_ops={"search_term_lower": "text_pattern_ops"}),
    )
