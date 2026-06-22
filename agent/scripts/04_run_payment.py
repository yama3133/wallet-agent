"""Step 4: PaymentSession を作成し、x402 マーチャントに対して決済を実行する。

このスクリプトでは:
  1. PaymentInstrument が ACTIVE になっているか確認
  2. PaymentSession 作成（spending limit + expiry）
  3. テスト用 x402 マーチャントにリクエスト → 402 → process_payment → リトライ

エージェントを介さず、決定論的なコードで x402 フローを通すための疎通テスト。
"""
from __future__ import annotations

import json
import time
import uuid

import boto3
import urllib.request
import urllib.error

from _common import env, print_header, region, require_state, save_state


def wait_instrument_active(dp, manager_arn: str, instrument_id: str) -> None:
    print("PaymentInstrument の status を確認")
    for _ in range(60):
        inst = dp.get_payment_instrument(
            paymentManagerArn=manager_arn, paymentInstrumentId=instrument_id
        )
        st = inst["status"]
        print(f"  status: {st}")
        if st == "ACTIVE":
            return
        if st in ("FAILED", "DELETED"):
            raise RuntimeError(f"Instrument が {st} になっている")
        time.sleep(10)
    raise TimeoutError("Instrument が ACTIVE にならない。ウォレット入金と権限付与を確認")


def create_session(dp, manager_arn: str, user_id: str) -> str:
    max_usd = env("PAYMENT_SESSION_MAX_USD", "1.00")
    expiry_min = int(env("PAYMENT_SESSION_EXPIRY_MINUTES", "60"))
    sess = dp.create_payment_session(
        userId=user_id,
        paymentManagerArn=manager_arn,
        expiryTimeInMinutes=expiry_min,
        limits={"maxSpendAmount": {"value": str(max_usd), "currency": "USD"}},
        clientToken=str(uuid.uuid4()),
    )
    sid = sess["paymentSessionId"]
    print(f"PaymentSession: {sid}  (max ${max_usd} / {expiry_min}min)")
    return sid


def fetch_402(url: str) -> dict:
    """マーチャントを叩いて 402 のペイロードを取得。200 ならその場で終了。"""
    print(f"GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            body = r.read().decode()
            print(f"  200 OK ({len(body)} bytes) - 課金なしで取れた")
            return {"statusCode": r.status, "headers": dict(r.headers), "body": body}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        headers = dict(e.headers)
        print(f"  {e.code} {e.reason}")
        if e.code != 402:
            raise RuntimeError(f"402 を期待したが {e.code}")
        try:
            payload = json.loads(body)
            print(f"  payload: {json.dumps(payload, indent=2)[:500]}")
        except Exception:
            print(f"  body: {body[:300]}")
        return {"statusCode": e.code, "headers": headers, "body": body}


def main() -> None:
    print_header("Step 4: PaymentSession 作成 + x402 決済")

    manager_arn = require_state("payment_manager_arn")
    instrument_id = require_state("payment_instrument_id")
    user_id = require_state("test_user_id")
    merchant = env("TEST_MERCHANT_URL")

    dp = boto3.client(
        "bedrock-agentcore",
        region_name=region(),
        endpoint_url=f"https://bedrock-agentcore.{region()}.amazonaws.com",
    )

    wait_instrument_active(dp, manager_arn, instrument_id)
    session_id = create_session(dp, manager_arn, user_id)

    print("\nマーチャントにリクエスト")
    res = fetch_402(merchant)
    if res["statusCode"] == 200:
        save_state({"payment_session_id": session_id, "last_run": "no_payment_needed"})
        return

    print("\nPaymentManager 経由で支払いヘッダを生成")
    from bedrock_agentcore.payments import PaymentManager

    manager = PaymentManager(payment_manager_arn=manager_arn, region_name=region())
    headers = manager.generate_payment_header(
        user_id=user_id,
        payment_instrument_id=instrument_id,
        payment_session_id=session_id,
        payment_required_request=res,
        client_token=str(uuid.uuid4()),
    )
    print(f"X-PAYMENT ヘッダ生成: {list(headers.keys())}")

    print("\nリトライ")
    req = urllib.request.Request(merchant, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            print(f"  {r.status} ({len(body)} bytes)")
            print(f"  body 先頭: {body[:300]}")
    except urllib.error.HTTPError as e:
        print(f"  {e.code} {e.reason}: {e.read().decode()[:300]}")
        raise

    print("\n--- セッション集計 ---")
    final = dp.get_payment_session(
        paymentManagerArn=manager_arn, paymentSessionId=session_id
    )
    print(json.dumps(final, indent=2, default=str)[:800])

    save_state({"payment_session_id": session_id, "last_run": "paid"})


if __name__ == "__main__":
    main()
