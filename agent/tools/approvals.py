"""承認ゲートのストア。

WALLET_AGENT_STORAGE=local: agent/.approvals.json（PoC・ローカル開発用）
WALLET_AGENT_STORAGE=dynamo: DynamoDB wallet_agent_approvals テーブル（クラウド運用）

公開API:
  request_approval / get_approval / decide / list_pending / wait_for_decision
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

APPROVALS_PATH = Path(__file__).resolve().parent.parent / ".approvals.json"
TABLE_NAME = os.environ.get("WALLET_AGENT_APPROVALS_TABLE", "wallet_agent_approvals")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _backend() -> str:
    return os.environ.get("WALLET_AGENT_STORAGE", "local")


# ---------------------------- local JSON ----------------------------

def _local_load() -> dict[str, Any]:
    if APPROVALS_PATH.exists():
        return json.loads(APPROVALS_PATH.read_text())
    return {}


def _local_save(data: dict[str, Any]) -> None:
    APPROVALS_PATH.write_text(json.dumps(data, indent=2, default=str))


# ---------------------------- DynamoDB ----------------------------

_table = None


def _dynamo_table():
    global _table
    if _table is None:
        import boto3
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    return _table


def _dynamo_get(approval_id: str) -> dict[str, Any] | None:
    r = _dynamo_table().get_item(Key={"approval_id": approval_id})
    return r.get("Item")


def _dynamo_put(item: dict[str, Any]) -> None:
    _dynamo_table().put_item(Item=item)


# ---------------------------- public API ----------------------------

def request_approval(
    *,
    resource: str,
    amount_usd: str,
    justification: str,
    ttl_seconds: int = 120,
    task_id: str | None = None,
) -> dict[str, Any]:
    approval_id = str(uuid.uuid4())
    now = time.time()
    entry: dict[str, Any] = {
        "approval_id": approval_id,
        "task_id": task_id or "_default_",
        "status": "PENDING",
        "resource": resource,
        "amount_usd": str(amount_usd),
        "justification": justification,
        "created_at": str(now),
        "expires_at": str(now + ttl_seconds),
        "decision": None,
    }
    if _backend() == "dynamo":
        _dynamo_put(entry)
    else:
        data = _local_load()
        data[approval_id] = entry
        _local_save(data)
    return entry


def get_approval(approval_id: str) -> dict[str, Any] | None:
    if _backend() == "dynamo":
        return _dynamo_get(approval_id)
    return _local_load().get(approval_id)


def decide(approval_id: str, decision: str, *, reason: str = "") -> dict[str, Any]:
    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision must be APPROVED or REJECTED")
    if _backend() == "dynamo":
        existing = _dynamo_get(approval_id)
        if existing is None:
            raise KeyError(approval_id)
        existing.update(
            status=decision,
            decision=decision,
            reason=reason,
            decided_at=str(time.time()),
        )
        _dynamo_put(existing)
        return existing
    data = _local_load()
    if approval_id not in data:
        raise KeyError(approval_id)
    data[approval_id]["status"] = decision
    data[approval_id]["decision"] = decision
    data[approval_id]["reason"] = reason
    data[approval_id]["decided_at"] = str(time.time())
    _local_save(data)
    return data[approval_id]


def list_pending() -> list[dict[str, Any]]:
    if _backend() == "dynamo":
        # PoC: scan は本数少ない前提。本番はGSI（status, created_at）を生やすのが妥当。
        r = _dynamo_table().scan(
            FilterExpression="#s = :p",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":p": "PENDING"},
        )
        return r.get("Items", [])
    return [v for v in _local_load().values() if v["status"] == "PENDING"]


def wait_for_decision(approval_id: str, *, poll_sec: float = 1.0) -> dict[str, Any]:
    while True:
        entry = get_approval(approval_id)
        if entry is None:
            raise KeyError(approval_id)
        if entry["status"] != "PENDING":
            return entry
        if time.time() > float(entry["expires_at"]):
            entry["status"] = "EXPIRED"
            if _backend() == "dynamo":
                _dynamo_put(entry)
            else:
                data = _local_load()
                data[approval_id] = entry
                _local_save(data)
            return entry
        time.sleep(poll_sec)
