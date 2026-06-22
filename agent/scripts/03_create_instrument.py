"""Step 3: ユーザー向けの PaymentInstrument（Embedded Wallet）を作成する。

実行後に redirectUrl が出力される。ユーザーはそのURLにブラウザでアクセスして、
入金とエージェントへの署名権限付与を行う必要がある（手動ステップ）。

入金が終わるまで status は ACTIVE にならない。
"""
from __future__ import annotations

import uuid

import boto3

from _common import env, print_header, region, require_state, save_state


def main() -> None:
    print_header("Step 3: PaymentInstrument 作成")

    manager_arn = require_state("payment_manager_arn")
    connector_id = require_state("payment_connector_id")
    user_id = env("TEST_USER_ID")
    user_email = env("TEST_USER_EMAIL")

    dp = boto3.client(
        "bedrock-agentcore",
        region_name=region(),
        endpoint_url=f"https://bedrock-agentcore.{region()}.amazonaws.com",
    )

    inst = dp.create_payment_instrument(
        userId=user_id,
        paymentManagerArn=manager_arn,
        paymentConnectorId=connector_id,
        paymentInstrumentType="EMBEDDED_CRYPTO_WALLET",
        paymentInstrumentDetails={
            "embeddedCryptoWallet": {
                "network": "ETHEREUM",
                "linkedAccounts": [{"email": {"emailAddress": user_email}}],
            }
        },
        clientToken=str(uuid.uuid4()),
    )
    instrument_id = inst["paymentInstrumentId"]
    redirect_url = inst.get("paymentInstrumentDetails", {}).get("redirectUrl")
    print(f"InstrumentId: {instrument_id}")
    print(f"\n=== 手動ステップ ===")
    print("以下のURLをブラウザで開き、ウォレットを入金してエージェントに署名権限を付与:")
    print(f"  {redirect_url}")
    print("テスト用なら base-sepolia の USDC を faucet から入手して入金")

    save_state(
        {
            "payment_instrument_id": instrument_id,
            "payment_instrument_redirect_url": redirect_url,
            "test_user_id": user_id,
        }
    )


if __name__ == "__main__":
    main()
