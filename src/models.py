"""SQLAlchemy 模型：candidate / station / booking / outbox（按共享契约字段）。

SQLite 与 PG16 通用（无 PG 专有类型）；CHECK 约束兜底防超卖。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Station(Base):
    __tablename__ = "station"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    booked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("booked_count >= 0", name="ck_quota_nonneg"),
        CheckConstraint("booked_count <= open_quota", name="ck_quota_ceiling"),
    )


class Candidate(Base):
    __tablename__ = "candidate"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    birth_ym: Mapped[str | None] = mapped_column(String(7), nullable=True)
    area_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    has_ebike: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    start_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    experience_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    health_cert: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retention_until: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=_now)
    updated_at: Mapped[str] = mapped_column(String(40), default=_now)


class Booking(Base):
    __tablename__ = "booking"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slot_start: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="booked")
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=_now)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(String(40), default=_now)
