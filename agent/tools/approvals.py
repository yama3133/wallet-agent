"""承認ゲートのローカル実装。

PoC ではDynamoDBの代わりに agent/.approvals.json で承認状態を管理する。
本番では同じインターフェースのままDynamoDB backendに差し替える前提。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

APPROVALS_PATH = Path(__file__).resolve().parent.parent / ".approvals.json"


def _load() -> dict[str, Any]:
    if APPROVALS_PATH.exists():
        return json.loads(APPROVALS_PATH.read_text())
    return {}


def _save(data: dict[str, Any]) -> None:
    APPROVALS_PATH.write_text(json.dumps(data, indent=2, default=str))


def request_approval(
    *,
    resource: str,
    amount_usd: str,
    justification: str,
    ttl_seconds: int = 120,
) -> dict[str, Any]:
    """承認を要求し pending エントリーを書き出す。UIはこのファイルを購読する。"""
    approval_id = str(uuid.uuid4())
    entry = {
        "approval_id": approval_id,
        "status": "PENDING",
        "resource": resource,
        "amount_usd": amount_usd,
        "justification": justification,
        "created_at": time.time(),
        "expires_at": time.time() + ttl_seconds,
        "decision": None,
    }
    data = _load()
    data[approval_id] = entry
    _save(data)
    return entry


def get_approval(approval_id: str) -> dict[str, Any] | None:
    return _load().get(approval_id)


def decide(approval_id: str, decision: str, *, reason: str = "") -> dict[str, Any]:
    """ユーザーが承認/拒否を記録する（CLI から呼ぶ）。"""
    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision must be APPROVED or REJECTED")
    data = _load()
    if approval_id not in data:
        raise KeyError(approval_id)
    data[approval_id]["status"] = decision
    data[approval_id]["decision"] = decision
    data[approval_id]["reason"] = reason
    data[approval_id]["decided_at"] = time.time()
    _save(data)
    return data[approval_id]


def list_pending() -> list[dict[str, Any]]:
    data = _load()
    return [v for v in data.values() if v["status"] == "PENDING"]


def wait_for_decision(approval_id: str, *, poll_sec: float = 1.0) -> dict[str, Any]:
    """承認が PENDING のままなら ttl まで待つ。CLI 側で decide() するのを待つ用途。"""
    while True:
        entry = get_approval(approval_id)
        if entry is None:
            raise KeyError(approval_id)
        if entry["status"] != "PENDING":
            return entry
        if time.time() > entry["expires_at"]:
            entry["status"] = "EXPIRED"
            data = _load()
            data[approval_id] = entry
            _save(data)
            return entry
        time.sleep(poll_sec)
