# 外部アカウント・クレデンシャル取得手順

Phase 1 PoC を動かすには、AWS とは別に Payment Provider のアカウントが要る。デフォルトは Stripe Privy。

## A. AWS の準備

```bash
# セッション切れていたら
aws login
aws sts get-caller-identity  # account 761018866498 が出ればOK
```

## B. Stripe Privy アカウント作成

PoC では Privy が必要。Stripe ブランドで動くが、内部は Privy が embedded crypto wallet を提供する。

1. https://dashboard.privy.io/ にアクセス → アカウント作成（無料）
2. 「Create new app」 → wallet-agent 専用のアプリを作る（他用途と混在させない）
3. **App settings** ページから以下をコピー
   - `App ID`
   - `App Secret`
4. **Wallet Infrastructure → Authorization** で「New Key」 → P-256 鍵ペアを生成
   - `Authorization ID`（公開鍵側）
   - `Authorization Private Key`（秘密鍵側）
5. Private key は **`wallet-auth:` プレフィックスを除いた base64 だけ** を使う

## C. （代替）Coinbase CDP アカウント作成

Privy ではなく Coinbase を使う場合：

1. https://docs.cdp.coinbase.com/api-reference/v2/authentication でアカウント作成
2. Project を作って「Create API Key」
   - `API Key ID`
   - `API Key Secret`
   - `Wallet Secret`
3. Project → Wallet → Embedded Wallets → Policies で **Delegated signing を ON**
4. `.env` の `PAYMENT_PROVIDER=CoinbaseCDP` に変更

## D. .env を埋める

```bash
cd agent/
cp .env.example .env
# エディタで .env を開き、B または C で取得した値を入れる
```

## E. テスト用ネットワークの USDC を入手

Phase 1 のテストネットは `base-sepolia`。ステップ 3 で出る `redirectUrl` をブラウザで開くと Coinbase/Privy のウォレットハブに飛ぶ。そこで以下：

- ログイン
- 「base-sepolia」を選択
- faucet から testnet USDC を入手して送金（PoC 用なら $1 分で十分）
- エージェント（このアプリ）に署名権限を付与

## F. スクリプト実行順

```bash
cd agent/
source .venv/bin/activate
cd scripts/
python 00_create_service_role.py
python 01_create_credential_provider.py
python 02_create_payment_manager.py
python 03_create_instrument.py   # 出力された URL でウォレット入金 → ACTIVE になるまで待つ
python 04_run_payment.py
```

実行結果は `agent/state.json` に追記される。再実行可。

## G. クリーンアップ

```bash
# 後日書く（delete_payment_* 系のスクリプト）
```

## トラブルシューティング

- `Your session has expired`: `aws login` を再実行
- PaymentManager が `CREATE_FAILED`: service role の trust policy か、リージョン確認
- `PaymentInstrument not active`: ウォレット入金 + 署名権限付与がまだ
- `Session expired or budget exceeded`: 新しいセッションを作るか、limits を上げる
- `process_payment` が `FAILED`: USDC 残高不足 or ガス代不足
