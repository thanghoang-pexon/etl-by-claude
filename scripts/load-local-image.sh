#!/usr/bin/env bash
# Lädt das lokale ETL-Image in minikube (für Tests ohne CI/ghcr.io)
set -euo pipefail

IMAGE="localhost:5001/etl-nba:local"

echo "==> Image bauen..."
docker build -t "$IMAGE" ./etl-repository

echo "==> Image in minikube laden..."
minikube image load "$IMAGE"

echo "==> values.yaml auf lokales Image setzen..."
sed -i '' \
  -e "s|repository: .*|repository: localhost:5001/etl-nba|" \
  -e "s|tag: .*|tag: local|" \
  -e "s|pullPolicy: .*|pullPolicy: Never|" \
  ops-repository/helm/etl-stack/values.yaml

echo ""
echo "✓ Image in minikube geladen."
echo "  ArgoCD 'Sync' klicken oder: kubectl -n argocd app sync etl-stack"
