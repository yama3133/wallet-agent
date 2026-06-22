# AgentCore Runtime デプロイ手順

PoC では Vercel API Routes 経由でローカル Python エージェントを直接 invoke する構成にしたが、
本番では agent を AgentCore Runtime（または Lambda コンテナ）にデプロイする想定。

## エントリポイント

`agent.py` の末尾で `BedrockAgentCoreApp` を構築済み。

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload: dict) -> dict:
    prompt = payload.get("prompt", "")
    ...
```

ローカルで HTTP サーバとして動かす:

```bash
python agent.py serve
# → デフォルト 0.0.0.0:8080 でリスニング
```

## CLI でのデプロイ（要 tty）

`agentcore configure` は対話入力を要求するため、ターミナルから手動で:

```bash
cd agent
source .venv/bin/activate
agentcore configure -e agent.py -n walletagent --requirements-file requirements.txt
agentcore deploy
agentcore invoke '{"prompt": "プレミアムな市況サマリが欲しい、上限0.005ドルで"}'
```

- IAM 実行ロールは agentcore CLI が `wallet-agent-execution-role` のような名前で作成
- ECR / S3 / CodeBuild が裏で動く
- 環境変数は `--env` で agent.py に渡す:
  - `WALLET_AGENT_STORAGE=dynamo`
  - `WALLET_AGENT_APPROVALS_TABLE=wallet_agent_approvals`
  - `AWS_REGION=us-east-1`
  - `PRIVY_*` は AgentCore Identity経由が望ましい（直渡しは PoC 限定）

## 代替: Lambda コンテナ

時間がない場合は Lambda コンテナで:

```bash
# Dockerfile (省略) で agent.py を ENTRYPOINT に
docker build -t wallet-agent-lambda .
aws ecr create-repository --repository-name wallet-agent-lambda
docker tag wallet-agent-lambda:latest <ECR_URI>:latest
docker push <ECR_URI>:latest
aws lambda create-function \
  --function-name wallet-agent \
  --package-type Image \
  --code ImageUri=<ECR_URI>:latest \
  --role <EXEC_ROLE_ARN> \
  --timeout 900 \
  --memory-size 2048
```

Vercel API Routes は `lambda:InvokeFunction` で呼び出す。
