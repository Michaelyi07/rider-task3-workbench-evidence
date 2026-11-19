"""候选人状态机 (AC2)。

契约 8 个 candidate 状态；知识卡提到"9 状态"，其中第 9 个是 booking.cancelled
（预约状态，非候选人状态），故 candidate 状态集按契约严格取 8 个，覆盖 8x8=64 对。
合法流转表来自知识卡，非法跃迁抛 IllegalTransition 且不改库。
"""

from __future__ import annotations

STATES: tuple[str, ...] = (
    "new", "collecting", "complete", "booked",
    "interviewed", "hired", "rejected", "handoff",
)

ALLOWED: dict[str, set[str]] = {
    "new":        {"collecting", "rejected", "handoff"},
    "collecting": {"complete", "new", "rejected", "handoff"},
    "complete":   {"booked", "rejected", "handoff"},
    "booked":     {"interviewed", "rejected", "handoff"},
    "interviewed":{"hired", "rejected", "handoff"},
    "handoff":    {"collecting", "complete", "booked", "interviewed", "rejected"},
    "hired":      set(),   # 终态
    "rejected":   set(),   # 终态
}

# 合法对数量（用于测试断言，避免写死方差）
LEGAL_PAIRS = sum(len(v) for v in ALLOWED.values())


class IllegalTransition(ValueError):
    def __init__(self, current: str, nxt: str):
        self.current, self.nxt = current, nxt
        super().__init__(f"illegal candidate transition: {current} -> {nxt}")


def is_legal(current: str, nxt: str) -> bool:
    return current in ALLOWED and nxt in ALLOWED[current]


def transition(current: str, nxt: str) -> str:
    """校验并返回目标状态；非法则抛 IllegalTransition。"""
    if current not in ALLOWED:
        raise IllegalTransition(current, nxt)
    if nxt not in ALLOWED[current]:
        raise IllegalTransition(current, nxt)
    return nxt
