"""测试夹具：每个测试重置内存依赖，避免相互污染；统一 utf-8 输出。"""
import sys

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from src.audit import AuditTrail
from src.repo import InMemoryRepository
from src.vault import VaultMock
from src.webhook import Receiver
import src.main as main


@pytest.fixture(autouse=True)
def fresh_state():
    audit = AuditTrail()
    vault = VaultMock(audit=audit)
    main.configure(repo=InMemoryRepository(), vault=vault, audit=audit,
                   receiver=Receiver(secret="test-secret"))
    yield
