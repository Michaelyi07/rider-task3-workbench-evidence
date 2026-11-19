-- Task 3/5 交付版 DDL（客户环境 PG16 用；本机由 SQLAlchemy create_all 自动建表）
-- 关键：三把唯一约束是 AC1/AC3/AC4 的最后防线；CHECK 是防超卖兜底。

CREATE TABLE IF NOT EXISTS station (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  lat DOUBLE PRECISION, lng DOUBLE PRECISION,
  open_quota INT NOT NULL CHECK (open_quota >= 0),
  booked_count INT NOT NULL DEFAULT 0 CHECK (booked_count >= 0),
  version INT NOT NULL DEFAULT 0,
  CONSTRAINT quota_ceiling CHECK (booked_count <= open_quota)
);
CREATE TABLE IF NOT EXISTS candidate (
  id TEXT PRIMARY KEY, name_token TEXT,
  phone_token TEXT NOT NULL UNIQUE,
  birth_ym TEXT, area_text TEXT, job_type TEXT, has_ebike BOOLEAN,
  start_text TEXT, experience_text TEXT, health_cert TEXT, source_channel TEXT,
  station_id TEXT, status TEXT NOT NULL,
  consent_version TEXT, consent_at TEXT, retention_until TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS booking (
  id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, station_id TEXT NOT NULL,
  slot_start TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'booked',
  request_id TEXT NOT NULL UNIQUE, created_at TEXT
);
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
  payload JSONB NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
  attempts INT DEFAULT 0, status TEXT DEFAULT 'pending', created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_booking_station ON booking(station_id);
CREATE INDEX IF NOT EXISTS ix_outbox_aggregate ON outbox(aggregate_id);
