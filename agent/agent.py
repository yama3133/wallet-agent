"""Strands Agent 本体。Claude Sonnet 4.6 + 承認ゲートツール 3 つ。

PoC 段階：
- 承認状態は agent/.approvals.json で管理（後で DynamoDB に差し替え）
- 決済本体は AgentCorePaymentsPlugin（auto_payment=False） → 承認後にツール経由で呼ぶ
- ProcessPayment は Privy signer 問題で失敗する可能性が高いが、try/except で囲ってフローを完走させる

CLI で対話する：
  $ python agent.py
  > 市況サマリが欲しい、最大 $0.05 まで払って良い

エージェントは候補を探す → 承認カードを発行 → 別ターミナルで承認 → 決済 → 結果を返す。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from strands import Agent
from strands.tools import tool

# 同梱モジュール
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "scripts"))  # _common を読みたい

load_dotenv(HERE / ".env")

from tools import approvals, x402_resources  # noqa: E402

LOG = logging.getLogger("wallet-agent")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


def _state() -> dict[str, Any]:
    p = HERE / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool
def search_paid_resources(query: str = "") -> list[dict]:
    """有料 API / x402 リソースをカタログから検索する。

    Args:
        query: キーワード（空文字列なら全件）。

    Returns:
        マッチしたリソース情報のリスト。各要素に id / title / description /
        url / expected_amount_usd / expected_currency / expected_network が入る。
    """
    return x402_resources.search(query)


@tool
def request_payment_approval(
    resource_id: str,
    amount_usd: str,
    justification: str,
) -> dict:
    """ユーザーに支払い承認を求める。承認カードを発行して結果を待つ。

    Args:
        resource_id: search_paid_resources で得た id。
        amount_usd: 支払う見込み額（USD 表記、例 "0.001"）。
        justification: なぜこの支払いがユーザーの依頼に必要かの短い説明。

    Returns:
        decision フィールドを含む承認結果（APPROVED / REJECTED / EXPIRED）。
    """
    resources = x402_resources.search(resource_id)
    if not resources:
        return {"status": "ERROR", "error": f"resource_id {resource_id} は未登録"}
    entry = approvals.request_approval(
        resource=resource_id, amount_usd=amount_usd, justification=justification
    )
    print(
        f"\n=== 承認カード ===\n"
        f"approval_id: {entry['approval_id']}\n"
        f"resource: {resource_id} ({resources[0]['title']})\n"
        f"amount: ${amount_usd} USD\n"
        f"justification: {justification}\n"
        f"別ターミナルで以下を実行して承認/拒否してください:\n"
        f"  python agent.py approve {entry['approval_id']}\n"
        f"  python agent.py reject  {entry['approval_id']}\n"
        f"=================\n"
    )
    if os.environ.get("WALLET_AGENT_AUTO_APPROVE") == "1":
        print("AUTO_APPROVE: APPROVED として進める")
        return approvals.decide(entry["approval_id"], "APPROVED", reason="auto-approved (demo mode)")
    final = approvals.wait_for_decision(entry["approval_id"])
    return final


@tool
def execute_x402_payment(resource_id: str, payment_session_id: str | None = None) -> dict:
    """承認済みの x402 リソースを叩いて支払い + コンテンツ取得を行う。

    Args:
        resource_id: search_paid_resources で得た id。
        payment_session_id: 既存セッションID。None なら新規作成。

    Returns:
        result フィールドにマーチャントから取得した本文（最大 2000 文字）。
        署名/決済が失敗した場合は error にメッセージを入れて返す。
    """
    import urllib.error
    import urllib.request
    import uuid as _uuid

    import boto3
    from bedrock_agentcore.payments import PaymentManager

    state = _state()
    manager_arn = state.get("payment_manager_arn")
    instrument_id = state.get("payment_instrument_id")
    user_id = state.get("test_user_id")
    if not (manager_arn and instrument_id and user_id):
        return {"status": "ERROR", "error": "state.json に AgentCore リソース情報がない"}

    resources = x402_resources.search(resource_id)
    if not resources:
        return {"status": "ERROR", "error": f"resource_id {resource_id} は未登録"}
    url = resources[0]["url"]

    region = os.environ.get("AWS_REGION", "us-east-1")
    dp = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        endpoint_url=f"https://bedrock-agentcore.{region}.amazonaws.com",
    )

    if payment_session_id is None:
        sess_resp = dp.create_payment_session(
            userId=user_id,
            paymentManagerArn=manager_arn,
            expiryTimeInMinutes=int(os.environ.get("PAYMENT_SESSION_EXPIRY_MINUTES", "60")),
            limits={
                "maxSpendAmount": {
                    "value": os.environ.get("PAYMENT_SESSION_MAX_USD", "1.00"),
                    "currency": "USD",
                }
            },
            clientToken=str(_uuid.uuid4()),
        )
        payment_session_id = sess_resp["paymentSession"]["paymentSessionId"]

    # 402 取得
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            body = r.read().decode()
            return {"status": "FREE", "body": body[:2000]}
    except urllib.error.HTTPError as e:
        if e.code != 402:
            return {"status": "ERROR", "error": f"HTTP {e.code}: {e.reason}"}
        payment_required = {
            "statusCode": e.code,
            "headers": dict(e.headers),
            "body": e.read().decode(),
        }

    # 署名生成
    manager = PaymentManager(payment_manager_arn=manager_arn, region_name=region)
    try:
        headers = manager.generate_payment_header(
            user_id=user_id,
            payment_instrument_id=instrument_id,
            payment_session_id=payment_session_id,
            payment_required_request=payment_required,
            client_token=str(_uuid.uuid4()),
        )
    except Exception as e:
        return {
            "status": "PAYMENT_FAILED",
            "error": str(e),
            "hint": "Privy の wallet と Authorization Key の signer 関係を確認",
            "payment_session_id": payment_session_id,
        }

    # リトライ
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return {
                "status": "PAID",
                "body": body[:2000],
                "payment_session_id": payment_session_id,
            }
    except urllib.error.HTTPError as e:
        return {
            "status": "MERCHANT_REJECTED",
            "error": f"HTTP {e.code}: {e.read().decode()[:500]}",
            "payment_session_id": payment_session_id,
        }


# ----------------------------------------------------------------------
# Agent
# ----------------------------------------------------------------------

SYSTEM_PROMPT = """\
あなたはユーザーの代わりに有料の情報 API にアクセスする買い物エージェントです。

ルール:
- ユーザーの依頼に対し、search_paid_resources で適切なリソースを探す
- 支払いが必要な場合、必ず request_payment_approval を呼んで人間に承認を求める
- 承認結果が APPROVED でないなら、決済しない。代わりに、なぜ実行できないかをユーザーに伝える
- APPROVED なら execute_x402_payment を呼んで本文を取得し、内容を要約してユーザーに返す
- 1依頼につき承認は最大1回。APPROVED のあとに追加の支払いが要るなら、別途承認を取り直す
- すべての応答は日本語で簡潔に。
"""


def build_agent() -> Agent:
    from strands.models import BedrockModel

    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-6",
        region_name=region,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_paid_resources, request_payment_approval, execute_x402_payment],
    )


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def cli() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("approve", "reject"):
        if len(args) < 2:
            print("usage: python agent.py approve <approval_id>")
            sys.exit(1)
        decision = "APPROVED" if args[0] == "approve" else "REJECTED"
        result = approvals.decide(args[1], decision)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        return

    if args and args[0] == "pending":
        for entry in approvals.list_pending():
            print(json.dumps(entry, indent=2, default=str, ensure_ascii=False))
        return

    if args and args[0] == "run":
        # 単発実行モード: python agent.py run "<prompt>"
        prompt = " ".join(args[1:]) if len(args) > 1 else ""
        if not prompt:
            print("usage: python agent.py run \"<prompt>\"")
            sys.exit(1)
        print(f"あなた> {prompt}\n")
        agent = build_agent()
        result = agent(prompt)
        print(f"\nエージェント> {result}")
        return

    print("wallet-agent: 対話モード。Ctrl-D で終了。")
    agent = build_agent()
    try:
        while True:
            try:
                user_input = input("\nあなた> ").strip()
            except EOFError:
                print()
                return
            if not user_input:
                continue
            result = agent(user_input)
            # Strands Agent の最終応答テキスト
            try:
                text = str(result)
            except Exception:
                text = repr(result)
            print(f"\nエージェント> {text}")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    cli()
