#!/usr/bin/env bash
# Creates (or updates) the martech/prod secret in AWS Secrets Manager.
# Run this once after provisioning your MongoDB, Redis, and OpenSearch services.
# Requires: aws CLI configured with sufficient IAM permissions.

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="martech/prod"

# ── Prompt for values ─────────────────────────────────────────────────────
read -rp "MongoDB URI (e.g. mongodb://user:pass@docdb-cluster:27017): " MONGO_URI
read -rp "Redis URL  (e.g. redis://martech.cache.amazonaws.com:6379/0): " REDIS_URL
read -rp "OpenSearch host (e.g. https://my-domain.us-east-1.es.amazonaws.com): " ES_HOST
read -rp "OpenSearch API key (leave blank if using IAM auth): " ES_API_KEY

SECRET_VALUE=$(jq -n \
  --arg m "$MONGO_URI" \
  --arg r "$REDIS_URL" \
  --argjson e "[\"$ES_HOST\"]" \
  --arg k "$ES_API_KEY" \
  '{MONGO_URI: $m, REDIS_URL: $r, ES_HOSTS: ($e | tostring), ES_API_KEY: $k}')

# Create or update
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" &>/dev/null; then
  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$SECRET_VALUE" \
    --region "$REGION"
  echo "Updated secret: $SECRET_NAME"
else
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Martech pipeline connection strings" \
    --secret-string "$SECRET_VALUE" \
    --region "$REGION"
  echo "Created secret: $SECRET_NAME"
fi
