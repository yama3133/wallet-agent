"""Step 2: PaymentManager と PaymentConnector を作成する。

PaymentManager が READY になるまで待ってから Connector を追加する。
"""
from __future__ import annotations

import time
import uuid

import boto3

from _common import print_header, region, require_state, save_state

MANAGER_NAME = "walletagentpm"
CONNECTOR_NAME = "walletagentconn"


def wait_until_ready(client, manager_id: str, *, timeout_sec: int = 180) -> str:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        st = client.get_payment_manager(paymentManagerId=manager_id)["status"]
        print(f"  status: {st}")
        if st == "READY":
            return st
        if st in ("CREATE_FAILED", "UPDATE_FAILED"):
            raise RuntimeError(f"PaymentManager が {st} になった")
        time.sleep(5)
    raise TimeoutError(f"{timeout_sec}秒以内に READY にならなかった")


def main() -> None:
    print_header("Step 2: PaymentManager と Connector 作成")

    service_role_arn = require_state("service_role_arn")
    credential_provider_arn = require_state("credential_provider_arn")
    vendor = require_state("credential_provider_vendor")
    name_prefix = require_state("payment_manager_name_prefix")

    # 名前は trust policy の SourceArn ArnLike と一致させる
    # name制約: [a-zA-Z][a-zA-Z0-9]{0,47} (ハイフン不可)
    manager_name = f"{name_prefix}{uuid.uuid4().hex[:8]}"

    client = boto3.client("bedrock-agentcore-control", region_name=region())

    print(f"PaymentManager 作成: {manager_name}")
    mgr = client.create_payment_manager(
        name=manager_name,
        authorizerType="AWS_IAM",
        roleArn=service_role_arn,
    )
    manager_id = mgr["paymentManagerId"]
    manager_arn = mgr["paymentManagerArn"]
    print(f"  ID:  {manager_id}")
    print(f"  ARN: {manager_arn}")

    save_state(
        {
            "payment_manager_name": manager_name,
            "payment_manager_id": manager_id,
            "payment_manager_arn": manager_arn,
        }
    )

    print("READY 待ち")
    wait_until_ready(client, manager_id)

    conn_key = "stripePrivy" if vendor == "StripePrivy" else "coinbaseCDP"
    print(f"\nPaymentConnector 作成 ({vendor})")
    conn = client.create_payment_connector(
        paymentManagerId=manager_id,
        name=CONNECTOR_NAME,
        type=vendor,
        credentialProviderConfigurations=[
            {conn_key: {"credentialProviderArn": credential_provider_arn}}
        ],
    )
    connector_id = conn["paymentConnectorId"]
    print(f"  ID: {connector_id}")

    save_state(
        {
            "payment_connector_name": CONNECTOR_NAME,
            "payment_connector_id": connector_id,
        }
    )


if __name__ == "__main__":
    main()
