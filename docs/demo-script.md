# wallet-agent デモ台本

「AIに財布を渡す日」を見せるための実機デモ。同じ実装で複数登壇に対応する。

## 用途別バージョン

| 登壇 | 形式 | 尺 | 重視点 |
|---|---|---|---|
| re:Invent 2026 COM Track | Breakout L300 単独 | 60分 | アーキ + Autonomy vs Approval 議論 |
| Qiita Tech Festa Day | LT 10分 | 7分実演 | 実機の生映像、承認カード往復 |
| iOSDC LT5 | LT 5分 | 3分実演 | コンセプトと「財布を渡す瞬間」 |
| re:Deploy Security | Breakout (英) 25分 | 5分実演 | セキュリティ境界・最小権限 |

## 0. 事前準備（必須）

1. `aws login` 済（acct 761018866498/us-east-1）
2. `agent/.env` に Privy creds 入力済
3. Privy template (`~/wallet-agent-privy-template`) で `pnpm dev` を裏で起動
4. wallet `0xE50ff0d8C64667548e4Ee742Ab34D79FDd74Bf92` に base-sepolia 20 USDC（推奨）
5. `agent/state.json` が最新Instrument に向いている確認
6. ターミナル2枚 (agent対話 / 承認CLI)

## A. ショートデモ（3 分版）

iOSDC LT 等の超短尺向け。

```bash
# 別端末: pnpm dev は事前起動済み
cd ~/wallet-agent/agent
source .venv/bin/activate

WALLET_AGENT_AUTO_APPROVE=1 AWS_REGION=us-east-1 \
  python agent.py run "プレミアムな市況サマリが欲しい、上限0.005ドルで"
```

**口頭で見せるポイント**

1. 「Sonnet 4.6 が候補リソースを探した（`search_paid_resources`）」
2. 「**人間承認カード**が発行された（`request_payment_approval`）」
3. 「**自動承認モード**なので今は通すが、本来はここで人間が判断」
4. 「**Privy + AgentCore Payments** が x402 で USDC 0.001 を送金」
5. 「実コンテンツが返ってきて、エージェントが日本語要約」

## B. フルデモ（7-10 分版）

Qiita Tech Festa LT / re:Invent Breakout の実演ブロック向け。

### B1. 「自律 vs 承認」を見せる（メイン）

```bash
# 1. 対話モード起動
python agent.py
> プレミアムな市況サマリが欲しい、上限0.005ドルで
```

承認カードが表示されて止まる。

```bash
# 2. 別端末で
python agent.py pending          # 承認待ち一覧を見せる
python agent.py approve <id>     # 承認
```

エージェントが続行 → 決済 → コンテンツ取得 → 要約。

### B2. 「拒否したらどうなる」を見せる

```bash
# 同じプロンプト
> プレミアムな市況サマリが欲しい、上限0.005ドルで
# 別端末で
python agent.py reject <id>
```

→ エージェントは「決済できないので結果を返せない」を日本語で説明。**承認ゲートが効いている**ことを実機で示す。

### B3. Privyダッシュボードを並べる

ブラウザで以下を並べる：
1. `localhost:3001` (Privy template ダッシュボード、Connect agent 完了状態)
2. `dashboard.privy.io/.../authorization-keys` (Authorization Key の Signer for 列)
3. `sepolia.basescan.org/address/0xE50ff...` (オンチェーン tx)

「**ユーザーが Connect agent しない限り、agent は1円も動かせない**」と説明。

## C. アーキテクチャ説明用スライド

re:Invent / re:Deploy 向け（25-60分セッションの最後）

```
┌──────────────┐   ┌──────────────────┐   ┌────────────────────┐
│ User (Vercel)│←─→│ Strands Agent    │←─→│ AgentCore Payments │
│ /chat        │   │ (Sonnet 4.6)     │   │ (PaymentManager,   │
│ /approvals   │   │ - search         │   │  Connector, Inst.) │
└──────────────┘   │ - request_approval│   └─────────┬──────────┘
                   │ - execute_x402   │             │
                   └──────────────────┘             │
                            ↑                       │
                            │ approve via DDB       │
                   ┌────────┴────────┐              │
                   │ DynamoDB        │              ▼
                   │ tasks/approvals │   ┌────────────────────┐
                   └─────────────────┘   │ Privy (StripePrivy)│
                                         │ x402 wallet signer │
                                         └─────────┬──────────┘
                                                   │
                                                   ▼
                                         ┌────────────────────┐
                                         │ x402 Merchant      │
                                         │ (drvd12nx....)     │
                                         └────────────────────┘
```

「承認ゲートを通らない限り `execute_x402_payment` ツールは呼ばれない」が中核メッセージ。

## D. 失敗時の救済

- Bedrock 認証切れ → `aws login` 再実行
- 残高不足 → faucet 再実行（Circle / Alchemy faucet）
- マーチャント側 simulation_failed → 数秒後 retry（PoCでも観測した過渡的現象）
- Privy signer 未登録 → `localhost:3001` で「Connect agent」をクリック

## E. 録画用の絵作り

| シーン | 画面 | 推奨秒数 |
|---|---|---|
| タイトル | 「AIに財布を渡す日」 | 3 |
| 依頼入力 | ターミナル: prompt | 4 |
| エージェント思考 | Tool #1, #2 表示 | 4 |
| 承認カード | 大写し | 5 |
| 承認操作 | 別端末 approve | 5 |
| 決済成功 | "Successfully processed payment" | 4 |
| コンテンツ表示 | 要約 | 8 |
| まとめ | architecture スライド | 5 |

**合計 ~38 秒 × 2 速 = 19 秒バージョンも可能**（SNS 用）。

## F. 関連登壇のリンク（memoryから）

- [[project_reinvent_com_cfp]] re:Invent 2026 COM Track 本命③
- [[project-qiita-tech-festa-day-2026-cfp]] Qiita Tech Festa Day 2026
- [[project-iosdc-japan-2026-cfp]] iOSDC LT5
- [[project_redeploy_2026]] re:Deploy 2026 Security
- [[project_aegis_slackhack]] Aegis Slackハッカソン（同じ承認軸の別実装）
