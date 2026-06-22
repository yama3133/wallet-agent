import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { fromWebToken, fromNodeProviderChain } from "@aws-sdk/credential-providers";

const REGION = process.env.AWS_REGION ?? "us-east-1";

export const TABLES = {
  tasks: process.env.WALLET_AGENT_TASKS_TABLE ?? "wallet_agent_tasks",
  approvals: process.env.WALLET_AGENT_APPROVALS_TABLE ?? "wallet_agent_approvals",
  txns: process.env.WALLET_AGENT_TXNS_TABLE ?? "wallet_agent_txns",
};

let _ddb: DynamoDBDocumentClient | null = null;

export function ddb(): DynamoDBDocumentClient {
  if (_ddb) return _ddb;

  // Vercel deploy 後は OIDC Federation を想定: AWS_ROLE_ARN を環境変数で渡す。
  // ローカル開発時は ~/.aws/credentials (aws login) を使う。
  const roleArn = process.env.AWS_ROLE_ARN;
  const oidcToken = process.env.AWS_WEB_IDENTITY_TOKEN ?? process.env.VERCEL_OIDC_TOKEN;

  let credentials;
  if (roleArn && oidcToken) {
    credentials = fromWebToken({
      roleArn,
      webIdentityToken: oidcToken,
      roleSessionName: "wallet-agent-web",
      durationSeconds: 3600,
    });
  } else {
    credentials = fromNodeProviderChain();
  }

  const raw = new DynamoDBClient({ region: REGION, credentials });
  _ddb = DynamoDBDocumentClient.from(raw, {
    marshallOptions: { removeUndefinedValues: true },
  });
  return _ddb;
}
