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
| 4. ProcessPayment（x402で1000μUSDC支払い） | ✗ Privyのsigner不整合で AccessDeniedException |

**詰まりポイント**: AWSの`CreatePaymentInstrument`が作ったPrivy wallet は内部生成Userがowner、私のAuthorization Key (`icv02b63ulgusmb11hxhahey`) はそのwalletの signer に紐付いていない。Privyダッシュボードでも `Signer for: 空` と確認。

**次の方針**: Strands Agent本体の実装に進む。決済部分はモック・try/exceptで囲い、x402署名は後で詰める。

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

## なぜ作るか

memory 上の以下の登壇/CFPで「AIに財布を渡す日」という同じ軸を使う。共通の実装ベースとして必要。

- re:Invent 2026 COM Track（本命③）
- Qiita Tech Festa Day 2026
- iOSDC Japan 2026 LT5
- re:Deploy 2026 Security
- Aegis（Slack Agent Builder Challenge）

## 構成

```
wallet-agent/
├── DESIGN.md      設計メモ
├── apps/web/      Vercel フロント（Next.js 16）
├── agent/         AgentCore Runtime（Strands Agent）
└── infra/         DynamoDB / IAM
```

## 開発予定

- [x] Phase 1: AgentCore Payments PoC スクリプト作成
- [x] Phase 1: PoC を実機で疎通（Privyアカウント取得・base-sepolia 20 USDC受領まで）
- [x] Phase 1: Strands Agent + 承認ゲート（骨格）
- [ ] Phase 1: ProcessPayment の Privy signer 問題を解決
- [ ] Phase 1: DynamoDB + AgentCore Runtime デプロイ
- [ ] Phase 1: Vercel フロント（承認カード + SSE）
- [ ] Phase 1: 登壇デモ整備
- [ ] Phase 2: 楽天 + Stripe

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
