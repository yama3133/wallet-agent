"""Step 6: 既存 PaymentInstrument を削除し、linkedAccounts に developerJwt を渡して
Authorization Key 紐付きで wallet を作り直す試み。

developerJwt.kid に Authorization Key ID、sub に user 識別子を入れる。
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _common import env, print_header, region, require_state, save_state


def main() -> None:
    print_header("Step 6: PaymentInstrument 削除 → developerJwt で再作成")

    manager_arn = require_state("payment_manager_arn")
    connector_id = require_state("payment_connector_id")
    user_id = env("TEST_USER_ID")
    old_id = require_state("payment_instrument_id")
    signer_id = env("PRIVY_AUTHORIZATION_ID")

    dp = boto3.client(
        "bedrock-agentcore",
        region_name=region(),
        endpoint_url=f"https://bedrock-agentcore.{region()}.amazonaws.com",
    )

    print(f"古い Instrument 削除: {old_id}")
    try:
        dp.delete_payment_instrument(
            userId=user_id,
            paymentManagerArn=manager_arn,
            paymentConnectorId=connector_id,
            paymentInstrumentId=old_id,
        )
        print("  OK")
    except Exception as e:
        print(f"  delete エラー (続行): {e}")

    time.sleep(3)

    print(f"\n新 Instrument 作成: developerJwt(kid={signer_id}, sub={user_id})")
    inst_resp = dp.create_payment_instrument(
        userId=user_id,
        paymentManagerArn=manager_arn,
        paymentConnectorId=connector_id,
        paymentInstrumentType="EMBEDDED_CRYPTO_WALLET",
        paymentInstrumentDetails={
            "embeddedCryptoWallet": {
                "network": "ETHEREUM",
                "linkedAccounts": [
                    {"developerJwt": {"kid": signer_id, "sub": user_id}}
                ],
            }
        },
        clientToken=str(uuid.uuid4()),
    )
    inst = inst_resp["paymentInstrument"]
    instrument_id = inst["paymentInstrumentId"]
    details = inst.get("paymentInstrumentDetails", {}).get("embeddedCryptoWallet", {})
    wallet_address = details.get("walletAddress")
    redirect_url = details.get("redirectUrl")

    print(f"\nInstrumentId   : {instrument_id}")
    print(f"WalletAddress  : {wallet_address}")
    print(f"redirectUrl    : {redirect_url}")
    print(f"Status         : {inst.get('status')}")
    print(json.dumps(inst, indent=2, default=str)[:1500])

    save_state(
        {
            "payment_instrument_id": instrument_id,
            "wallet_address": wallet_address,
            "payment_instrument_redirect_url": redirect_url,
        }
    )


if __name__ == "__main__":
    main()
