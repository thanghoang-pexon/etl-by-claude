#!/usr/bin/env bash
set -euo pipefail

echo "==> 1/5 Lokale Registry starten..."
if docker ps -a --format '{{.Names}}' | grep -q '^kind-registry$'; then
  docker start kind-registry 2>/dev/null || true
  echo "     kind-registry läuft bereits."
else
  docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2
  echo "     kind-registry gestartet auf localhost:5001"
fi

echo "==> 2/5 kind Cluster erstellen..."
if kind get clusters | grep -q '^etl-cluster$'; then
  echo "     Cluster 'etl-cluster' existiert bereits."
else
  kind create cluster --config kind-config.yml
fi

echo "==> 3/5 kind-registry mit Cluster-Netzwerk verbinden..."
docker network connect kind kind-registry 2>/dev/null || echo "     Bereits verbunden."

echo "==> 4/5 Registry-ConfigMap für Cluster anlegen..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5001"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo "==> 5/5 Cluster-Info"
kubectl cluster-info --context kind-etl-cluster
echo ""
echo "✓ Cluster bereit. Registry: localhost:5001"
echo "  kubectl get nodes"
