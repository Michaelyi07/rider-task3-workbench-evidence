"""FastAPI 应用：工作台与业务服务 API (AC0/AC1/AC4/AC5/AC7)。

错误体统一 {code, message}；开放 /openapi.json 与 /docs；
同步端点运行在线程池，配合 PG SELECT FOR UPDATE 支撑真实并发。
"""

from __future__ import annotations

import math

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .audit import AuditTrail
from .db import make_engine, make_session_factory, init_db
from .leads import Lead, import_leads
from .repo import InMemoryRepository, PGRepository, QuotaFull, StationNotFound
from .state_machine import IllegalTransition, transition
from .vault import VaultMock
from .webhook import EVENT_TYPES, Receiver, sign, verify

app = FastAPI(title="ClawHunt Task3 Workbench", version="1.0.0",
              description="Recruitment Workbench and Business Services (synthetic data only)")


# ---- 默认内存依赖（压测脚本会把 repo 换成 PGRepository） ----
_audit = AuditTrail()
_vault = VaultMock(audit=_audit)
_repo = InMemoryRepository()
_receiver = Receiver(secret="demo-webhook-secret")


def configure(repo=None, vault=None, audit=None, receiver=None):
    global _repo, _vault, _audit, _receiver
    if repo is not None: _repo = repo
    if vault is not None: _vault = vault
    if audit is not None: _audit = audit
    if receiver is not None: _receiver = receiver


def use_postgres(url: str | None = None):
    """切到真实 PG16 仓储（压测用），建表并返回 repo。"""
    engine = make_engine(url)
    init_db(engine)
    repo = PGRepository(engine)
    configure(repo=repo)
    return repo, engine


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status,
                        content={"code": exc.code, "message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "code": "VALIDATION_ERROR", "message": str(exc.errors())[:500]})


@app.exception_handler(QuotaFull)
async def quota_full_handler(_: Request, exc: QuotaFull):
    return JSONResponse(status_code=409,
                        content={"code": "QUOTA_FULL", "message": "no remaining slot"})


@app.exception_handler(StationNotFound)
async def station_not_found_handler(_: Request, exc: StationNotFound):
    return JSONResponse(status_code=404,
                        content={"code": "STATION_NOT_FOUND", "message": "station missing"})


@app.exception_handler(IllegalTransition)
async def illegal_transition_handler(_: Request, exc: IllegalTransition):
    return JSONResponse(status_code=400, content={
        "code": "ILLEGAL_TRANSITION", "message": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"code": "BAD_REQUEST", "message": str(exc)})


@app.exception_handler(KeyError)
async def key_error_handler(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": str(exc)})


# ----------------------------- schemas -----------------------------
class CandidateOut(BaseModel):
    id: str
    name_masked: str = ""
    phone_masked: str = ""
    birth_ym: str | None = None
    area_text: str | None = None
    job_type: str | None = None
    has_ebike: bool | None = None
    start_text: str | None = None
    experience_text: str | None = None
    health_cert: str | None = None
    source_channel: str | None = None
    station_id: str | None = None
    status: str
    consent_version: str | None = None
    consent_at: str | None = None
    retention_until: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RevealIn(BaseModel):
    reason: str = Field(min_length=5)


class RejectIn(BaseModel):
    status: str = "rejected"
    reason: str = Field(min_length=1)


class BookingIn(BaseModel):
    candidate_id: str
    station_id: str
    slot_start: str
    request_id: str


class VaultIn(BaseModel):
    type: str
    value: str


class DetokenizeIn(BaseModel):
    token: str
    reason: str = Field(min_length=5)


class LeadIn(BaseModel):
    phone: str
    area_text: str
    source_channel: str
    station_id: str | None = None
    job_type: str = "undecided"


class ImportIn(BaseModel):
    leads: list[LeadIn]
    rule: str = "round_robin"
    active_stations: list[str] = ["S1", "S2", "S3", "S4"]


class TransitionIn(BaseModel):
    next: str
    reason: str = ""


# ----------------------------- routes -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/candidates", response_model=list[CandidateOut])
def list_candidates():
    out = []
    for c in _repo.list_candidates():
        row = dict(c)
        row["phone_masked"] = _vault.masked(row.get("phone_token", ""), "phone")
        row["name_masked"] = _vault.masked(row.get("name_token", ""), "name") if row.get("name_token") else ""
        out.append(row)
    return out


@app.post("/api/v1/candidates/{cid}/reveal")
def reveal(cid: str, body: RevealIn):
    c = _repo.get_candidate(cid)
    if c is None:
        raise AppError(404, "NOT_FOUND", "candidate missing")
    value = _vault.detokenize(c["phone_token"], body.reason)
    return {"phone": value, "reason": body.reason, "one_time": True}


@app.post("/api/v1/candidates/{cid}/reject")
def reject(cid: str, body: RejectIn):
    result = _repo.set_status(cid, "rejected")
    _audit.record("reject", actor="recruiter", target=cid, reason=body.reason)
    return result


@app.post("/api/v1/candidates/{cid}/transition")
def do_transition(cid: str, body: TransitionIn):
    c = _repo.get_candidate(cid)
    if c is None:
        raise AppError(404, "NOT_FOUND", "candidate missing")
    nxt = transition(c["status"], body.next)  # 非法抛 ValueError -> 400
    return _repo.set_status(cid, nxt)


@app.post("/api/v1/leads/import")
def import_leads_api(body: ImportIn):
    leads = [Lead(**x.model_dump()) for x in body.leads]
    res = import_leads(leads, body.rule, body.active_stations)
    added = 0
    for row in res.rows:
        if _repo.ensure_candidate(row):
            added += 1
    return {"inserted": added, "duplicates_skipped": res.duplicates_skipped,
            "assignments": res.assignments}


@app.post("/api/v1/bookings")
def create_booking(body: BookingIn):
    return _repo.create_booking(body.candidate_id, body.station_id,
                                body.slot_start, body.request_id)


@app.get("/api/v1/stations/recommend")
def recommend(lat: float = 31.2, lng: float = 121.5, limit: int = 4):
    """按距离 + 剩余名额排序（热点优先有空位）。"""
    stations = _repo.list_candidates()  # 占位以兼容接口；真实列表来自 repo 扩展
    # 用 repo 暴露的 station 数据（若有）
    raw = getattr(_repo, "stations", None)
    items = []
    if isinstance(raw, dict):
        items = list(raw.values())
    else:  # PG 仓储：直接查库
        from .models import Station
        with _repo.Session() as s:
            items = [{"id": st.id, "name": st.name, "lat": st.lat, "lng": st.lng,
                      "open_quota": st.open_quota, "booked_count": st.booked_count}
                     for st in s.query(Station).all()]

    def dist(x):
        return math.hypot((x.get("lat") or 0) - lat, (x.get("lng") or 0) - lng)

    items = [x for x in items if x.get("open_quota", 0) - x.get("booked_count", 0) > 0]
    items.sort(key=lambda x: (dist(x), -(x["open_quota"] - x["booked_count"])))
    return [{"id": x["id"], "name": x["name"],
             "remaining": x["open_quota"] - x["booked_count"],
             "distance": round(dist(x), 4),
             "slots": ["10:00", "14:00", "16:00"]} for x in items[:limit]]


@app.post("/api/v1/vault/tokenize")
def vault_tokenize(body: VaultIn):
    return {"token": _vault.tokenize(body.type, body.value)}


@app.post("/api/v1/vault/detokenize")
def vault_detokenize(body: DetokenizeIn):
    try:
        return {"value": _vault.detokenize(body.token, body.reason)}
    except (ValueError, KeyError) as e:
        raise AppError(400, "DETOKENIZE_FAILED", str(e))


@app.post("/api/v1/webhook/receiver")
async def webhook_receiver(request: Request):
    raw = await request.body()
    result = _receiver.handle(
        raw_body=raw,
        event_id=request.headers.get("X-ClawHunt-Event-Id", ""),
        timestamp=int(request.headers.get("X-ClawHunt-Timestamp", "0")),
        signature=request.headers.get("X-ClawHunt-Signature", ""),
    )
    return JSONResponse(status_code=result["status"], content=result["body"])


@app.get("/api/v1/events/types")
def event_types():
    return {"types": list(EVENT_TYPES)}
