"""Step 1: AgentCore Identity に PaymentCredentialProvider を登録する。

.env の PAYMENT_PROVIDER に従い、StripePrivy か CoinbaseCDP のクレデンシャルを
Secrets Manager に保存する（AgentCore が裏でやってくれる）。
"""
from __future__ import annotations

import boto3

from _common import env, print_header, region, save_state

PROVIDER_NAME = "wallet-agent-creds"


def main() -> None:
    print_header("Step 1: PaymentCredentialProvider 作成")

    provider = env("PAYMENT_PROVIDER", "StripePrivy")
    print(f"プロバイダ: {provider}")

    client = boto3.client("bedrock-agentcore-control", region_name=region())

    kwargs: dict = {
        "name": PROVIDER_NAME,
        "credentialProviderVendor": provider,
    }

    if provider == "StripePrivy":
        kwargs["providerConfigurationInput"] = {
            "stripePrivyConfiguration": {
                "appId": env("PRIVY_APP_ID"),
                "appSecret": env("PRIVY_APP_SECRET"),
                "authorizationId": env("PRIVY_AUTHORIZATION_ID"),
                "authorizationPrivateKey": env("PRIVY_AUTHORIZATION_PRIVATE_KEY"),
            }
        }
    elif provider == "CoinbaseCDP":
        kwargs["providerConfigurationInput"] = {
            "coinbaseCdpConfiguration": {
                "apiKeyId": env("CDP_API_KEY_ID"),
                "apiKeySecret": env("CDP_API_KEY_SECRET"),
                "walletSecret": env("CDP_WALLET_SECRET"),
            }
        }
    else:
        raise RuntimeError(f"未対応のプロバイダ: {provider}")

    resp = client.create_payment_credential_provider(**kwargs)
    arn = resp["credentialProviderArn"]
    print(f"作成成功: {arn}")

    save_state(
        {
            "credential_provider_name": PROVIDER_NAME,
            "credential_provider_arn": arn,
            "credential_provider_vendor": provider,
        }
    )


if __name__ == "__main__":
    main()
