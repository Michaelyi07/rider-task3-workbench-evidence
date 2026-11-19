"""审计留痕：detokenize / reject / transition 写入，供 AC5 与任务5对接。

本任务只做审计"写入 + 查询"接口（明文审计实现属任务5，明确排除）。
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEntry:
    id: str
    action: str
    actor: str
    target: str
    reason: str
    ts: str


class AuditTrail:
    def __init__(self):
        self._entries: list[AuditEntry] = []

    def record(self, action: str, actor: str, target: str, reason: str = "") -> AuditEntry:
        e = AuditEntry(
            id=str(uuid.uuid4()), action=action, actor=actor, target=target,
            reason=reason, ts=datetime.now(timezone.utc).isoformat(),
        )
        self._entries.append(e)
        return e

    def query(self, action: str | None = None, target: str | None = None) -> list[dict]:
        out = [asdict(e) for e in self._entries]
        if action is not None:
            out = [e for e in out if e["action"] == action]
        if target is not None:
            out = [e for e in out if e["target"] == target]
        return out

    def __len__(self) -> int:
        return len(self._entries)
