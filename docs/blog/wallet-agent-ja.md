---
title: "AIに財布を渡す日 — Sonnet 4.6 × AgentCore Payments × 楽天 × Stripe で承認付き買い物エージェントを作った"
published: false
description: "Bedrock AgentCore Payments の x402 マイクロペイメントと、楽天市場 + Stripe のテスト決済を、Human-in-the-Loop の承認ゲート越しに 1 つの Strands Agent で動かした PoC。Vercel 本番デプロイ + 8 言語 UI まで。"
tags: bedrock, agentcore, nextjs, ai
cover_image: https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/blog/wallet-agent-thumb-ja.png
canonical_url: https://github.com/yama3133/wallet-agent
---

> **TL;DR**
> 「AIに財布を渡す日」をネタに **Bedrock AgentCore Payments (x402 + USDC)** と **楽天市場 + Stripe Checkout** を 1 つの Strands Agent から動かして、 **人間の承認カードを挟まないと 1 円も動かせない** PoC を作った。本番デプロイ + 8 言語 UI まで通している。
>
> - 本番: https://wallet-agent.vercel.app/
> - リポ: https://github.com/yama3133/wallet-agent

![wallet-agent thumbnail](https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/blog/wallet-agent-thumb-ja.png)

## なぜ作ったか

re:Invent 2026 COM Track / Qiita Tech Festa / iOSDC LT / re:Deploy Security / Slack Hackathon — **「AIエージェントに財布を渡す日 / 承認ゲート」** という同じ軸の CFP / 登壇が 5 本走っている。スライドだけで通すのは限界があるので、 **共通の実装ベース** を 1 つ持っておきたかった。

ゴールはシンプル。

> ユーザーが自然文で依頼 → エージェントが選定 → **承認カードが立つ** → 人間が承認 / 拒否 → 承認されたら実決済 → 結果を要約して返す

それを「有料 API へのマイクロ課金」と「実商品の購入」の 2 軸でやる。

## アーキテクチャ

![architecture](https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/images/wallet-agent-architecture-ja.png)

- **フロント**: Next.js 16 on Vercel（承認カード一覧 + chat + checkout 結果）
- **状態**: DynamoDB 3 テーブル (tasks / approvals / txns) + Streams + PITR
- **エージェント**: AgentCore Runtime (ARM64 container) + Strands Agent + Claude Sonnet 4.6
- **決済 Phase 1**: AgentCore Payments → Privy (StripePrivy) → x402 → base-sepolia USDC
- **決済 Phase 2**: 楽天市場 IchibaItem/Search → Stripe Checkout (test mode)
- **多言語**: ja / en / zh / ko / fr / it / es / **ar(RTL)** の 8 言語、`localStorage` + `navigator.language` 自動検出、フォントは **LINE Seed JP Bold**

すべてのコードと CloudFormation テンプレ、デモ台本まで [yama3133/wallet-agent](https://github.com/yama3133/wallet-agent) に置いてある。

## エージェントの中身

エージェントは Strands Agents で組んだ、ただの `@tool` 関数 6 個。

```python
@tool
def search_paid_resources(query: str = "") -> list[dict]: ...  # x402 カタログ

@tool
def request_payment_approval(resource_id: str, amount_usd: str, justification: str) -> dict:
    """承認カードを DynamoDB / ローカル JSON に書き、決断を待つ"""

@tool
def execute_x402_payment(resource_id: str, payment_session_id: str | None = None) -> dict:
    """AgentCore Payments の generate_payment_header で x402 を完走させる"""

@tool
def search_rakuten_items(keyword: str, max_jpy: int | None = None, hits: int = 5) -> list[dict]: ...

@tool
def request_purchase_approval(item_id: str, title: str, amount_jpy: int, justification: str) -> dict: ...

@tool
def execute_stripe_checkout(item_id: str, title: str, amount_jpy: int, image_url: str = "") -> dict:
    """Stripe Checkout Session を作って URL を返す"""
```

ポイントは `request_*_approval` で **DynamoDB に承認待ち行を書いて Block する** こと。承認が来るまでツールチェーンが進まないので、 LLM が暴走しない。

## Phase 1: AgentCore Payments の signer 問題

最初に詰まったのがここ。

```
ProcessPayment → AccessDeniedException
"Privy credentials are invalid. Please verify the credential configuration."
```

`PaymentManager` / `PaymentConnector` / `PaymentInstrument` (Embedded Crypto Wallet) は全部 boto3 から作れたが、 ProcessPayment だけが通らない。

Privy ダッシュボードを見てみると、 AWS の `CreatePaymentInstrument` が作った wallet は **「内部生成 User」が owner** になっていて、 私が発行した Authorization Key は **どの wallet の signer でもない** 状態だった。

解決策は、Privy が公開している **公式テンプレート [privy-io/aws-agentcore-sdk](https://github.com/privy-io/aws-agentcore-sdk)** をローカルで動かして、 ブラウザでログインして **「Connect agent」UI** を踏むこと。これで Privy 内部 API が `additional_signers` に Authorization Key を登録してくれる。

```bash
git clone https://github.com/privy-io/aws-agentcore-sdk ~/wallet-agent-privy-template
cd ~/wallet-agent-privy-template
# .env.local に NEXT_PUBLIC_PRIVY_APP_ID / PRIVY_APP_SECRET / NEXT_PUBLIC_PRIVY_SIGNER_ID を入れる
pnpm dev
# → ブラウザで localhost:3001 → ログイン → Connect agent
```

ここまで終わると、 同じ Python から `process_payment` が **`PROOF_GENERATED`** で返ってきて、 マーチャント (`https://drvd12nxpcyd5.cloudfront.net/market-recap` という x402 デモエンドポイント) が受理してくれる。

```
[bedrock_agentcore.payments.manager] Successfully processed payment for user test-user-yama3133
[bedrock_agentcore.payments.manager] Successfully generated payment header for user test-user-yama3133
```

学び：**「サーバーサイドだけで AgentCore Payments を完結させようとすると詰む」**。 Privy のフロントエンドUX をデモ動線に組み込む前提で設計するのが正解。

## Phase 2: 楽天市場 API の Referer ハマり

Phase 2 はもっとプリミティブな WebAPI のハマり方だった。

楽天 webservice で新しく作ったアプリの `Application ID` (UUID形式) を `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401` に投げると、

```json
{"errors":{"errorCode":403,"errorMessage":"REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING"}}
```

しかも `Referer: https://wallet-agent.vercel.app/` を付けても落ちる。原因は **User-Agent の bot 判定**。 `User-Agent: wallet-agent/0.1` だと弾かれて、 ブラウザ風の `Mozilla/5.0 ...` に変えたら通った。

最終的に `tools/rakuten.py` はこうなった：

```python
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": referer,             # WALLET_AGENT_PUBLIC_URL
    "Origin": referer.rstrip("/"),
}
if access_key:
    headers["accessKey"] = access_key
    params["accessKey"] = access_key
```

これで黒い靴下 ¥1,980 を取って、 Stripe Checkout Session を生成して、 `4242 4242 4242 4242` で決済すると `https://wallet-agent.vercel.app/checkout/success?session_id=cs_test_...` に飛んで **「決済完了 / Paid」** が出る。

## DynamoDB と Vercel フロント

承認状態は **DynamoDB の `wallet_agent_approvals`** に書く（ローカル開発時は `agent/.approvals.json` にフォールバック、 環境変数 `WALLET_AGENT_STORAGE=local|dynamo` で切替）。

Vercel の Next.js 16 App Router 側はこんな感じで GET / POST を生やしている。

```typescript
// /api/approvals (GET) — status=PENDING を一覧
const r = await ddb().send(new ScanCommand({
  TableName: TABLES.approvals,
  FilterExpression: "#s = :p",
  ExpressionAttributeNames: { "#s": "status" },
  ExpressionAttributeValues: { ":p": "PENDING" },
}));

// /api/approvals/[id] (POST) — 承認 / 拒否
await ddb().send(new UpdateCommand({
  TableName: TABLES.approvals,
  Key: { approval_id: id },
  UpdateExpression: "SET #s = :d, decision = :d, #r = :r, decided_at = :t",
  ExpressionAttributeNames: { "#s": "status", "#r": "reason" },
  ExpressionAttributeValues: { ":d": body.decision, ":r": body.reason ?? "", ":t": String(Date.now()/1000), ":pending": "PENDING" },
  ConditionExpression: "attribute_exists(approval_id) AND #s = :pending",
}));
```

ハマったのは DynamoDB の **`error` が予約語** で `ExpressionAttributeNames` で `#e` にエスケープしないと `ValidationException: Invalid UpdateExpression` で落ちるところ。実装中に 1 回踏んだ。

## 8 言語 UI と LINE Seed JP

`apps/web/src/lib/i18n.ts` に 8 言語 ×31 キーの辞書を持って、 `useI18n()` で current locale と `t.*` を取り回す素朴な作り。 アラビア語のときだけ `document.documentElement.dir = "rtl"` を入れ替える。

```tsx
useEffect(() => {
  document.documentElement.lang = locale;
  document.documentElement.dir = getDir(locale); // "ltr" | "rtl"
}, [locale]);
```

フォントは Next.js 16 の `next/font/google` から **LINE Seed JP Bold** をそのまま読んで、 CSS変数 `--font-line-seed` を Tailwind の `font-sans` に流し込む。日本語のときに丸ゴ系の太字基調になって、 アジア圏で「LINE っぽくて読みやすい」と評判の良いフォント。

## 学んだこと

1. **Privy signer の壁はサーバーサイドだけでは超えられない**。フロントエンドの「Connect agent」操作を必ず動線に組み込む。
2. **`agentcore configure` は対話入力前提**。`-ni`（non-interactive）+ ECR repo 手動作成 + Dockerfile 同梱で CI/automation でも通せる。
3. **Vercel Hobby plan の 60 秒 timeout** はエージェント往復の同期 invoke と非常に相性が悪い。`waitUntil` か polling の二段構えにするのが現実的。
4. **「人間承認カード」ツールを 1 個挟むだけ** で、 LLM の暴走リスクと「いつでも止められる」UX が両立できる。これは Phase 1 / Phase 2 のどちらでも同じパターンで効いた。

## リンク

- 🐙 GitHub: [yama3133/wallet-agent](https://github.com/yama3133/wallet-agent)
- 🚀 本番: https://wallet-agent.vercel.app/
- 📐 アーキ図 (PNG): [docs/images/wallet-agent-architecture-ja.png](https://github.com/yama3133/wallet-agent/blob/main/docs/images/wallet-agent-architecture-ja.png)
- 🎬 デモ台本: [docs/demo-script.md](https://github.com/yama3133/wallet-agent/blob/main/docs/demo-script.md)

「同じ実装で 5 本の登壇に持っていく」用 PoC として、 動かしながら改造していく予定です。フィードバック歓迎。

— [@yama3133](https://github.com/yama3133) (AWS Community Builder, AI Engineering / 2026)
