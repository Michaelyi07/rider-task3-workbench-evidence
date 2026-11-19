"""AC3 硬证据：50 并发抢同一站点最后 5 个名额 = 恰好 5 成功、0 超卖。

方案：PG16 直连 + httpx.ASGITransport 进程内并发（无需 uvicorn）
      + asyncio.Event 起跑屏障制造最大碰撞。
      FastAPI 同步端点在线程池执行，每请求独立 Session/事务；
      核心 create_booking 用 SELECT ... FOR UPDATE 行锁串行化名额行。
重复 3 轮，每轮直连 PG 重置并核对 booked_count / booking 行数。

真实运行：
  DATABASE_URL=postgresql+psycopg://<DB_USER>@127.0.0.1:55432/clawhunt_task3 \
  D:/tmp/pg16/.venv-pg/Scripts/python.exe tests/loadtest_concurrency.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx

from src.db import (count_bookings, database_url, get_booked_count, get_open_quota,
                    make_engine, reset_station)
from src.main import app, use_postgres

N = 50
SLOTS = 5
ROUNDS = 3
BASE = "http://testserver"
limits = httpx.Limits(max_connections=60, max_keepalive_connections=60)


async def hit(cid: int, barrier: asyncio.Event) -> int:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url=BASE, limits=limits) as c:
        await barrier.wait()                       # 50 个协程同时起跑
        r = await c.post("/api/v1/bookings", json={
            "candidate_id": f"cand-{cid:03d}", "station_id": "S1",
            "slot_start": "2026-11-20T10:00:00+08:00",
            "request_id": f"lt-{cid}",
        })
        return r.status_code


async def one_round(engine, rnd: int) -> dict:
    reset_station(engine, "S1", open_quota=SLOTS, booked_count=0)
    barrier = asyncio.Event()
    tasks = [asyncio.create_task(hit(i, barrier)) for i in range(N)]
    barrier.set()
    codes = await asyncio.gather(*tasks)

    ok = sum(c in (200, 201) for c in codes)
    rejected = sum(c in (409, 423) for c in codes)
    other = N - ok - rejected
    dbc = get_booked_count(engine, "S1")
    q = get_open_quota(engine, "S1")
    rows = count_bookings(engine, "S1", "booked")
    oversell = max(0, ok - SLOTS)
    result = {
        "round": rnd, "success": ok, "rejected": rejected, "other": other,
        "oversell": oversell, "db_booked_count": dbc, "db_booking_rows": rows,
        "open_quota": q,
    }
    print(
        f"round {rnd}/{ROUNDS}: success={ok} rejected={rejected} other={other} "
        f"oversell={oversell} db_booked_count={dbc} db_booking_rows={rows} "
        f"open_quota={q}"
    )
    assert ok == SLOTS, f"expected {SLOTS} successes, got {ok}"
    assert rejected == N - SLOTS, f"expected {N-SLOTS} rejections, got {rejected}"
    assert oversell == 0
    assert dbc == SLOTS and rows == SLOTS
    return result


async def main() -> None:
    url = os.environ.get("DATABASE_URL", database_url())
    if "postgres" not in url:
        raise SystemExit("PG16 required; set DATABASE_URL to a PostgreSQL URL")
    engine = make_engine(url, pool_size=60, max_overflow=20)
    use_postgres(url)
    print(f"DATABASE_URL={url}")
    print(f"N={N} SLOTS={SLOTS} ROUNDS={ROUNDS} transport=ASGITransport barrier=asyncio.Event")
    results = []
    for r in range(1, ROUNDS + 1):
        results.append(await one_round(engine, r))
    print("ALL_ROUNDS_PASS", len(results))


if __name__ == "__main__":
    asyncio.run(main())
