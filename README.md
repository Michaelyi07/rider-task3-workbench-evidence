# ClawHunt — Task 3/5: Recruitment Workbench & Business Services

> **Bid evidence snapshot.** This repository contains the reproducible verification evidence (test suite, measured outputs, interface contract and startup notes) for this task. The full runnable implementation is delivered to the awarding party after the bid is won. All data shown is synthetic.



可运行参考实现 + 真实验收证据。对应投标单 1806（报价 $600）。**只用合成数据，无真实个人信息。**

## 范围
- candidate / station / booking / outbox 数据模型（字段按「共用接口契约 v1」）
- 100 条线索导入：手机号 token 去重 + 分配规则（by_station / by_region / round_robin）
- 候选人状态机（非法跃迁拒绝，覆盖全部状态对）
- **50 并发抢最后 5 名额：恰好 5 成功、零超卖**（`SELECT … FOR UPDATE` 行锁）
- event outbox + Webhook（HMAC-SHA256、失败重试、幂等去重）
- 手机号/姓名脱敏 + 查看完整号需理由 + vault mock + 审计
- OpenAPI 文档 + 契约测试

## 技术栈与许可
Python 3.12+ / FastAPI / SQLAlchemy 2.0 / psycopg3 / PostgreSQL 16 / pytest / httpx。
依赖均为 MIT / Apache-2.0 / BSD / PostgreSQL 许可，无 GPL/AGPL（见 `requirements.txt`）。

## 一键启动（客户环境，需 Docker）
```bash
docker compose up --build -d
curl -s http://127.0.0.1:8000/health          # {"status":"ok"}
curl http://127.0.0.1:8000/docs               # OpenAPI / Swagger UI
```
本机无 Docker，故本机验证走下方「直连 PG16」路径，证据见 `VERIFICATION.md`。

## 测试（单命令全绿）
```bash
python -m pytest                 # 88 passed（去重/状态机/Webhook/脱敏/审计/契约）
```
`tests/loadtest_concurrency.py` 文件名不匹配 `test_*.py`，不被 pytest 收集，可独立运行。

## 关键并发证据（独立脚本，真连 PG16，重复 3 轮）
```bash
# 本机 PG16 于 127.0.0.1:55432，库 clawhunt_task3（见 VERIFICATION.md 启动命令）
DATABASE_URL=postgresql+psycopg://<DB_USER>@127.0.0.1:55432/clawhunt_task3 \
  python tests/loadtest_concurrency.py
# 每轮: success=5 rejected=45 other=0 oversell=0 db_booked_count=5 db_booking_rows=5
```

## 目录
- `src/models.py` 模型 · `src/repo.py` **行锁预约核心** · `src/state_machine.py` 状态机
- `src/leads.py` 去重与分配 · `src/vault.py` 保险箱 mock/脱敏 · `src/webhook.py` outbox+HMAC
- `src/audit.py` 审计 · `src/main.py` FastAPI app/路由 · `src/db.py` 引擎与压测辅助
- `tests/` 测试 + `tests/data/leads_100.csv`（100 条合成线索）
- `evidence/` 真实运行输出 · `VERIFICATION.md` 验证记录 · `schema.sql` DDL

## 防超卖事务边界（核心）
```
BEGIN
  SELECT ... FROM station WHERE id=? FOR UPDATE;   -- ① 锁名额行（串行点）
  remaining = open_quota - booked_count
  IF remaining <= 0 -> 409 QUOTA_FULL               -- ② 判余量
  INSERT booking ... ON CONFLICT(request_id) DO NOTHING -- ③ 幂等占位
  UPDATE station SET booked_count=booked_count+1     -- ④ 扣减（CHECK 兜底）
  INSERT outbox(booking.created, ...)                -- ⑤ 同事务写事件
COMMIT                                                -- ⑥ 提交放锁
```
三把唯一约束兜底：`candidate.phone_token`（AC1）、`booking.request_id`（AC3 幂等）、
`outbox.idempotency_key`（AC4 幂等）；`CHECK(booked_count<=open_quota)` 为超卖最后防线。
Webhook 投递在事务外异步进行，避免长 IO 拉长持锁时间。

## 诚实边界
- `SELECT FOR UPDATE` 语义依赖 PostgreSQL 行锁；SQLite 不支持，其应用层互斥锁仅用于逻辑演示，**不作为超卖证据**。
- 本机未运行 Docker/前端 Playwright：水印截图（AC6）与 `docker compose` 冷启动需客户环境验证。
- 客户环境需替换 `VAULT_PEPPER` / Webhook secret / JWT 配置（本仓库为演示值）。
