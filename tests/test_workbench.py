"""AC5：列表脱敏、查看完整号需理由+vault、标记不合适需理由、审计。"""
import asyncio
import uuid

import httpx

import src.main as main
from src.vault import tokenize

BASE = "http://testserver"


def _seed_candidate(phone="13800008000", name="王小明", status="new"):
    token = tokenize("phone", phone)
    main._vault.tokenize("phone", phone)          # vault store 里登记明文（mock 保险箱）
    name_t = main._vault.tokenize("name", name)
    cid = str(uuid.uuid4())
    row = {"id": cid, "name_token": name_t, "phone_token": token,
           "birth_ym": "1995-06", "area_text": "浦东张江镇", "job_type": "fulltime",
           "has_ebike": True, "start_text": "立即", "experience_text": "2年",
           "health_cert": "holding", "source_channel": "channel_a",
           "station_id": "S1", "status": status, "consent_version": "v1",
           "consent_at": None, "retention_until": None}
    main._repo.ensure_candidate(row)
    return cid


def _get(path):
    async def run():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as c:
            return await c.get(path)
    return asyncio.run(run())


def _post(path, payload):
    async def run():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as c:
            return await c.post(path, json=payload)
    return asyncio.run(run())


def test_list_masks_phone_and_no_plaintext():
    _seed_candidate()
    r = _get("/api/v1/candidates")
    assert r.status_code == 200
    body = r.text
    row = r.json()[0]
    assert row["phone_masked"] == "138****8000"
    assert "13800008000" not in body           # 列表无明文
    assert "phone_token" not in body           # 列表无 token
    assert "phone" not in [k for k in row]     # 无明文字段名


def test_reveal_requires_reason():
    cid = _seed_candidate()
    r = _post(f"/api/v1/candidates/{cid}/reveal", {"reason": "短"})
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_reveal_with_reason_writes_audit():
    cid = _seed_candidate()
    r = _post(f"/api/v1/candidates/{cid}/reveal", {"reason": "电话核实面试时间"})
    assert r.status_code == 200
    assert r.json()["phone"] == "13800008000"
    assert r.json()["one_time"] is True
    assert len(main._audit.query(action="detokenize")) == 1


def test_reject_requires_reason():
    cid = _seed_candidate()
    r = _post(f"/api/v1/candidates/{cid}/reject", {"reason": ""})
    assert r.status_code == 422


def test_reject_with_reason_changes_status_and_audits():
    cid = _seed_candidate()
    r = _post(f"/api/v1/candidates/{cid}/reject", {"reason": "不符合岗位要求"})
    assert r.status_code == 200
    assert main._repo.get_candidate(cid)["status"] == "rejected"
    assert len(main._audit.query(action="reject")) == 1


def test_illegal_transition_rejected():
    cid = _seed_candidate(status="new")
    r = _post(f"/api/v1/candidates/{cid}/transition", {"next": "hired"})
    assert r.status_code == 400
    assert r.json()["code"] == "ILLEGAL_TRANSITION"
    assert main._repo.get_candidate(cid)["status"] == "new"   # 状态不变
