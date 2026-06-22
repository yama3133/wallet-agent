"""Step 0: AgentCore Payments の ResourceRetrievalRole を作成する。

このロールは bedrock-agentcore.amazonaws.com が AssumeRole してクレデンシャル取得する
ためのサービスロール。PaymentManager 作成時に必要。

Trust policy と base permission policy を仕込む。Connector 追加時の per-connector
permission も AWS 側が自動で付与する設計のはずだが、PoC では確実に動かすため
最低限の inline policy を手動で attach する。
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError

from _common import print_header, region, save_state

ROLE_NAME = "AgentCorePaymentsResourceRetrievalRole"
PAYMENT_MANAGER_NAME_PREFIX = "walletagentpm"
INLINE_POLICY_NAME = "WalletAgentPaymentsBase"


def base_permission_policy(account_id: str, aws_region: str) -> dict:
    # PoC では最低限の絞り込みで bedrock-agentcore 系を全許可、Secrets Manager は account 内に限定。
    # 本番では payments-iam-roles docs の最小権限版に差し替える。
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockAgentCoreAll",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:*"],
                "Resource": "*",
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [f"arn:aws:secretsmanager:{aws_region}:{account_id}:secret:*"],
                "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}},
            },
        ],
    }


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
                            f":payment-manager/{PAYMENT_MANAGER_NAME_PREFIX}*"
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

    perm_doc = base_permission_policy(account_id, aws_region)
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=INLINE_POLICY_NAME,
        PolicyDocument=json.dumps(perm_doc),
    )
    print(f"インラインポリシー {INLINE_POLICY_NAME} を attach")

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
