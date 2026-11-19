# ClawHunt — Task 3/5: Recruitment Workbench & Business Services

可运行参考实现 + 真实验收证据。对应投标单 1806（报价 $600）。**只用合成数据，无真实个人信息。**

## 范围
- candidate / station / booking / outbox 数据模型（字段按「共用接口契约 v1」）
- 100 条线索导入：手机号 token 去重 + 分配规则（by_station / by_region / round_robin）
- 候选人状态机（非法跃迁拒绝，覆盖全部状态对）
- **50 并发抢最后 5 名额：恰好 5 成功、零超卖**（`SELECT … FOR UPDATE` 行锁）
- event outbox + Webhook（HMAC-SHA256、失败重试、幂等去重）
- 手机号/姓名脱敏 + 查看完整号需理由 + vault mock + 审计
- OpenAPI 文档 + 契约测试
- **React + AntD 工作台前端**（AC5/AC6）：我的候选人列表（默认脱敏 138\*\*\*\*8000、来源/意向站点/意向度/状态列、筛选搜索）、详情页（AI 画像字段、初筛建议 ✓/!、对话摘要、确认面试/转人工/标记不合适——无理由禁提交）、查看完整号码（必须填理由 → vault detokenize，仅显示一次不缓存）、页面右下角个人水印（姓名 · 工号 · 日期）

## 技术栈与许可
Python 3.12+ / FastAPI / SQLAlchemy 2.0 / psycopg3 / PostgreSQL 16 / pytest / httpx；
前端 React 18 + Ant Design 5 + Vite 5 + Vitest（Node 22）。
依赖均为 MIT / Apache-2.0 / BSD / PostgreSQL 许可，无 GPL/AGPL（见 `requirements.txt` 与 `frontend/package.json`）。

## 一键启动（客户环境，需 Docker）
```bash
docker compose up --build -d
curl -s http://127.0.0.1:8000/health          # {"status":"ok"}
curl http://127.0.0.1:8000/docs               # OpenAPI / Swagger UI
# 工作台前端：nginx 静态托管 + /api 反代后端
# 浏览器打开 http://127.0.0.1:8080
```
本机无 Docker，故本机验证走下方「直连 PG16」路径 + 前端本机真实构建，证据见 `VERIFICATION.md`。

## 测试（单命令全绿）
```bash
python -m pytest                 # 88 passed（去重/状态机/Webhook/脱敏/审计/契约）
# 前端（本机坑位：NODE_OPTIONS 与 vite 冲突，必须 env -u NODE_OPTIONS）
cd frontend && env -u NODE_OPTIONS npm install
cd frontend && env -u NODE_OPTIONS npm test     # 5 passed（脱敏显示/无理由禁提交/水印存在/reveal 一次性）
cd frontend && env -u NODE_OPTIONS npm run build  # vite build 成功
```
前端默认走内置契约 mock（`src/api/mock.js`，不依赖后端起服）；对接真实后端时设 `VITE_USE_MOCK=false`。
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
- `frontend/` React+AntD 工作台（`src/pages/` 列表与详情 · `src/components/Watermark.jsx` AC6 水印 ·
  `src/api/mock.js` 契约 mock · `src/__tests__/` Vitest · `Dockerfile`+`nginx.conf` compose 前端服务）
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
- 前端已在本机真实构建（vite build 成功）并通过 Vitest 5/5；本机未运行 Docker/Playwright：
  `docker compose` 冷启动与水印浏览器截图（AC6）需客户环境验证。
- 客户环境需替换 `VAULT_PEPPER` / Webhook secret / JWT 配置（本仓库为演示值）。
