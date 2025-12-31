"""SQLAlchemy models for user wishes (tours) and wants (cities)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WishedRoute(Base):
    """User's wish for a coming_soon tour.

    Tracks user interest in tours that are not yet published.
    Used for:
    - Notification when tour becomes available
    - Analytics on most anticipated tours
    """
    __tablename__ = "wished_routes"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tour_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # US-030: Notification preference for tour publish
    notify_on_publish: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    tour: Mapped["Tour"] = relationship()  # type: ignore

    __table_args__ = (
        Index(
            "idx_wished_routes_route_active",
            "tour_id",
            postgresql_where="is_active = true",
        ),
        Index(
            "idx_wished_routes_user_active",
            "user_id",
            postgresql_where="is_active = true",
        ),
    )


class WantedCity(Base):
    """User's want for tours in a city.

    Tracks user interest in cities that don't have tours yet.
    Used for:
    - Notification when first tour is added to city
    - Analytics on most wanted cities for expansion
    """
    __tablename__ = "wanted_cities"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    geonameid: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cities.geonameid", ondelete="CASCADE"),
        primary_key=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    city: Mapped["City"] = relationship()  # type: ignore

    __table_args__ = (
        Index(
            "idx_wanted_cities_city_active",
            "geonameid",
            postgresql_where="is_active = true",
        ),
        Index(
            "idx_wanted_cities_user_active",
            "user_id",
            postgresql_where="is_active = true",
        ),
    )
