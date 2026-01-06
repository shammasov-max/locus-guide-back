from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, HSTORE, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.database import Base

if TYPE_CHECKING:
    from app.auth.models import Account
    from app.geo.models import City


class Tour(Base):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cities.geonameid"), nullable=True, index=True
    )
    active_route_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("routes.id"), nullable=True
    )
    draft_route_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("routes.id"), nullable=True
    )
    title_i18n: Mapped[dict] = mapped_column(HSTORE, nullable=False)
    description_i18n: Mapped[dict | None] = mapped_column(HSTORE, nullable=True)
    price_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_coming_soon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=True
    )

    # Relationships
    city: Mapped["City"] = relationship("City", back_populates="tours")
    active_route: Mapped["Route | None"] = relationship(
        "Route",
        foreign_keys=[active_route_id],
        post_update=True,
    )
    draft_route: Mapped["Route | None"] = relationship(
        "Route",
        foreign_keys=[draft_route_id],
        post_update=True,
    )
    routes: Mapped[list["Route"]] = relationship(
        "Route",
        back_populates="tour",
        foreign_keys="Route.tour_id",
        cascade="all, delete-orphan",
    )
    await_list: Mapped[list["AwaitList"]] = relationship(
        "AwaitList", back_populates="tour", cascade="all, delete-orphan"
    )
    bundle_associations: Mapped[list["BundleToTour"]] = relationship(
        "BundleToTour", back_populates="tour"
    )
    entitlements: Mapped[list["Entitlement"]] = relationship(
        "Entitlement", back_populates="tour"
    )


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tour_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    geojson: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    waypoint_guids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID), nullable=True)
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elevation_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    languages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    tour: Mapped["Tour"] = relationship(
        "Tour", back_populates="routes", foreign_keys=[tour_id]
    )
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="route")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Waypoint(Base):
    __tablename__ = "waypoints"

    guid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    coordinates: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    description_i18n: Mapped[dict | None] = mapped_column(HSTORE, nullable=True)
    is_checkpoint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=False
    )

    # Relationships
    created_by_user: Mapped["Account"] = relationship("Account", back_populates="waypoints")


class Run(Base):
    __tablename__ = "runs"

    guid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.id"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_checkpoints: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID), nullable=True, default=[]
    )
    is_simulation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_position: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    # Relationships
    route: Mapped["Route"] = relationship("Route", back_populates="runs")
    account: Mapped["Account"] = relationship("Account", back_populates="runs")


class AwaitList(Base):
    __tablename__ = "await_list"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tour_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="await_list")
    tour: Mapped["Tour"] = relationship("Tour", back_populates="await_list")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class WatchList(Base):
    __tablename__ = "watch_list"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.geonameid", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="watch_list")
    city: Mapped["City"] = relationship("City", back_populates="watchers")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Bundle(Base):
    __tablename__ = "bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_i18n: Mapped[dict] = mapped_column(HSTORE, nullable=False)
    description_i18n: Mapped[dict | None] = mapped_column(HSTORE, nullable=True)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    tour_associations: Mapped[list["BundleToTour"]] = relationship(
        "BundleToTour", back_populates="bundle", cascade="all, delete-orphan"
    )
    entitlements: Mapped[list["Entitlement"]] = relationship(
        "Entitlement", back_populates="bundle"
    )


class BundleToTour(Base):
    __tablename__ = "bundle_to_tour"

    bundle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bundles.id", ondelete="CASCADE"), primary_key=True
    )
    tour_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tours.id", ondelete="CASCADE"), primary_key=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    bundle: Mapped["Bundle"] = relationship("Bundle", back_populates="tour_associations")
    tour: Mapped["Tour"] = relationship("Tour", back_populates="bundle_associations")


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tour_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bundle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bundles.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # direct, bundle, promo, editor_access
    receipt_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="entitlements")
    tour: Mapped["Tour"] = relationship("Tour", back_populates="entitlements")
    bundle: Mapped["Bundle | None"] = relationship("Bundle", back_populates="entitlements")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
