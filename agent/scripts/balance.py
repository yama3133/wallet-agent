"""ウォレット残高を確認するヘルパー。base-sepolia の USDC 残高を表示。"""
from __future__ import annotations

import json

import boto3

from _common import print_header, region, require_state


def main() -> None:
    print_header("ウォレット残高確認")

    manager_arn = require_state("payment_manager_arn")
    connector_id = require_state("payment_connector_id")
    instrument_id = require_state("payment_instrument_id")
    user_id = require_state("test_user_id")
    wallet_address = require_state("wallet_address")

    dp = boto3.client(
        "bedrock-agentcore",
        region_name=region(),
        endpoint_url=f"https://bedrock-agentcore.{region()}.amazonaws.com",
    )

    for chain, token in [("BASE_SEPOLIA", "USDC"), ("BASE", "USDC"), ("ETHEREUM", "USDC")]:
        try:
            r = dp.get_payment_instrument_balance(
                userId=user_id,
                paymentManagerArn=manager_arn,
                paymentConnectorId=connector_id,
                paymentInstrumentId=instrument_id,
                chain=chain,
                token=token,
            )
            balance = {k: v for k, v in r.items() if k != "ResponseMetadata"}
            print(f"  {chain}/{token}: {json.dumps(balance, default=str)}")
        except Exception as e:
            print(f"  {chain}/{token}: error - {type(e).__name__}: {str(e)[:120]}")

    print(f"\nbase-sepolia explorer:")
    print(f"  https://sepolia.basescan.org/address/{wallet_address}")
    print(f"  https://sepolia.basescan.org/token/0x036CbD53842c5426634e7929541eC2318f3dCF7e?a={wallet_address}")


if __name__ == "__main__":
    main()
