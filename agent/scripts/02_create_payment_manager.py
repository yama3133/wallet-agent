"""Step 2: PaymentManager と PaymentConnector を作成する。

PaymentManager が READY になるまで待ってから Connector を追加する。
"""
from __future__ import annotations

import time
import uuid

import boto3

from _common import print_header, region, require_state, save_state

MANAGER_NAME = "wallet-agent-pm"
CONNECTOR_NAME = "wallet-agent-connector"


def wait_until_ready(client, arn: str, *, timeout_sec: int = 180) -> str:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        st = client.get_payment_manager(paymentManagerArn=arn)["status"]
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
    manager_name = f"{name_prefix}-{uuid.uuid4().hex[:8]}"

    client = boto3.client("bedrock-agentcore-control", region_name=region())

    print(f"PaymentManager 作成: {manager_name}")
    mgr = client.create_payment_manager(
        name=manager_name,
        authorizerType="AWS_IAM",
        roleArn=service_role_arn,
    )
    manager_arn = mgr["paymentManagerArn"]
    print(f"  ARN: {manager_arn}")

    print("READY 待ち")
    wait_until_ready(client, manager_arn)

    print(f"\nPaymentConnector 作成 ({vendor})")
    conn = client.create_payment_connector(
        paymentManagerArn=manager_arn,
        name=CONNECTOR_NAME,
        paymentConnectorType=vendor,
        credentialProviderArn=credential_provider_arn,
    )
    connector_id = conn["paymentConnectorId"]
    print(f"  ID: {connector_id}")

    save_state(
        {
            "payment_manager_name": manager_name,
            "payment_manager_arn": manager_arn,
            "payment_connector_name": CONNECTOR_NAME,
            "payment_connector_id": connector_id,
        }
    )


if __name__ == "__main__":
    main()
