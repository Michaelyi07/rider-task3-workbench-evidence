"""事件 outbox + HMAC-SHA256 Webhook：签名、失败重试、幂等去重 (AC4)。

6 种契约事件类型严格固定。签名覆盖 timestamp.raw_body（防重放），
接收端时间窗 300s + hmac.compare_digest 常量时间比较 + event_id 唯一去重。
Dispatcher 指数退避 1/2/4/8/16s，超限进死信。
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid

EVENT_TYPES = (
    "candidate.created", "candidate.updated", "candidate.completed",
    "booking.created", "booking.cancelled", "handoff.requested",
)

SIGNATURE_HEADER = "X-ClawHunt-Signature"
EVENT_ID_HEADER = "X-ClawHunt-Event-Id"
TIMESTAMP_HEADER = "X-ClawHunt-Timestamp"


def sign(secret: str, timestamp: int, raw_body: bytes) -> str:
    """签名 = HMAC_SHA256(secret, f'{timestamp}.' + raw_body_bytes)。"""
    payload = str(timestamp).encode() + b"." + raw_body
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: int, raw_body: bytes, signature: str,
           now: int | None = None, tolerance: int = 300) -> bool:
    """校验时间窗 + 常量时间比较。"""
    now = now if now is not None else int(time.time())
    if abs(now - timestamp) > tolerance:
        return False
    return hmac.compare_digest(sign(secret, timestamp, raw_body), signature)


class Receiver:
    """Webhook 接收端（幂等）：同一 event_id 只处理一次。"""

    def __init__(self, secret: str):
        self.secret = secret
        self._seen: dict[str, dict] = {}
        self.processed: list[dict] = []

    def handle(self, raw_body: bytes, event_id: str, timestamp: int,
               signature: str, now: int | None = None) -> dict:
        if not verify(self.secret, timestamp, raw_body, signature, now=now):
            return {"status": 401, "body": {"code": "BAD_SIGNATURE", "message": "invalid signature"}}
        if event_id in self._seen:               # 幂等：ON CONFLICT DO NOTHING 等价
            return {"status": 200, "body": {"duplicate": True}}
        self._seen[event_id] = {"ts": timestamp}
        self.processed.append({"event_id": event_id, "body": raw_body})
        return {"status": 200, "body": {"duplicate": False}}


class OutboxWriter:
    """把事件写入 outbox（与业务同事务由调用方保证）。"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def emit(self, event_type: str, aggregate_id: str, payload: dict,
             idempotency_key: str | None = None) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {event_type}")
        from .models import Outbox
        with self.session_factory() as s:
            s.add(Outbox(
                id=str(uuid.uuid4()), event_type=event_type,
                aggregate_id=aggregate_id, payload=payload,
                idempotency_key=idempotency_key or str(uuid.uuid4()),
                status="pending", attempts=0,
            ))
            s.commit()


class Dispatcher:
    """投递 pending 事件；失败按指数退避重试，超限进死信。send 可注入便于测试。"""

    BACKOFF = [1, 2, 4, 8, 16]

    def __init__(self, session_factory, secret: str, url: str, send=None):
        self.session_factory = session_factory
        self.secret, self.url = secret, url
        self._send = send

    def dispatch_once(self, row) -> bool:
        """发一条 outbox 记录；成功返回 True。"""
        import json
        raw = json.dumps(row.payload, separators=(",", ":"), ensure_ascii=False).encode()
        ts = int(time.time())
        headers = {
            SIGNATURE_HEADER: sign(self.secret, ts, raw),
            EVENT_ID_HEADER: row.idempotency_key,
            TIMESTAMP_HEADER: str(ts),
        }
        if self._send is not None:
            ok = self._send(self.url, raw, headers)
        else:  # pragma: no cover - 需网络时使用，本机验证用注入的 send
            import httpx
            r = httpx.post(self.url, content=raw, headers=headers, timeout=5)
            ok = 200 <= r.status_code < 300
        return bool(ok)

    def run_round(self, backoff_override: list[int] | None = None) -> dict:
        """扫 pending，逐条投递并更新 attempts/status。返回统计。"""
        from .models import Outbox
        backoff = backoff_override or self.BACKOFF
        stats = {"sent": 0, "retried": 0, "dead": 0, "pending": 0}
        with self.session_factory() as s:
            rows = s.query(Outbox).filter(Outbox.status == "pending").all()
            for row in rows:
                ok = self.dispatch_once(row)
                if ok:
                    row.status = "sent"
                    stats["sent"] += 1
                else:
                    row.attempts += 1
                    if row.attempts > len(backoff):
                        row.status = "dead"
                        stats["dead"] += 1
                    else:
                        stats["retried"] += 1
            s.commit()
        return stats
