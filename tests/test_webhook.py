"""AC4：Webhook HMAC 签名 / 时间戳防重放 / 幂等 / 失败重试。"""
import json
import time

from src.webhook import Dispatcher, Receiver, sign, verify

SECRET = "test-secret"


def test_sign_and_verify():
    body = b'{"event":"booking.created"}'
    ts = int(time.time())
    sig = sign(SECRET, ts, body)
    assert sig.startswith("sha256=")
    assert verify(SECRET, ts, body, sig, now=ts) is True


def test_bad_signature_rejected():
    body = b'{"a":1}'
    ts = int(time.time())
    assert verify(SECRET, ts, body, "sha256=deadbeef", now=ts) is False
    assert verify("wrong-secret", ts, body, sign(SECRET, ts, body), now=ts) is False


def test_stale_timestamp_rejected():
    body = b"{}"
    ts = int(time.time())
    sig = sign(SECRET, ts - 1000, body)
    assert verify(SECRET, ts - 1000, body, sig, now=ts, tolerance=300) is False


class FakeRow:
    def __init__(self, payload, key):
        import uuid
        self.id = str(uuid.uuid4())
        self.payload = payload
        self.idempotency_key = key
        self.attempts = 0
        self.status = "pending"


class FakeQuery:
    def __init__(self, rows): self.rows = rows
    def filter(self, *a): return self
    def all(self): return self.rows


class FakeSession:
    def __init__(self, rows): self.rows = rows
    def query(self, m): return FakeQuery(self.rows)
    def commit(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_receiver_idempotent():
    r = Receiver(SECRET)
    body = b'{"event":"booking.created"}'
    ts = int(time.time())
    headers = {
        "event_id": "evt-1", "timestamp": ts,
        "signature": sign(SECRET, ts, body),
    }
    first = r.handle(body, **headers, now=ts)
    second = r.handle(body, **headers, now=ts)
    assert first["status"] == 200 and first["body"]["duplicate"] is False
    assert second["body"]["duplicate"] is True
    assert len(r.processed) == 1


def test_dispatcher_retry_then_success():
    row = FakeRow({"a": 1}, "idem-1")
    attempts = {"n": 0}

    def send(url, raw, headers):
        attempts["n"] += 1
        return attempts["n"] >= 3   # 前两次失败，第三次成功

    d = Dispatcher(lambda: FakeSession([row]), SECRET, "http://x", send=send)
    # 每轮只扫 pending 一次；失败留 pending 等待下一轮（真实 worker 按退避间隔重扫）
    s1 = d.run_round(backoff_override=[1, 2, 4])
    s2 = d.run_round(backoff_override=[1, 2, 4])
    s3 = d.run_round(backoff_override=[1, 2, 4])
    assert s1["retried"] == 1 and s2["retried"] == 1 and s3["sent"] == 1
    assert row.status == "sent"
    assert attempts["n"] == 3


def test_dispatcher_dead_letter_after_max_retries():
    row = FakeRow({"a": 1}, "idem-2")
    d = Dispatcher(lambda: FakeSession([row]), SECRET, "http://x", send=lambda *a: False)
    for _ in range(3):                # 3 轮均失败：attempts 达 3 > len(backoff)=2
        stats = d.run_round(backoff_override=[1, 2])
    assert row.status == "dead"
    assert stats["dead"] == 1
