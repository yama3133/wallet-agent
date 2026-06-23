# 次のステップ手順

「上から順にやって」分のうち、ユーザー操作が必要な残りの手順をまとめる。

## 3. Phase 2 実機テスト（楽天 + Stripe）

### a. 楽天 application ID を発行

1. https://webservice.rakuten.co.jp/ で楽天会員ログイン
2. 「アプリ情報の登録」→ 新規アプリ作成
   - アプリ名: `wallet-agent`
   - アプリURL: `https://wallet-agent.vercel.app/`
3. 発行された **アプリID** を控える

`agent/.env` に追加:

```env
RAKUTEN_APPLICATION_ID=<取得した値>
```

### b. Stripe テストキーを発行

1. https://dashboard.stripe.com/test/apikeys
2. 「Secret key (test mode)」を Reveal → コピー (`sk_test_...`)

`agent/.env` に追加:

```env
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
```

### c. 楽天プロンプトでローカル実行

```bash
cd ~/wallet-agent/agent
source .venv/bin/activate

WALLET_AGENT_AUTO_APPROVE=1 \
  python agent.py run "黒い靴下を3000円以内で楽天で探して、よさそうなら買って"
```

期待される挙動:
1. `search_rakuten_items("靴下", max_jpy=3000, hits=5)` で候補
2. `request_purchase_approval(...)` で承認カード（auto-approve でAPPROVED）
3. `execute_stripe_checkout(...)` で Stripe Checkout URL 返却
4. URL を表示

Vercel本番でもテストするなら、AgentCore Runtime にこれらの環境変数を渡すには `agentcore configure` を再実行するか、Lambda版に切替が必要（PoCではローカル CLI で十分）。

## 4. 既に完了した tasks API + chat UI

- 本番: https://wallet-agent.vercel.app/chat
- 機能: textarea で prompt → POST /api/tasks → AgentCore Runtime invoke → 結果表示
- 注意: Vercel Hobby は最大60秒 timeout。承認カード往復 + 決済を1リクエストで完結させると間に合わない可能性
  - 対策: `WALLET_AGENT_AUTO_APPROVE=1` を AgentCore Runtime に設定するか、UI 側 で polling + 非同期 invoke にリファクタ

## 5. デモ動画録画

### 録画ソフト（mac）

- **QuickTime Player**: 画面収録 → File / New Screen Recording
- **OBS Studio**: 細かい制御、シーン切替向き
- **CleanShot X**: 画面収録 + 編集機能

### 録画スクリプト（3 分版・docs/demo-script.md のショート版に対応）

1. 録画開始
2. ターミナル全画面: `python agent.py` 起動 → タイトルを見せる
3. プロンプト送信: `プレミアムな市況サマリが欲しい、上限0.005ドルで`
4. 承認カード表示 → ブラウザに切替
5. https://wallet-agent.vercel.app/ で承認待ち表示
6. 「承認」ボタン押下 → エージェント続行
7. 決済成功ログ + Sonnet 要約 表示
8. 録画停止

### 録画スクリプト（フル版・docs/demo-script.md の B1〜B3）

`docs/demo-script.md` の通り。承認 / 拒否 / Privy ダッシュボードまで見せる。

### 公開用編集

- DEV.to / Qiita 用には GIF も用意（`brew install ffmpeg` → mp4 → gif）
- アスペクト比: 16:9 (1920x1080) / 1:1 (SNS 用)

## 既知の制約

- AgentCore Runtime はpreviewのため、CodeBuild / IAM / ECR まわりが頻繁に更新される
- Vercel OIDC Federation は本番化したいが、 IAM ユーザー access key で代用中
- Lambda コンテナによる代替も可能（agent/AGENTCORE_RUNTIME.md 参照）
