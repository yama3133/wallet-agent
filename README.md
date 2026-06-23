# wallet-agent

「AIに財布を渡す日」を実装で見せるアプリ。AIエージェントが自律的に判断 → ユーザーが承認 → 実決済、というフローを Human-in-the-Loop で構築する。

## ステータス

Phase 1 PoC、ProcessPayment直前まで疎通（2026-06-23）。

| Step | 状況 |
|---|---|
| 0. ServiceRole（trust + inline policy） | ✓ |
| 1. PaymentCredentialProvider（StripePrivy） | ✓ |
| 2. PaymentManager + Connector（READY） | ✓ |
| 3. PaymentInstrument（Embedded Wallet ACTIVE、20 USDC入金確認） | ✓ |
| 4. ProcessPayment（x402で1000μUSDC支払い） | ✅ 署名フル通過、最後はbase-sepoliaのgas(ETH)不足のみ |

**解決経緯**: 当初は Privyのwallet signer が紐付かず AccessDeniedException。privy-io/aws-agentcore-sdk テンプレを `~/wallet-agent-privy-template` にclone → `pnpm dev` → ブラウザでログイン → 「Connect agent」UI で Authorization Key を wallet の additional signer として登録 → AgentCore の generate_payment_header が `PAYMENT-SIGNATURE` を生成 → マーチャント (drvd12nxpcyd5.cloudfront.net) が受理 → transaction simulation 段階まで進行（`invalid_exact_evm_transaction_simulation_failed`）。base-sepolia の ETH faucet で gas を補えば完走の見込み。

**Phase 1 PoC 実証完了範囲**: AgentCore Payments を介した x402 マイクロペイメントの**署名・提示まで全パス通過**。残るは blockchain上の gas のみ。

- 設計: [DESIGN.md](./DESIGN.md)
- 外部クレデンシャル取得手順: [agent/CREDENTIALS.md](./agent/CREDENTIALS.md)
- PoCスクリプト: [agent/scripts/](./agent/scripts/)

## アーキテクチャ（要約）

- **フロント**: Next.js 16 on Vercel（承認カードUI / SSE で状態購読）
- **エージェント**: AgentCore Runtime + Strands Agent + Claude Sonnet 4.6
- **決済**:
  - Phase 1: AgentCore Payments（x402 + USDC + Stripe Privy or Coinbase）
  - Phase 2: Stripe Checkout（テストモード）+ 楽天市場API
- **状態**: DynamoDB

詳細は [DESIGN.md](./DESIGN.md) を参照。

## 構成

```
wallet-agent/
├── DESIGN.md      設計メモ
├── apps/web/      Vercel フロント（Next.js 16）
├── agent/         AgentCore Runtime（Strands Agent）
└── infra/         DynamoDB / IAM
```

## PoCの動かし方

```bash
# 1. クレデンシャル取得（Privy or Coinbase）→ agent/CREDENTIALS.md 参照
# 2. AWS にログイン
aws login

# 3. venv とパッケージ
cd agent
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. .env を埋める
cp .env.example .env
# エディタで Privy/Coinbase の認証情報を貼る

# 5. スクリプトを順番に
cd scripts
python 00_create_service_role.py
python 01_create_credential_provider.py
python 02_create_payment_manager.py
python 03_create_instrument.py   # redirect URL でウォレット入金
python 04_run_payment.py
```

各ステップの作成物 ARN/ID は `agent/state.json` に追記される。

## Strands Agent CLI

```bash
cd agent
source .venv/bin/activate

# 対話モード
python agent.py
> 市況サマリが欲しい、上限 0.005 ドルで

# 別ターミナルで承認待ち一覧
python agent.py pending

# 承認 / 拒否
python agent.py approve <approval_id>
python agent.py reject  <approval_id>
```

承認状態は `agent/.approvals.json` に保存（gitignore済）。

## ウォレット残高確認

```bash
cd agent/scripts
../.venv/bin/python balance.py
```
