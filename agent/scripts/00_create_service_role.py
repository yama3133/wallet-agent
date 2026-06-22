"""Step 0: AgentCore Payments の ResourceRetrievalRole を作成する。

このロールは bedrock-agentcore.amazonaws.com が AssumeRole してクレデンシャル取得する
ためのサービスロール。PaymentManager 作成時に必要。

ベース権限は CreatePaymentManager 時に AWS 側が自動で追加する。
ここでは Trust policy だけ仕込む。
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError

from _common import print_header, region, save_state

ROLE_NAME = "AgentCorePaymentsResourceRetrievalRole"
PAYMENT_MANAGER_NAME_PREFIX = "wallet-agent-pm"


def trust_policy(account_id: str, aws_region: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{aws_region}:{account_id}"
                            f":payment-manager/{PAYMENT_MANAGER_NAME_PREFIX}-*"
                        )
                    },
                },
            }
        ],
    }


def main() -> None:
    print_header("Step 0: ResourceRetrievalRole 作成")

    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    account_id = identity["Account"]
    aws_region = region()
    print(f"アカウント: {account_id}, リージョン: {aws_region}")

    iam = boto3.client("iam")
    policy_doc = trust_policy(account_id, aws_region)

    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(policy_doc),
            Description=(
                "Service role for AgentCore Payments to retrieve credentials. "
                "Created by wallet-agent PoC."
            ),
        )
        role_arn = resp["Role"]["Arn"]
        print(f"作成成功: {role_arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print("既に存在。Trust policy を更新する")
        iam.update_assume_role_policy(
            RoleName=ROLE_NAME, PolicyDocument=json.dumps(policy_doc)
        )
        role_arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        print(f"更新済み: {role_arn}")

    save_state(
        {
            "account_id": account_id,
            "aws_region": aws_region,
            "service_role_name": ROLE_NAME,
            "service_role_arn": role_arn,
            "payment_manager_name_prefix": PAYMENT_MANAGER_NAME_PREFIX,
        }
    )
    print("state.json に保存した")


if __name__ == "__main__":
    main()
