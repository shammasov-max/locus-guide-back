"""SQLAlchemy models for achievements (US-025-028)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Achievement(Base):
    """Achievement definition.

    Defines gamification achievements that users can earn.
    Categories:
    - 'routes': Achievements for completing tours (US-025, US-026)
    - 'cities': Achievements for visiting cities (US-027)
    - 'completion': Achievements for 100% completion (US-028)
    """

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title_i18n: Mapped[dict] = mapped_column(HSTORE, nullable=False)
    description_i18n: Mapped[dict | None] = mapped_column(HSTORE)
    icon_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    user_achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="achievement",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_achievement_code"),
        Index("idx_achievements_category", "category"),
    )


class UserAchievement(Base):
    """User's earned achievements.

    Tracks which achievements a user has earned and when.
    """

    __tablename__ = "user_achievements"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    achievement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("achievements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["AppUser"] = relationship()  # type: ignore
    achievement: Mapped["Achievement"] = relationship(back_populates="user_achievements")

    __table_args__ = (Index("idx_user_achievements_user", "user_id"),)
