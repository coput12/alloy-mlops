#!/usr/bin/env bash
# Деплой приложения в k3s через Helm. 
# Образ должен лежать в ghcr.io/coput12/alloy-mlops
# (собирается GitHub Actions), а инфраструктура (PG/Redis/Kafka/RabbitMQ/MySQL)
# развёрнута отдельно — см. README раздел "Kubernetes (k3s)".
set -euo pipefail

NAMESPACE="${NAMESPACE:-alloy}"
RELEASE="alloy-mlops"
CHART="./deploy/helm/ml-service"
VALUES="${VALUES:-./deploy/helm/ml-service/values-k3s.yaml}"

kubectl create namespace "$NAMESPACE" 2>/dev/null || true

helm upgrade --install "$RELEASE" "$CHART" \
    --namespace "$NAMESPACE" \
    --create-namespace \
    --values "$VALUES" \
    --wait --timeout 5m

echo ">> Статус:"
kubectl -n "$NAMESPACE" get pods -l app=ml-service
kubectl -n "$NAMESPACE" get hpa
kubectl -n "$NAMESPACE" get cronjob