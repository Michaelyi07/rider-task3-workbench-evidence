# 验证记录 — Task 3/5（可复现，真实执行）

环境：Windows 10 / Python 3.13.14（venv `D:/tmp/pg16/.venv-pg`）/ PostgreSQL 16.9 / pytest 9.2.0 /
SQLAlchemy 2.1.9 / psycopg 3.3.9 / httpx 0.28.1。所有结果 2026-11-19 本机真实执行，输出存于 `evidence/`。
本机无 Docker / uvicorn / Redis，故按知识卡第 3 节用「PG16 直连 + httpx.ASGITransport 进程内并发」出硬证据。

## 0. 启动本机 PG16（独立临时目录与端口，避免冲突）
```
$ D:/tmp/pg16/extracted/pgsql/bin/initdb.exe -D D:/tmp/pg16/data-task3 -U <local_os_user> --auth=trust -E UTF8
$ D:/tmp/pg16/extracted/pgsql/bin/pg_ctl.exe -D D:/tmp/pg16/data-task3 -l D:/tmp/pg16/pg-task3.log -o "-p 55432" start
$ D:/tmp/pg16/extracted/pgsql/bin/psql.exe -h 127.0.0.1 -p 55432 -U <local_os_user> -d postgres -c "CREATE DATABASE clawhunt_task3;"
$ D:/tmp/pg16/extracted/pgsql/bin/psql.exe -h 127.0.0.1 -p 55432 -U <local_os_user> -d clawhunt_task3 -c "SELECT version;"
 PostgreSQL 16.9, compiled by Visual C++ build 1943, 64-bit
```

## 1. 单命令全绿（AC1/AC2/AC4/AC5/AC7）
```
$ python -m pytest
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 0.43s
```
明细（88 项）：
- 状态机 64 对全笛卡尔积 + 3 项结构断言（AC2）。契约 candidate.status 定义 **8 个状态**，8×8=64 全覆盖；
  知识卡正文「9 状态 / 81 对」把 `booking.cancelled`（预约状态）并入 candidate 统计。本仓库严格按契约 8 状态做 64 对；
  第 9 状态属 booking 状态机，不在 candidate 契约字段内——此为口径差异，非功能缺失。
- 线索去重 85 唯一 / 15 跳过（+86、连字符、86 前缀归一化同 token）+ 三种分配规则（AC1）。
- Webhook：签名正确 / 错误签名拒绝 / 超时戳拒绝 / 幂等（同 event_id 仅处理一次）/ 重试后成功 / 超限进死信（AC4）。
- 脱敏列表无明文、reveal 无理由 422、有理由写审计、reject 无理由 422、有理由改状态+审计、非法跃迁 400 且状态不变（AC5）。
- OpenAPI 路径/字段、6 种事件类型、错误体 `{code,message}`（AC7）。

## 2. 并发压测硬证据（AC3，最关键）— 真实 PG16 行锁
```
$ DATABASE_URL=postgresql+psycopg://<DB_USER>@127.0.0.1:55432/clawhunt_task3 \
    python tests/loadtest_concurrency.py
DATABASE_URL=postgresql+psycopg://<DB_USER>@127.0.0.1:55432/clawhunt_task3
N=50 SLOTS=5 ROUNDS=3 transport=ASGITransport barrier=asyncio.Event
round 1/3: success=5 rejected=45 other=0 oversell=0 db_booked_count=5 db_booking_rows=5 open_quota=5
round 2/3: success=5 rejected=45 other=0 oversell=0 db_booked_count=5 db_booking_rows=5 open_quota=5
round 3/3: success=5 rejected=45 other=0 oversell=0 db_booked_count=5 db_booking_rows=5 open_quota=5
ALL_ROUNDS_PASS 3
```
真实数字：**success=5 / rejected=45 / other=0 / oversell=0**，3 轮一致。
机制：50 协程 `asyncio.Event` 屏障同时放行，经 ASGITransport 进程内打 FastAPI；每请求独立事务，
`SELECT … FOR UPDATE` 真实锁 S1 名额行，READ COMMITTED 下重读最新已提交版本，判余量→插 booking→+1→写 outbox→提交。
每轮脚本内断言 `ok==5, rejected==45, oversell==0, db_booked_count==5, db_booking_rows==5` 全通过才继续。

## 3. psql 直连 DB 复核（压测后，独立于应用）
```
$ psql -h 127.0.0.1 -p 55432 -U <local_os_user> -d clawhunt_task3 \
    -c "SELECT id, open_quota, booked_count FROM station WHERE id='S1';" \
    -c "SELECT count(*) FROM booking WHERE station_id='S1' AND status='booked';" \
    -c "SELECT event_type, count(*) FROM outbox WHERE payload->>'station_id'='S1' GROUP BY event_type;"
 id | open_quota | booked_count
----+------------+--------------
 S1 |          5 |            5
 booking_rows: 5      booking.created: 5
```
DB 层实测：名额 5/5 用尽、booking 行数恰好 5、outbox 事件恰好 5 条，无超卖、无重复事件。

## 4. 修复记录（真实排错，非编造）
- 首轮压测第 2 轮报 `UniqueViolation: ix_outbox_idempotency_key (lt-0)`：原 outbox 幂等键用 request_id，
  跨轮重置时未随 booking 清理。修复：幂等键改用 `booking_id-created`（每次预约唯一），
  且 `reset_station` 按 `payload->>'station_id'` 精确清理 outbox。修复后 3 轮全绿（见上方输出）。
- `Dispatcher.run_round` 每轮只扫描投递一次，重试由 worker 多轮驱动；对应测试改为多轮调用后通过。

## 边界（诚实标注：需客户环境）
- `docker compose up --build -d` 冷启动、AC6 页面水印截图（Playwright）、前端 React+AntD 完整工作台、
  真实 JWT/权限与任务1/任务5真实服务对接 —— 本机无 Docker/Node/uvicorn，未在本机验证，需在客户环境执行。
- 本仓库 `src/main.py` 已交付 OpenAPI 与全部后端路由；vault/agent/LLM 依赖按契约 mock。
- 生产部署须替换 `VAULT_PEPPER`、Webhook secret、JWT 密钥，并启用任务5的加密与审计实现（本任务明确排除）。
- 并发方案为知识卡推荐的 PG 行锁（方案 A）；未使用 Redis 分布式锁（方案 C）或乐观锁（方案 B），
  因本机无 Redis 且 PG 行锁证据最硬。降级方案（SQLite + 应用层锁）仅在 PG 不可用时演示逻辑，不作证据。
