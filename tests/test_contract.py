"""AC7：OpenAPI 契约测试 —— 路径、字段、事件类型、错误体、响应无敏感明文。"""
import asyncio
import json

import httpx

import src.main as main
from src.webhook import EVENT_TYPES


def test_openapi_has_required_paths():
    schema = main.app.openapi()
    paths = schema["paths"]
    required = [
        "/api/v1/candidates", "/api/v1/bookings", "/api/v1/leads/import",
        "/api/v1/vault/tokenize", "/api/v1/vault/detokenize",
        "/api/v1/webhook/receiver", "/api/v1/stations/recommend",
    ]
    for p in required:
        assert p in paths, p


def test_candidate_response_fields_present():
    schema = main.app.openapi()
    props = schema["components"]["schemas"]["CandidateOut"]["properties"]
    for field in ["phone_masked", "status", "source_channel", "station_id",
                  "health_cert", "job_type", "consent_version"]:
        assert field in props, field
    assert "phone_token" not in props
    assert "phone" not in props


def test_six_event_types():
    assert len(EVENT_TYPES) == 6
    assert set(EVENT_TYPES) == {
        "candidate.created", "candidate.updated", "candidate.completed",
        "booking.created", "booking.cancelled", "handoff.requested",
    }


def test_error_body_shape():
    """校验错误体 {code, message}。"""
    async def run():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            return await c.post("/api/v1/candidates/xxx/reveal", json={"reason": "x"})
    r = asyncio.run(run())
    assert r.status_code == 422
    body = r.json()
    assert "code" in body and "message" in body


def test_openapi_json_serializable():
    s = main.app.openapi()
    assert "/openapi.json" not in s["paths"]  # 由框架提供，无需自定义
    assert json.loads(json.dumps(s)) == s
