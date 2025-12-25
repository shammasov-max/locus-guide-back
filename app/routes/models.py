import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, HSTORE, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    COMING_SOON = "coming_soon"
    ARCHIVED = "archived"


class RouteVersionStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class AudioListenStatus(str, enum.Enum):
    NONE = "none"
    STARTED = "started"
    COMPLETED = "completed"


class CompletionType(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.geonameid"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(RouteStatus, name="route_status", create_type=False),
        nullable=False,
        server_default="draft",
    )
    published_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("route_versions.id", use_alter=True, name="fk_route_published_version"),
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
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
    city: Mapped["City"] = relationship()  # type: ignore
    created_by: Mapped["AppUser"] = relationship()  # type: ignore
    versions: Mapped[list["RouteVersion"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        foreign_keys="[RouteVersion.route_id]",
    )
    published_version: Mapped["RouteVersion | None"] = relationship(
        foreign_keys=[published_version_id],
        post_update=True,
    )
    active_sessions: Mapped[list["UserActiveRoute"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("city_id", "slug", name="uq_route_city_slug"),
        Index("idx_routes_city", "city_id"),
        Index("idx_routes_status", "status"),
        Index("idx_routes_created_by", "created_by_user_id"),
    )


class RouteVersion(Base):
    __tablename__ = "route_versions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    route_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(RouteVersionStatus, name="route_version_status", create_type=False),
        nullable=False,
    )
    title_i18n: Mapped[dict] = mapped_column(HSTORE, nullable=False)
    summary_i18n: Mapped[dict | None] = mapped_column(HSTORE)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    ascent_m: Mapped[int | None] = mapped_column(Integer)
    descent_m: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    path = mapped_column(Geography("LINESTRING", srid=4326))
    geojson: Mapped[dict | None] = mapped_column(JSONB)
    bbox = mapped_column(Geography("POLYGON", srid=4326))
    free_checkpoint_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_currency: Mapped[str | None] = mapped_column(String(3))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id"), nullable=False
    )

    # Relationships
    route: Mapped["Route"] = relationship(
        back_populates="versions",
        foreign_keys=[route_id],
    )
    created_by: Mapped["AppUser"] = relationship()  # type: ignore
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        back_populates="route_version",
        cascade="all, delete-orphan",
        order_by="Checkpoint.seq_no",
    )

    __table_args__ = (
        UniqueConstraint("route_id", "version_no", name="uq_route_version"),
        Index("idx_route_versions_route", "route_id"),
        Index("idx_route_versions_status", "status"),
        CheckConstraint(
            "free_checkpoint_limit >= 0", name="check_free_checkpoint_limit_nonneg"
        ),
        CheckConstraint(
            "(price_amount IS NULL AND price_currency IS NULL) OR "
            "(price_amount IS NOT NULL AND price_currency IS NOT NULL)",
            name="check_price_fields_together",
        ),
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    route_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("route_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    display_number: Mapped[int | None] = mapped_column(Integer)
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    source_point_id: Mapped[int | None] = mapped_column(Integer)
    title_i18n: Mapped[dict] = mapped_column(HSTORE, nullable=False)
    description_i18n: Mapped[dict | None] = mapped_column(HSTORE)
    location = mapped_column(Geography("POINT", srid=4326), nullable=False)
    trigger_radius_m: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="25"
    )
    is_free_preview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    osm_way_id: Mapped[int | None] = mapped_column(BigInteger)
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
    route_version: Mapped["RouteVersion"] = relationship(back_populates="checkpoints")
    visited_points: Mapped[list["VisitedPoint"]] = relationship(
        back_populates="checkpoint",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "route_version_id", "seq_no", name="uq_checkpoint_route_version_seq"
        ),
        Index("idx_checkpoints_route_version", "route_version_id"),
        CheckConstraint("seq_no >= 0", name="check_seq_no_nonneg"),
        CheckConstraint("trigger_radius_m > 0", name="check_trigger_radius_positive"),
    )


class VisitedPoint(Base):
    __tablename__ = "visited_points"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id"),
        primary_key=True,
    )
    checkpoint_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("checkpoints.id"),
        primary_key=True,
    )
    visited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audio_status: Mapped[str] = mapped_column(
        Enum(AudioListenStatus, name="audio_listen_status", create_type=False),
        nullable=False,
        server_default="none",
    )
    audio_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audio_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    checkpoint: Mapped["Checkpoint"] = relationship(back_populates="visited_points")

    __table_args__ = (
        Index("idx_visited_points_user", "user_id"),
        Index("idx_visited_points_checkpoint", "checkpoint_id"),
    )


class UserActiveRoute(Base):
    __tablename__ = "user_active_routes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    locked_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("route_versions.id"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_type: Mapped[str | None] = mapped_column(
        Enum(CompletionType, name="completion_type", create_type=False)
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    route: Mapped["Route"] = relationship(back_populates="active_sessions")
    locked_version: Mapped["RouteVersion"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "route_id", name="uq_user_active_route"),
        Index("idx_user_active_routes_user", "user_id"),
        Index("idx_user_active_routes_route", "route_id"),
    )
