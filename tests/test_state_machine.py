"""AC2：候选人状态机覆盖所有状态对（8x8=64）。

注：契约 candidate.status 明确定义 8 个状态。知识卡正文"9 状态"处把
booking.cancelled 一并计入（并注明它不是 candidate 状态）。本测试严格按契约
的 8 个 candidate 状态做全笛卡尔积 64 对；如需覆盖 9x9=81，则第 9 个须为
booking 状态机（见 VERIFICATION.md 边界说明）。
"""

import pytest

from src.state_machine import ALLOWED, STATES, IllegalTransition, transition, is_legal

ALL_PAIRS = [(a, b) for a in STATES for b in STATES]


def test_all_states_defined():
    assert len(STATES) == 8
    assert set(ALLOWED) == set(STATES)


@pytest.mark.parametrize("cur,nxt", ALL_PAIRS)
def test_every_state_pair(cur, nxt):
    legal = nxt in ALLOWED[cur]
    assert is_legal(cur, nxt) is legal
    if legal:
        assert transition(cur, nxt) == nxt
    else:
        with pytest.raises(IllegalTransition):
            transition(cur, nxt)


def test_pair_count_is_64():
    assert len(ALL_PAIRS) == 64
