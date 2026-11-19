"""引擎/会话工厂与建表、压测辅助（同步 SQLAlchemy + psycopg3，无需 greenlet）。"""

from __future__ import annotations

import os

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import Base

DEFAULT_DATABASE_URL = "postgresql+psycopg://<DB_USER>@127.0.0.1:55432/clawhunt_task3"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None, pool_size: int = 60, max_overflow: int = 20):
    """PG16 用够大的连接池避免 50 并发把连接等待误判为失败；SQLite 忽略池参数。"""
    url = url or database_url()
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


# ---- 压测辅助（直连 DB 重置/计数，用 psycopg 同步连接） ----
def reset_station(engine, station_id: str = "S1", open_quota: int = 5,
                  booked_count: int = 0, name: str = "S1") -> None:
    with engine.begin() as conn:
        # 先删该站点 booking 对应的 outbox 事件（按 booking id），再删 booking
        bids = [r[0] for r in conn.execute(
            text("SELECT id FROM booking WHERE station_id=:s"), {"s": station_id}).fetchall()]
        if bids:
            stmt = text("DELETE FROM outbox WHERE aggregate_id IN :bids").bindparams(
                bindparam("bids", expanding=True))
            conn.execute(stmt, {"bids": bids})
        # 兜底：清理 payload 里指向该站点的所有 outbox 事件（含历史遗留/孤行）
        conn.execute(text("DELETE FROM outbox WHERE payload->>'station_id' = :s"), {"s": station_id})
        conn.execute(text("DELETE FROM booking WHERE station_id=:s"), {"s": station_id})
        exists = conn.execute(text("SELECT 1 FROM station WHERE id=:s"), {"s": station_id}).first()
        if exists:
            conn.execute(
                text("UPDATE station SET open_quota=:q, booked_count=:b, version=0 WHERE id=:s"),
                {"q": open_quota, "b": booked_count, "s": station_id},
            )
        else:
            conn.execute(
                text("INSERT INTO station(id,name,lat,lng,open_quota,booked_count,version) "
                     "VALUES(:s,:n,31.2,121.5,:q,:b,0)"),
                {"s": station_id, "n": name, "q": open_quota, "b": booked_count},
            )


def get_booked_count(engine, station_id: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT booked_count FROM station WHERE id=:s"),
                                {"s": station_id}).scalar_one())


def get_open_quota(engine, station_id: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT open_quota FROM station WHERE id=:s"),
                                {"s": station_id}).scalar_one())


def count_bookings(engine, station_id: str, status: str = "booked") -> int:
    with engine.connect() as conn:
        return int(conn.execute(
            text("SELECT count(*) FROM booking WHERE station_id=:s AND status=:st"),
            {"s": station_id, "st": status},
        ).scalar_one())
