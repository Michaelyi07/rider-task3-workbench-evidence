"""仓储层。

PGRepository：真实 PG16，核心 create_booking 用 SELECT ... FOR UPDATE 行锁，
同事务内 锁名额行 -> 判余量 -> 插 booking -> +1 -> 写 outbox -> 提交（AC3 主方案）。
InMemoryRepository：线程锁字典，供非并发 API 测试；不作为超卖证据。
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .models import Booking, Candidate, Outbox, Station


class QuotaFull(Exception):
    code = "QUOTA_FULL"


class StationNotFound(Exception):
    code = "STATION_NOT_FOUND"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_outbox(event_type, aggregate_id, payload, key):
    return Outbox(
        id=str(uuid.uuid4()), event_type=event_type, aggregate_id=aggregate_id,
        payload=payload, idempotency_key=key, status="pending", attempts=0,
    )


# ---------------------------------------------------------------- PG (主方案)
class PGRepository:
    def __init__(self, engine):
        from .db import make_session_factory
        self.engine = engine
        self.Session = make_session_factory(engine)

    # ---- candidates ----
    def ensure_candidate(self, row: dict) -> bool:
        """按 phone_token 去重插入；返回 True 表示新增，False 表示重复。"""
        with self.Session() as s:
            try:
                with s.begin():
                    s.add(Candidate(**row))
                return True
            except IntegrityError:
                return False

    def list_candidates(self) -> list[dict]:
        with self.Session() as s:
            rows = s.execute(select(Candidate)).scalars().all()
            return [{c.name: getattr(x, c.name) for c in Candidate.__table__.columns} for x in rows]

    def get_candidate(self, cid: str) -> dict | None:
        with self.Session() as s:
            x = s.get(Candidate, cid)
            return None if x is None else {c.name: getattr(x, c.name) for c in Candidate.__table__.columns}

    def set_status(self, cid: str, status: str) -> dict:
        with self.Session() as s:
            with s.begin():
                x = s.get(Candidate, cid)
                if x is None:
                    raise KeyError(cid)
                x.status = status
                x.updated_at = _now()
                s.add(_new_outbox("candidate.updated", cid, {"status": status}, f"{cid}-updated"))
            return {"id": cid, "status": status}

    # ---- bookings（核心：SELECT FOR UPDATE 行锁） ----
    def create_booking(self, candidate_id: str, station_id: str,
                       slot_start: str, request_id: str) -> dict:
        with self.Session() as s:
            with s.begin():                                   # 事务边界
                # ① 锁名额行（READ COMMITTED 下会重读最新已提交版本）
                st = s.execute(
                    select(Station).where(Station.id == station_id).with_for_update()
                ).scalar_one_or_none()
                if st is None:
                    raise StationNotFound(station_id)
                # ② 判余量
                if st.open_quota - st.booked_count <= 0:
                    raise QuotaFull(station_id)
                # 幂等：同一 request_id 重试返回原结果
                existing = s.execute(
                    select(Booking).where(Booking.request_id == request_id)
                ).scalar_one_or_none()
                if existing is not None:
                    return {"booking_id": existing.id, "status": "booked", "duplicate": True}
                # ③ 占位
                bid = str(uuid.uuid4())
                s.add(Booking(id=bid, candidate_id=candidate_id, station_id=station_id,
                              slot_start=slot_start, status="booked", request_id=request_id,
                              created_at=_now()))
                # ④ 扣减（CHECK booked_count<=open_quota 兜底）
                st.booked_count += 1
                st.version += 1
                # ⑤ 同事务写 outbox（幂等键与 booking id 绑定，跨请求唯一）
                s.add(_new_outbox("booking.created", bid, {
                    "candidate_id": candidate_id, "station_id": station_id,
                    "slot_start": slot_start,
                }, f"{bid}-created"))
            # ⑥ 提交释放锁
            return {"booking_id": bid, "status": "booked", "duplicate": False}


# ------------------------------------------------------------ in-memory (测试)
class InMemoryRepository:
    def __init__(self):
        self._lock = threading.Lock()
        self.candidates: dict[str, dict] = {}
        self.stations: dict[str, dict] = {}
        self.bookings: dict[str, dict] = {}
        self.outbox: list[dict] = []

    def ensure_candidate(self, row: dict) -> bool:
        with self._lock:
            if any(c["phone_token"] == row["phone_token"] for c in self.candidates.values()):
                return False
            self.candidates[row["id"]] = dict(row)
            return True

    def list_candidates(self) -> list[dict]:
        with self._lock:
            return [dict(c) for c in self.candidates.values()]

    def get_candidate(self, cid: str) -> dict | None:
        with self._lock:
            c = self.candidates.get(cid)
            return dict(c) if c else None

    def set_status(self, cid: str, status: str) -> dict:
        with self._lock:
            c = self.candidates[cid]
            c["status"] = status
            c["updated_at"] = _now()
            self.outbox.append({"event_type": "candidate.updated", "aggregate_id": cid})
            return {"id": cid, "status": status}

    def create_booking(self, candidate_id, station_id, slot_start, request_id):
        with self._lock:                     # 应用层互斥锁（仅测试；非超卖证据）
            st = self.stations.get(station_id)
            if st is None:
                raise StationNotFound(station_id)
            if st["open_quota"] - st["booked_count"] <= 0:
                raise QuotaFull(station_id)
            for b in self.bookings.values():
                if b["request_id"] == request_id:
                    return {"booking_id": b["id"], "status": "booked", "duplicate": True}
            bid = str(uuid.uuid4())
            self.bookings[bid] = {"id": bid, "candidate_id": candidate_id,
                                  "station_id": station_id, "slot_start": slot_start,
                                  "status": "booked", "request_id": request_id}
            st["booked_count"] += 1
            self.outbox.append({"event_type": "booking.created", "aggregate_id": bid})
            return {"booking_id": bid, "status": "booked", "duplicate": False}
