from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    locale_pref: Mapped[str | None] = mapped_column(Text)  # e.g., 'ru-RU'
    ui_lang: Mapped[str | None] = mapped_column(Text)
    audio_lang: Mapped[str | None] = mapped_column(Text)
    units: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="metric"
    )
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Relationships
    identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("units IN ('metric', 'imperial')", name="check_units"),
    )


class AuthIdentity(Base):
    __tablename__ = "auth_identity"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_subject: Mapped[str] = mapped_column(Text, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["AppUser"] = relationship(back_populates="identities")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="identity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
        CheckConstraint("provider IN ('google', 'email')", name="check_provider"),
        Index("idx_auth_identity_user", "user_id"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    device_info: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["AppUser"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_token_user", "user_id"),
        Index("idx_refresh_token_expires", "expires_at"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_token"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    identity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth_identity.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    identity: Mapped["AuthIdentity"] = relationship(back_populates="password_reset_tokens")
