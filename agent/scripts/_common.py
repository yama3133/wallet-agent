"""共通ユーティリティ。スクリプト間で state.json を介して ARN/ID を受け渡す。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = AGENT_DIR / "state.json"
ENV_PATH = AGENT_DIR / ".env"

load_dotenv(ENV_PATH)


def region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")


def env(key: str, default: str | None = None) -> str:
    v = os.environ.get(key, default)
    if v is None or v == "":
        raise RuntimeError(f"環境変数 {key} が設定されていない。{ENV_PATH} を確認")
    return v


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(updates: dict[str, Any]) -> dict[str, Any]:
    state = load_state()
    state.update(updates)
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))
    return state


def require_state(key: str) -> Any:
    state = load_state()
    if key not in state:
        raise RuntimeError(f"state.json に {key} がない。前段のスクリプトを実行")
    return state[key]


def print_header(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}")
