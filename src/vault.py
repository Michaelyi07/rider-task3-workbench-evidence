"""保险箱 mock + 脱敏 (AC5, 共享契约 Vault mock)。

token 用确定性 HMAC(pepper, 归一化值)，相同值必得相同 token —— AC1 去重基石。
真实值只存"保险箱"(mock 内存字典)，业务库只存 token。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

_DEFAULT_PEPPER = b"clawhunt-task3-demo-pepper-NOT-FOR-PROD"


def normalize_phone(raw: str) -> str:
    """归一化手机号：去空格/连字符，去 +86/86 前缀，只保留 11 位数字。"""
    s = re.sub(r"[\s\-()]", "", str(raw))
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


def tokenize(field_type: str, value: str, pepper: bytes | None = None) -> str:
    pepper = pepper if pepper is not None else os.getenv("VAULT_PEPPER", "").encode() or _DEFAULT_PEPPER
    v = normalize_phone(value) if field_type == "phone" else value.strip()
    digest = hmac.new(pepper, v.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{field_type}_{digest}"


class VaultMock:
    """契约 mock：tokenize/detokenize，detokenize 写审计。"""

    def __init__(self, pepper: bytes | None = None, audit=None):
        self.pepper = pepper or (_DEFAULT_PEPPER)
        self._store: dict[str, str] = {}
        self.audit = audit

    def tokenize(self, field_type: str, value: str) -> str:
        token = tokenize(field_type, value, self.pepper)
        self._store[token] = normalize_phone(value) if field_type == "phone" else value
        return token

    def detokenize(self, token: str, reason: str) -> str:
        if not reason or len(reason.strip()) < 5:
            raise ValueError("reason must be at least 5 characters")
        if token not in self._store:
            raise KeyError("unknown token")
        if self.audit is not None:
            self.audit.record("detokenize", actor="recruiter", target=token, reason=reason)
        return self._store[token]

    def masked(self, token: str, field_type: str = "phone") -> str:
        """仅用于列表脱敏展示，不写审计、不返回明文。"""
        value = self._store.get(token, "")
        return mask_phone(value) if field_type == "phone" else mask_name(value)


def mask_phone(phone: str) -> str:
    """13800008000 -> 138****8000；不足 11 位按最小必要脱敏。"""
    s = re.sub(r"\D", "", phone)
    if len(s) == 11:
        return f"{s[:3]}****{s[-4:]}"
    if len(s) <= 4:
        return "*" * len(s)
    return f"{s[:2]}****{s[-2:]}"


def mask_name(name: str) -> str:
    """王小明 -> 王**；单字 -> *。"""
    s = name.strip()
    if not s:
        return ""
    if len(s) == 1:
        return "*"
    return s[0] + "*" * (len(s) - 1)
