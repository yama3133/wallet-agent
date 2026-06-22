# wallet-agent — 設計メモ

「AIに財布を渡す日」を実装で見せるアプリ。Phase 1 で AgentCore Payments の正規ユースケース（x402 + 暗号通貨マイクロペイメント）、Phase 2 で Stripe + 楽天市場API による一般EC型の買い物エージェントを乗せる。

承認ゲート（Human-in-the-Loop）が共通の核。

## 1. ゴールと非ゴール

### ゴール
- AIエージェントが**自律的に判断**して、ユーザーに「これを買って良いか / これに支払って良いか」を問う
- ユーザーが承認/拒否すると、エージェントが続きの処理を実行する
- 全取引が **観測可能**（誰が、何に、いくら、いつ）

### 非ゴール（少なくとも当面）
- 実カードでの本番決済（テストモードのみ）
- 商品の物理的な発送・在庫管理（楽天Phase 2でも、楽天市場APIは検索のみ、購入は擬似で良い）
- マルチユーザー認証（最初はシングルユーザー前提でOK）

## 2. 2フェーズの全体像

| | Phase 1 | Phase 2 |
|---|---|---|
| キャッチコピー | 「AIに財布を渡す日」 | 「AIが代わりに買い物してくれる日」 |
| 商品 | 有料API・有料MCPサーバー・有料Webコンテンツ | 楽天市場の実商品（検索） |
| 決済 | AgentCore Payments（x402 + USDC） | Stripe Checkout（テストモード） |
| ウォレット | Coinbase CDP or Stripe Privy のEmbedded Wallet | クレカ（テストカード） |
| 登壇との関係 | re:Invent / Qiita / iOSDC LT / re:Deploy のCFPと完全一致 | エンドユーザー向けデモとして見栄え重視 |
| AgentCore Payments | 正規に使用 | 使わない（承認UIの仕組みだけ流用） |

## 3. アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ Vercel (Next.js 16)                                          │
│  ├─ /chat            ユーザー → エージェントへの依頼          │
│  ├─ /tasks/[id]      タスク詳細・承認カード・進捗            │
│  ├─ /history         取引履歴                                │
│  ├─ API Routes                                                │
│  │   ├─ POST /api/tasks         タスク開始                    │
│  │   ├─ POST /api/approvals     承認/拒否                    │
│  │   ├─ GET  /api/tasks/[id]/stream  SSE で状態 push          │
│  │   └─ POST /api/wallet/topup  Phase1: ウォレット入金導線    │
│  └─ Auth: OIDC Federation → IAM Role（既存パターン）          │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ HTTPS (AssumeRole)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentCore Runtime (us-east-1)                                │
│  ├─ Strands Agent (Claude Sonnet 4.6)                        │
│  │   ├─ Tools:                                                │
│  │   │   - search_resource    Phase1=有料API一覧 / Phase2=楽天検索 │
│  │   │   - request_approval   DynamoDBに承認待ちを書く          │
│  │   │   - check_approval     ポーリングで承認状態を確認        │
│  │   │   - execute_payment    Phase1=process_payment / Phase2=Stripe │
│  │   └─ AgentCorePaymentsPlugin (auto_payment=False)          │
│  └─ 状態は DynamoDB に永続化                                  │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ DynamoDB                                                     │
│  ├─ wallet_agent_tasks       task_id, status, payload         │
│  ├─ wallet_agent_approvals   approval_id, task_id, decision  │
│  └─ wallet_agent_txns        txn_id, task_id, amount, proof   │
└─────────────────────────────────────────────────────────────┘
               │
               ▼ Phase 1
┌─────────────────────────────────────────────────────────────┐
│ AgentCore Payments (us-east-1)                               │
│  ├─ PaymentManager                                            │
│  ├─ PaymentConnector (StripePrivy または CoinbaseCDP)        │
│  ├─ PaymentInstrument (ユーザーのEmbedded Wallet)             │
│  ├─ PaymentSession (TTL + maxSpendAmount)                     │
│  └─ ProcessPayment (x402 v2)                                  │
└─────────────────────────────────────────────────────────────┘

               ▼ Phase 2
┌─────────────────────────────────────────────────────────────┐
│ 楽天市場API + Stripe Checkout (test)                          │
│  ├─ Rakuten IchibaItem/Search/20260401                       │
│  └─ Stripe Checkout Session（動的に作成）                     │
└─────────────────────────────────────────────────────────────┘
```

## 4. データフロー（Phase 1 のハッピーパス）

1. ユーザーが `/chat` で「**今日のNVDAの市況サマリをまとめて。プレミアムなデータが必要なら買って良いよ（上限 $1.00）**」と入力
2. Vercel `POST /api/tasks` → DynamoDB に task 作成（status: `PLANNING`）
3. Vercel が AgentCore Runtime を invoke（task_id, prompt, payment_session_id を渡す）
4. エージェントが Claude Sonnet 4.6 で思考 → `search_resource` ツールで x402 対応の市況API候補を出す
5. エージェントが `request_approval` ツールを呼ぶ → DynamoDB に approval 待ちを書く（amount, resource, justification）→ task status: `WAITING_APPROVAL`
6. Vercel `/tasks/[id]` が SSE で `WAITING_APPROVAL` を検知 → 承認カードUIを表示
7. ユーザーが「承認」→ `POST /api/approvals` → DynamoDB の approval に `APPROVED` を書く
8. エージェントが `check_approval` で `APPROVED` を確認 → `execute_payment` で実 API を叩く（402 → `process_payment` 経由で x402 ヘッダ生成 → リトライ）→ 結果取得
9. エージェントが結果を要約 → DynamoDB の task に `COMPLETED` と最終応答を書く
10. Vercel UI に最終応答が流れる

**重要**: AgentCore Payments プラグインは `auto_payment=False` で動かす。402を見ても自動決済しない。承認待ちを挟んでから `process_payment` を呼ぶ。

## 5. 主要な実装上の決定

### 5.1 リージョン
- AgentCore Payments / Runtime: **us-east-1**
- DynamoDB: us-east-1（同居）
- Vercel: グローバル（OIDC Federation で us-east-1 の IAM Role を Assume）

### 5.2 Payment Provider
- **デフォルト: StripePrivy**
  - 理由: Stripeブランドが日本の聴衆に分かりやすい / Privyのドキュメントが整っている
  - 切り替えコスト低：CredentialProvider と Connector を作り直すだけ
- 代替: CoinbaseCDP（暗号色を強く出したい場合）

### 5.3 ブロックチェーンネットワーク
- テスト: `base-sepolia`（Base L2 のテストネット）
- 本番: `base`（低手数料・Coinbase運営）
- ネットワークプリファレンス: `["eip155:8453", "base-sepolia"]`

### 5.4 エージェントモデル
- **Claude Sonnet 4.6**（memory 確認済み、acct 761018866498/us-east-1 で利用可）
- 思考が重いタスクで Opus 4.5 にスイッチも可

### 5.5 承認の粒度
- 承認カードは **1取引につき1枚**
- バッチ承認は Phase 3 以降（やらない可能性）
- 承認内容に含めるもの: 金額、宛先（リソース）、エージェントの理由付け、有効期限（90秒）

### 5.6 セッション設計
- PaymentSession の `maxSpendAmount`: ユーザーが `/chat` で指定した上限（デフォルト $1.00）
- `expiryTimeInMinutes`: 60
- 1チャットセッション = 1 PaymentSession

## 6. リポ構成（予定）

```
wallet-agent/
├── README.md
├── DESIGN.md                    # このファイル
├── .gitignore
├── apps/
│   └── web/                     # Vercel (Next.js 16, App Router)
│       ├── app/
│       │   ├── chat/
│       │   ├── tasks/[id]/
│       │   ├── history/
│       │   └── api/
│       ├── components/
│       │   └── ApprovalCard.tsx
│       ├── lib/
│       │   ├── dynamodb.ts      # AssumeRole + DynamoDB クライアント
│       │   ├── agentcore.ts     # Runtime invoke
│       │   └── sse.ts
│       └── package.json
├── agent/                       # AgentCore Runtime（Pythonエージェント）
│   ├── agent.py                 # Strands Agent + Payments Plugin
│   ├── tools/
│   │   ├── search.py            # 有料API一覧 / 楽天検索
│   │   ├── approval.py          # 承認ゲートツール
│   │   └── payment.py           # x402 実行
│   ├── pyproject.toml
│   └── Dockerfile               # AgentCore Runtime デプロイ用
├── infra/
│   ├── dynamodb.yaml            # CloudFormation / SAM
│   ├── iam.yaml                 # IAM ロール
│   └── agentcore-setup.sh       # AgentCore CLI でのセットアップ
└── docs/
    ├── architecture.png
    └── demo-script.md           # 登壇用デモ台本
```

## 7. Phase 別の実装計画

### Phase 1（AgentCore Payments 正規）
1. **PoC**: ローカルで `boto3` から `create_payment_manager` → `create_payment_session` → `process_payment` まで疎通（最小）
2. **エージェント単体**: Strands Agent + AgentCorePaymentsPlugin（auto_payment=False）で承認待ちが入る形を確認
3. **DynamoDB**: 状態保存テーブル3本作成
4. **AgentCore Runtime デプロイ**: `agentcore deploy`
5. **Vercel フロント**: 承認カードUI、SSE、`/chat`
6. **疎通**: ユーザーがブラウザから依頼 → 承認 → 決済成功 → 結果表示
7. **デモ整備**: 「市況データAPI」のモックx402サーバーを用意（自作 or Coinbase Bazaar）

### Phase 2（Stripe + 楽天）
1. 楽天市場API アプリID取得 → 商品検索ツール（`/api/search-rakuten`）
2. Stripe テストモードAPIキー → Checkout Session 作成のラッパー
3. エージェントのツールに `search_rakuten` と `create_stripe_checkout` を追加
4. 承認カードに楽天商品の画像・価格を表示
5. 承認後、Stripe Checkout URL を返してユーザーがテストカードで決済（or Stripe API で直接 PaymentIntent を confirm）

## 8. 確認事項・未解決

- [ ] StripePrivy か CoinbaseCDP、どちらでPoCを進めるか（**デフォルト: StripePrivy**）
- [ ] x402 対応の本物のテストAPI先（Coinbase Bazaar に何があるか要調査）
- [ ] AgentCore Runtime のローカル開発体験（`agentcore invoke --local` 的なものがあるか確認）
- [ ] Vercel OIDC Federation の Runtime invoke 権限スコープ（最小）
- [ ] デモ台本（30秒バージョン / 5分バージョン）
- [ ] ウォレット入金UXを登壇でどう見せるか（事前入金 vs ライブ入金）

## 9. リスクとフォールバック

| リスク | フォールバック |
|---|---|
| AgentCore Payments の preview が登壇日までに大きな破壊的変更 | デモ動画事前録画 |
| Embedded Wallet 入金が登壇環境（ホテルWi-Fi等）で失敗 | 事前入金 + 残高スクショ |
| x402対応の良いテストAPIが見つからない | 自前で x402 v2 対応モックサーバーをデプロイ（Vercel 1関数で書ける） |
| AgentCore Runtime のコールドスタートが遅すぎる | Vercel API Routes に Strands Agent を直接埋め込む形に退避（タイムアウトを気にしながら） |

## 10. 関連メモ（memory 参照）

- `project_reinvent_com_cfp` — re:Invent COM Track CFP（本命③）
- `project-qiita-tech-festa-day-2026-cfp` — Qiita Tech Festa（同じ「AIに財布を渡す日」軸）
- `project_aegis_slackhack` — Aegis（人間承認コントロールプレーン、同じ軸の別実装）
- `project_redeploy_2026` — re:Deploy 2026 Security 登壇
- `project-iosdc-japan-2026-cfp` — iOSDC LT5「AIに財布を渡す日」

このアプリが完成すると、上記5つの登壇/CFPで**同じ実装を使い回せる**。
