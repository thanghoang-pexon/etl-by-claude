#!/usr/bin/env bash
set -euo pipefail

echo "==> 1/5 Apache Airflow Helm Repo hinzufügen..."
helm repo add apache-airflow https://airflow.apache.org 2>/dev/null || true
helm repo update

echo "==> 2/5 Namespace + Postgres-Secret anlegen..."
kubectl create namespace airflow 2>/dev/null || true
kubectl apply -f ops-repository/k8s/etl-postgres-secret-airflow.yaml

echo "==> 3/5 Airflow via Helm installieren (dauert 2-3 Minuten)..."
helm upgrade --install airflow apache-airflow/airflow \
  --namespace airflow \
  -f ops-repository/helm/airflow-values.yaml \
  --timeout 10m \
  --wait

echo "==> 4/5 ArgoCD Application für Airflow anlegen..."
kubectl apply -f ops-repository/argocd/airflow-application.yaml

echo "==> 5/5 Status prüfen..."
kubectl -n airflow get pods

AIRFLOW_PW=$(kubectl -n airflow get secret airflow -o jsonpath="{.data.webserver-secret-key}" 2>/dev/null | base64 -d || echo "admin123")

echo ""
echo "============================================"
echo "  Airflow UI → http://localhost:8081"
echo "  User: admin / Password: admin123"
echo "============================================"
echo ""
echo "Port-Forward starten mit:"
echo "  kubectl port-forward svc/airflow-webserver -n airflow 8081:8080"
