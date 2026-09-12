#!/usr/bin/env bash
# Ручной bootstrap k3s на Ubuntu-виртуалке (если не используете Ansible).
set -euo pipefail

VERSION="${K3S_VERSION:-v1.30.2+k3s2}"

echo ">> Установка k3s $VERSION"
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$VERSION" \
    INSTALL_K3S_EXEC="--write-kubeconfig-mode 644" sh -

echo ">> kubeconfig: ~/.kube/config (копируем из /etc/rancher/k3s/k3s.yaml)"
mkdir -p "$HOME/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
sudo chown "$USER" "$HOME/.kube/config"

echo ">> Установка helm"
curl -fsSL https://get.helm.sh/helm-v3.15.2-linux-amd64.tar.gz -o /tmp/helm.tar.gz
tar -xzf /tmp/helm.tar.gz -C /tmp
sudo mv /tmp/linux-amd64/helm /usr/local/bin/helm
rm -rf /tmp/linux-amd64 /tmp/helm.tar.gz

echo ">> Проверка"
kubectl version --short --client
kubectl get nodes
helm version