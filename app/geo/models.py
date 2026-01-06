from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.database import Base

if TYPE_CHECKING:
    from app.tours.models import Tour, WatchList


class Country(Base):
    __tablename__ = "countries"

    iso: Mapped[str] = mapped_column(String(2), primary_key=True)
    iso3: Mapped[str | None] = mapped_column(String(3), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capital: Mapped[str | None] = mapped_column(String(200), nullable=True)
    continent: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Relationships
    cities: Mapped[list["City"]] = relationship("City", back_populates="country")


class City(Base):
    __tablename__ = "cities"

    geonameid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asciiname: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.iso"), nullable=False, index=True
    )
    admin1_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    population: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    timezone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geom: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False, index=True
    )

    # Relationships
    country: Mapped["Country"] = relationship("Country", back_populates="cities")
    alternate_names: Mapped[list["AlternateName"]] = relationship(
        "AlternateName", back_populates="city", cascade="all, delete-orphan"
    )
    search_index: Mapped[list["CitySearchIndex"]] = relationship(
        "CitySearchIndex", back_populates="city", cascade="all, delete-orphan"
    )
    tours: Mapped[list["Tour"]] = relationship("Tour", back_populates="city")
    watchers: Mapped[list["WatchList"]] = relationship("WatchList", back_populates="city")


class AlternateName(Base):
    __tablename__ = "alternate_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geonameid: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.geonameid", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    city: Mapped["City"] = relationship("City", back_populates="alternate_names")


class CitySearchIndex(Base):
    __tablename__ = "city_search_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geonameid: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.geonameid", ondelete="CASCADE"), nullable=False, index=True
    )
    search_term: Mapped[str] = mapped_column(String(400), nullable=False)
    search_term_lower: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(7), nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    city: Mapped["City"] = relationship("City", back_populates="search_index")
