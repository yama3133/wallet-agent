# wallet-agent

「AIに財布を渡す日」を実装で見せるアプリ。AIエージェントが自律的に判断 → ユーザーが承認 → 実決済、というフローを Human-in-the-Loop で構築する。

## ステータス

設計中（DESIGN.md 参照）。コードはまだ書いていない。

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

1. Phase 1: AgentCore Payments PoC（boto3 で疎通）
2. Phase 1: Strands Agent + 承認ゲート
3. Phase 1: DynamoDB + AgentCore Runtime デプロイ
4. Phase 1: Vercel フロント（承認カード + SSE）
5. Phase 1: 登壇デモ整備
6. Phase 2: 楽天 + Stripe
