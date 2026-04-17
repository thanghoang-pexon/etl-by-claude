#!/usr/bin/env bash
# Öffnet ArgoCD und Harbor im Browser (Port-Forwarding)
set -euo pipefail

MINIKUBE_IP=$(minikube ip)

echo "============================================"
echo "  ArgoCD UI  →  http://localhost:8080"
echo "  User: admin"
echo "  Password: $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)"
echo ""
echo "  Harbor UI   →  http://${MINIKUBE_IP}:30080"
echo "  User: admin / Password: Harbor12345"
echo "============================================"
echo ""
echo "Starte Port-Forward für ArgoCD... (Ctrl+C zum Beenden)"
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
PF_PID=$!

open "http://localhost:8080" 2>/dev/null || true
open "http://${MINIKUBE_IP}:30080" 2>/dev/null || true

wait $PF_PID
