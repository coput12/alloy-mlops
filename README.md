# Alloy MLOps — платформа прогнозирования прочности сплавов Fe-Co-Ni-Al-Ti

Full-stack MLOps/DevOps проект на реальных данных дипломной работы:
RandomForest-модель прогнозирует предел прочности (UTS, МПа) многокомпонентных
сплавов. Вокруг модели выстроена продакшн-инфраструктура: REST API, событийная
архитектура, мониторинг, CI/CD и деплой в Kubernetes.

```
┌───────────────────────────── CI/CD ──────────────────────────────┐
│ GitHub Actions: lint→test→build→push GHCR  ·  git push → автомат │
│   · retrain.yml: ночной переобучение на data/alloy_data.csv      │
│   · cd.yml: SSH на виртуалку → helm upgrade на k3s               │
└───────────────────────────────┬──────────────────────────────────┘
                                 ▼
            ┌──────────────────────────────────┐
  HTTP      │  REST API (Flask / gunicorn)     │
  /predict  │  - /health /metrics              │
            │  - /predict      — синхронный    │
            │  - /predict-batch — асинхронный  │
            └──────┬───────────────────┬───────┘
            кэш    │  Redis            │  RabbitMQ (predict_requests)
            Результаты                 ▼
        ┌───────────┐           ┌─────────────────┐
        │ Redis     │           │ ml-worker       │
        │ (кэш/     │           │ предсказание    │
        │  статусы) │           │ + метрики       │
        └───────────┘           └────────┬────────┘
                                         │ запись истории
                                         ▼
                                 ┌────────────────────┐
                                 │ PostgreSQL         │
                                 │ predictions (JSONB)│
                                 └────────┬───────────┘
                                          │ событие
                                          ▼
                              Kafka (topic: predictions.completed)
                                          │
                                          ▼
                              kafka-audit → MySQL (audit_log)
                                 ┌──────────────────────┐
                                 │ сервис-аудита         │
                                 └──────────────────────┘

Сквозной мониторинг: Prometheus (метрики /metrics) → Grafana (дашборд,
алерты), node-exporter. Логи: Filebeat → Elasticsearch → Kibana.
Инфраструктура: Zabbix (сервер+агент), K8s CronJob (ежедневный отчёт),
Terraform (Yandex Cloud), Ansible (bootstrap k3s).
```

## Что внутри

| Компонент | Технологии | Роль |
|---|---|---|
| `apps/ml-service/` | Flask, gunicorn | REST API, предсказание, батчи |
| `apps/ml-service/worker.py` | RabbitMQ, Kafka, PostgreSQL | асинхронная обработка задач |
| `apps/ml-service/kafka_audit.py` | Kafka → MySQL | аудит события через вторую СУБД |
| `apps/ml-service/daily_report.py` | PostgreSQL | отчёт для CronJob / crontab |
| `ml/train.py` | pandas, scikit-learn | пайплайн переобучения + метрики |
| `deploy/docker-compose.yml` | Docker | локальный весь стек (dev) |
| `deploy/helm/ml-service/` | Helm | чарт: Deployment, HPA, CronJob, ServiceMonitor |
| `deploy/terraform/` | Terraform | Yandex Cloud: сеть + ВМ + security group |
| `deploy/ansible/` | Ansible | bootstrap k3s на Ubuntu |
| `monitoring/` | Prometheus, Grafana | метрики, дашборд, алерты |
| `deploy/elk/` | Filebeat, Elasticsearch, Kibana | сбор и визуализация логов |
| `deploy/zabbix/` (профиль в compose) | Zabbix | мониторинг инфраструктуры |
| `.github/workflows/`, `.gitlab-ci.yml` | GitHub Actions, GitLab CI | CI/CD |

## Модель

- Источник: MPEA Database + литературные данные по сплавам Fe-Co-Ni-Al-Ti (709 записей)
- Фичи: `Fe, Co, Ni, Al, Ti, T_test_C, IsTensile`
- Модель: Random Forest Regressor, `model_rf.pkl`
- Метрики: CV R² = 0.787, MAE = 108 МПа (растяжение MAE = 97 МПа)

## Быстрый старт (локально, без Kubernetes)

Требуется: Linux (рекомендуется WSL2 или ваша Ubuntu-виртуалка) + Docker Compose v2.

```bash
git clone https://github.com/coput12/alloy-mlops.git
cd alloy-mlops
docker compose -f deploy/docker-compose.yml up --build -d
```

Проверка:

```bash
# здоровье
curl localhost:8000/health
# синхронное предсказание
curl -s -X POST localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"fe":20,"co":20,"ni":20,"al":20,"ti":20,"is_tensile":1}'
# асинхронный батч
TASK=$(curl -s -X POST localhost:8000/predict-batch \
  -H 'Content-Type: application/json' \
  -d '{"rows":[{"fe":20,"co":20,"ni":20,"al":20,"ti":20},{"fe":10,"co":20,"ni":30,"al":20,"ti":20}]}' | python -c "import sys,json;print(json.load(sys.stdin)['task_id'])")
curl localhost:8000/tasks/$TASK
```

Стек поднимется целиком: `postgres, mysql, redis, rabbitmq (UI :15672),
kafka, ml-service (:8000), ml-worker, kafka-audit, prometheus (:9090),
grafana (admin/admin, :3000), node-exporter`.

Дополнительно (profile):

```bash
docker compose -f deploy/docker-compose.yml --profile zabbix up -d   # Zabbix UI :8080
docker compose -f deploy/docker-compose.yml --profile elk up -d      # Kibana :5601
```

## Событийная архитектура (как работает батч)

1. `POST /predict-batch` — запрос принимается, в сообщение кладётся в RabbitMQ `predict_requests`, статус `queued` в Redis.
2. `ml-worker` забирает задачу, нормализует составы до 100%, предсказывает, сохраняет историю в PostgreSQL, публикует событие в Kafka `predictions.completed`.
3. `kafka-audit` потребляет событие и дублирует в MySQL `audit_log`.
4. Клиент опрашивает `GET /tasks/{id}` — статусы хранятся в Redis (TTL).

Причины выбора именно так:
- **RabbitMQ** — надёжная доставка задач в очередь (prefetch, ack) для работного тредпул;
- **Kafka** — потоковое событие «завершено» для многих потребителей (аудит, аналитика, уведомления) с replay-семантикой.

## Kubernetes (k3s на вашей Ubuntu-виртуалке)

Вариант A — Ansible:

```bash
cd deploy/ansible
cp inventory.ini.example inventory.ini   # впишите IP виртуалки
ansible-playbook -i inventory.ini bootstrap-k3s.yml
```

Вариант B — вручную:

```bash
bash scripts/setup-k3s.sh
```

Инфраструктурные сервисы вне кластера (реальный продакшн-паттерн — managed services).
Можно поднять их отдельно через compose (ред. `infra` секцию в
`deploy/helm/ml-service/values-k3s.yaml`, чтобы указать внешние адреса),
либо поставить в кластер через bitnami-чарты:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgres-internal bitnami/postgresql     --set auth.postgresPassword=alloy
helm install redis-internal  bitnami/redis            --set auth.enabled=false
helm install rabbitmq-internal bitnami/rabbitmq       --set auth.username=guest --set auth.password=guest
helm install kafka-internal  bitnami/kafka
helm install mysql-internal  bitnami/mysql            --set auth.rootPassword=root --set auth.database=alloy --set auth.username=alloy --set auth.password=alloy
```

Деплой приложения:

```bash
# в values-k3s.yaml укажите свой image.repository (см. ниже CI/CD)
bash scripts/deploy-k3s.sh
kubectl -n alloy get pods,hpa,cronjob
```

HPA масштабирует API-под 1→3 по CPU; CronJob `alloy-mlops-daily-report`
каждый день в 02:15 печатает сводку по предсказаниям.

## CI/CD

Через `Settings → Secrets → Actions` добавьте: `VM_HOST`, `VM_USER`, `VM_SSH_KEY`.
В `deploy/helm/ml-service/values.yaml` и `values-k3s.yaml` замените
`coput12` на ваш GitHub-ник, чтобы образы тянулись из вашего GHCR.

| Workflow | Триггер | Что делает |
|---|---|---|
| `ci.yml` | push/PR в main | ruff → pytest → сборка образа → push в GHCR |
| `retrain.yml` | ночью / вручную / изменения в `data/` | `ml/train.py` → коммит модели и метрик |
| `cd.yml` | после успешного CI | SSH на виртуалку → `helm upgrade` |
| `.gitlab-ci.yml` | GitLab | зеркало CI (lint/test/build+push) |

Ruff и pytest можно гонять локально:

```bash
pip install -r apps/ml-service/requirements-dev.txt
cd apps/ml-service && pytest -q
```

## Переобучение модели

```bash
python ml/train.py --data data/alloy_data.csv --out models/model_rf.pkl
# метрики → ml/artifacts/metrics.json, пикл → models/model_rf.pkl
```

## Terraform (обязательно поменять на своё облако)

`deploy/terraform/` поднимет в Yandex Cloud сеть, security group и ВМ Ubuntu,
на которую потом ставится k3s:

```bash
cd deploy/terraform
yc init
cp terraform.tfvars.example terraform.tfvars   # впишите cloud_id, folder_id, ssh key
terraform init && terraform plan && terraform apply
ssh ubuntu@$(terraform output -raw vm_public_ip)
```

## ## Раздел для резюме

База: `MLOps · CI/CD · Docker · Kubernetes (Helm/k3s) · Kafka · RabbitMQ ·
PostgreSQL · MySQL · Redis · Prometheus · Grafana · ELK · Zabbix ·
Ansible · Terraform · GitHub Actions · GitLab CI`

Формулировки:

- Построил MLOps-платформу прогнозирования прочности сплавов (RandomForest + Flask):
  REST API, асинхронная обработка батчей через RabbitMQ, событийная архитектура
  на Kafka, история предсказаний в PostgreSQL, аудит в MySQL, кэш в Redis.
- Настроил observability: Prometheus-метрики во всех сервисах (латенция, RPS,
  распределение предсказаний), Grafana-дашборд и алерты как код, логи в ELK,
  мониторинг хостов Zabbix.
- Автоматизировал жизненный цикл модели: ночной retrain-пайплайн в GitHub
  Actions, версионирование артефактов, авто-деплой в Kubernetes (k3s) через
  Helm с HPA и CronJob, второй CI-пайплайн на GitLab.
- Инфраструктура как код: Terraform (Yandex Cloud) + Ansible-плейбуки для
  bootstrap k3s.

## Дорожная карта / идеи для развития

- [ ] Канарейка и откат модели (A/B двух версий в кластере)
- [ ] Drift-детекция: переобучение при ухудшении метрик на новых данных
- [ ] Аргоцед / GitOps вместо SSH-деплоя
- [ ] Графан-алерты с уведомлениями в Telegram
- [ ] Нагрузочное тестирование k6 + демо HPA

## Заметка о безопасности

Все пароли в репозитории — демо-значения для локальной среды. В проде:
K8s Secret / External Secrets, managed Kafka/PG, secret-менеджер для CI/CD.