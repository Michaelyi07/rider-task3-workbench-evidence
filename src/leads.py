"""100 条线索导入去重（手机号 token）+ 分配规则 (AC1)。

去重：归一化手机号 -> 确定性 token -> ON CONFLICT(phone_token) DO NOTHING（内存层用 set）。
分配：by_station / by_region / round_robin（itertools.cycle）。
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass

from .vault import tokenize


@dataclass
class Lead:
    phone: str
    area_text: str
    source_channel: str
    station_id: str | None = None
    job_type: str = "undecided"


@dataclass
class ImportResult:
    inserted: int
    duplicates_skipped: int
    assignments: dict[str, int]          # station_id -> count
    rows: list[dict]                     # 已落库 candidate dict（含 phone_token）


REGION_STATION_MAP = {
    "浦东": "S1", "徐汇": "S2", "静安": "S3", "闵行": "S4",
}


def assignment_for(lead: Lead, rule: str, active_stations: list[str], cycle) -> str:
    if rule == "by_station":
        if not lead.station_id:
            raise ValueError("by_station rule requires station_id")
        return lead.station_id
    if rule == "by_region":
        for prefix, sid in REGION_STATION_MAP.items():
            if lead.area_text.startswith(prefix):
                return sid
        return active_stations[0]
    if rule == "round_robin":
        return next(cycle)
    raise ValueError(f"unknown assignment rule: {rule}")


def import_leads(
    leads: list[Lead],
    rule: str = "round_robin",
    active_stations: list[str] | None = None,
    existing_tokens: set[str] | None = None,
) -> ImportResult:
    """按 phone_token 去重导入，返回 inserted/duplicates + 分配统计。

    纯函数：不写 DB；调用方（repo/API）负责持久化。existing_tokens 支持跨批增量去重。
    """
    active_stations = active_stations or ["S1", "S2", "S3", "S4"]
    seen = set(existing_tokens or ())
    cycle = itertools.cycle(active_stations)
    inserted_rows: list[dict] = []
    assignments: dict[str, int] = {s: 0 for s in active_stations}
    dup = 0

    for lead in leads:
        token = tokenize("phone", lead.phone)
        if token in seen:                       # ON CONFLICT DO NOTHING 的内存等价
            dup += 1
            continue
        seen.add(token)
        sid = assignment_for(lead, rule, active_stations, cycle)
        if sid not in assignments:
            assignments[sid] = 0
        assignments[sid] += 1
        inserted_rows.append({
            "id": str(uuid.uuid4()),
            "name_token": None,
            "phone_token": token,
            "birth_ym": None,
            "area_text": lead.area_text,
            "job_type": lead.job_type,
            "has_ebike": None,
            "start_text": None,
            "experience_text": None,
            "health_cert": "unknown",
            "source_channel": lead.source_channel,
            "station_id": sid,
            "status": "new",
            "consent_version": "v1",
            "consent_at": None,
            "retention_until": None,
        })
    return ImportResult(
        inserted=len(inserted_rows), duplicates_skipped=dup,
        assignments=assignments, rows=inserted_rows,
    )
