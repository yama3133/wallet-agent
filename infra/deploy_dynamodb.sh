#!/usr/bin/env bash
set -euo pipefail

STACK_NAME="${STACK_NAME:-wallet-agent-ddb}"
REGION="${AWS_REGION:-us-east-1}"

cd "$(dirname "$0")"

aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file dynamodb.yaml \
  --no-fail-on-empty-changeset \
  --region "$REGION"

aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output table
