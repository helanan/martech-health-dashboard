#!/usr/bin/env bash
# Creates the IAM role + policy for IRSA so the martech pod can read Secrets Manager.
# Requires: aws CLI, eksctl or kubectl with cluster access.

set -euo pipefail

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${EKS_CLUSTER_NAME:-martech-cluster}"
ROLE_NAME="martech-secrets-role"
POLICY_NAME="martech-secrets-policy"
NAMESPACE="martech"
SERVICE_ACCOUNT="martech-sa"

# Get the OIDC provider for your EKS cluster
OIDC_PROVIDER=$(aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --query "cluster.identity.oidc.issuer" \
  --output text | sed 's|https://||')

echo "OIDC Provider: $OIDC_PROVIDER"

# Create IAM policy
POLICY_ARN=$(aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"secretsmanager:GetSecretValue\", \"secretsmanager:DescribeSecret\"],
      \"Resource\": \"arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:martech/*\"
    }]
  }" \
  --query "Policy.Arn" --output text 2>/dev/null || \
  aws iam list-policies --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" --output text)

echo "Policy ARN: $POLICY_ARN"

# Create IAM role with trust policy for IRSA
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Principal\": {\"Federated\": \"arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}\"},
      \"Action\": \"sts:AssumeRoleWithWebIdentity\",
      \"Condition\": {
        \"StringEquals\": {
          \"${OIDC_PROVIDER}:sub\": \"system:serviceaccount:${NAMESPACE}:${SERVICE_ACCOUNT}\"
        }
      }
    }]
  }" 2>/dev/null || echo "Role already exists, skipping creation."

aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"

echo ""
echo "Done. Update k8s/base/service-account.yaml with:"
echo "  arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
