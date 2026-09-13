#!/usr/bin/env bash
# Деплой приложения в k3s через Helm.
# Образ должен лежать в ghcr.io/coput12/alloy-mlops
# (собирается GitHub Actions), а инфраструктура (PG/Redis/Kafka/RabbitMQ/MySQL)
# развёрнута на хосте в docker-compose — адресуется через IP этой машины.
set -euo pipefail

NAMESPACE="${NAMESPACE:-alloy}"
RELEASE="alloy-mlops"
CHART="${CHART:-./deploy/helm/ml-service}"
VALUES="${VALUES:-./deploy/helm/ml-service/values-k3s.yaml}"

# k3s хранит kubeconfig по умолчанию здесь; работает и от root (sudo в CD), и от user.
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

if [ ! -r "$KUBECONFIG" ]; then
  if [ "$(id -u)" = 0 ] || sudo -n true 2>/dev/null; then
    sudo chmod 644 "$KUBECONFIG"
  else
    echo ">> kubeconfig $KUBECONFIG недоступен для чтения. Выполни: sudo chmod 644 $KUBECONFIG" >&2
    exit 1
  fi
fi

VMIP="${VMIP:-$(hostname -I | awk '{print $1}')}"
echo ">> Инфраструктура (docker-compose на хосте) адресуется через ${VMIP}"

kubectl create namespace "$NAMESPACE" 2>/dev/null || true

helm upgrade --install "$RELEASE" "$CHART" \
    --namespace "$NAMESPACE" \
    --create-namespace \
    --values "$VALUES" \
    --set infra.rabbitmqUrl="amqp://guest:guest@${VMIP}:5672/" \
    --set infra.kafkaBootstrap="${VMIP}:9092" \
    --set infra.redisUrl="redis://${VMIP}:6379/0" \
    --set infra.postgresDsn="postgresql://alloy:alloy@${VMIP}:5432/alloy" \
    --set infra.mysqlHost="${VMIP}" \
    --set infra.mysqlPort=3306 \
    --wait --timeout 8m

echo ">> Статус:"
kubectl -n "$NAMESPACE" get pods -l app=ml-service
kubectl -n "$NAMESPACE" get hpa
kubectl -n "$NAMESPACE" get cronjob