import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from "@aws-sdk/client-bedrock-agentcore";
import { fromWebToken, fromNodeProviderChain, fromEnv } from "@aws-sdk/credential-providers";

const REGION = process.env.AWS_REGION ?? "us-east-1";
const AGENT_RUNTIME_ARN = process.env.WALLET_AGENT_RUNTIME_ARN ?? "";

let _client: BedrockAgentCoreClient | null = null;

function client(): BedrockAgentCoreClient {
  if (_client) return _client;

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
  } else if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
    credentials = fromEnv();
  } else {
    credentials = fromNodeProviderChain();
  }

  _client = new BedrockAgentCoreClient({ region: REGION, credentials });
  return _client;
}

export interface InvokeResult {
  status: "OK" | "ERROR";
  response?: string;
  error?: string;
}

export async function invokeAgent(prompt: string, sessionId?: string): Promise<InvokeResult> {
  if (!AGENT_RUNTIME_ARN) {
    return { status: "ERROR", error: "WALLET_AGENT_RUNTIME_ARN 未設定" };
  }
  const body = new TextEncoder().encode(JSON.stringify({ prompt }));
  // AgentCore Runtime InvokeAgentRuntime: runtimeSessionId は 33 chars 以上、 user/session の identifier
  const runtimeSessionId = sessionId ?? `web-${crypto.randomUUID()}-${Date.now()}`;
  try {
    const cmd = new InvokeAgentRuntimeCommand({
      agentRuntimeArn: AGENT_RUNTIME_ARN,
      runtimeSessionId,
      payload: body,
      contentType: "application/json",
      accept: "application/json",
    });
    const resp = await client().send(cmd);
    if (!resp.response) return { status: "ERROR", error: "empty response" };
    // streaming Uint8Array → concat
    const chunks: Uint8Array[] = [];
    // ReadableStream の場合
    const reader = (resp.response as unknown as { getReader?: () => unknown });
    if (typeof (reader as { getReader?: unknown }).getReader === "function") {
      const r = (resp.response as unknown as ReadableStream<Uint8Array>).getReader();
      while (true) {
        const { done, value } = await r.read();
        if (done) break;
        if (value) chunks.push(value);
      }
    } else {
      // Buffer or Uint8Array
      chunks.push(resp.response as unknown as Uint8Array);
    }
    const totalLen = chunks.reduce((s, c) => s + c.byteLength, 0);
    const merged = new Uint8Array(totalLen);
    let off = 0;
    for (const c of chunks) {
      merged.set(c, off);
      off += c.byteLength;
    }
    const text = new TextDecoder().decode(merged);
    // payload は {"response":"..."} 形式（agent.py の entrypoint return 値）
    try {
      const j = JSON.parse(text);
      return { status: "OK", response: j.response ?? text };
    } catch {
      return { status: "OK", response: text };
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { status: "ERROR", error: msg };
  }
}
