"""Воркер: RabbitMQ (predict_requests) -> модель -> PostgreSQL + Kafka (predictions.completed).

Пример асинхронной обработки baтч-задач: API кладёт задачу в очередь,
воркер считает и публикует событие в Kafka, событие аудитится в MySQL.
"""
import json
import logging
import time
from datetime import datetime, timezone

import pika
from app.config import Config
from app.db import ensure_postgres, insert_predictions
from app.features import COMPONENTS, row_to_features
from app.metrics import LATENCY, PREDICT_VALUE, PREDICTIONS
from app.model import ModelService
from app.tasks import set_task
from confluent_kafka import Producer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def _kafka_delivery(err, msg):
    if err is not None:
        log.error("Kafka: отправка не удалась: %s", err)
    else:
        log.info("Kafka: событие опубликовано в %s", msg.topic())


def main():
    service = ModelService()
    service.load()
    if not service.ready:
        log.error("Модель не загружена, воркер останавливается")
        raise SystemExit(1)
    ensure_postgres(Config.POSTGRES_DSN)

    producer = Producer({"bootstrap.servers": Config.KAFKA_BOOTSTRAP_SERVERS})

    def on_message(ch, method, properties, body):
        try:
            msg = json.loads(body)
            task_id = msg["task_id"]
            rows = msg["rows"]
            t_test_c = float(msg.get("t_test_c", Config.DEFAULT_TEMP))
            is_tensile = int(msg.get("is_tensile", 1))

            set_task(task_id, {"status": "processing", "n_rows": len(rows)})

            results = []
            for row in rows:
                feat = row_to_features(row, t_test_c, is_tensile)
                start = time.perf_counter()
                value = service.predict(feat)
                LATENCY.labels(kind="batch").observe(time.perf_counter() - start)
                PREDICT_VALUE.labels(kind="batch").observe(value)
                results.append({
                    **{k: float(row.get(k, 0.0) or 0.0) for k in COMPONENTS},
                    "prediction": round(value, 1),
                })

            PREDICTIONS.labels(kind="batch").inc(len(results))
            insert_predictions(
                Config.POSTGRES_DSN, task_id, len(results),
                service.version, {"rows": results},
            )

            event = {
                "task_id": task_id,
                "n_rows": len(results),
                "model_version": service.version,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            producer.produce(Config.KAFKA_TOPIC, json.dumps(event).encode(), callback=_kafka_delivery)
            producer.flush()

            set_task(task_id, {"status": "done", "n_rows": len(results), "model_version": service.version, "results": results})
            ch.basic_ack(delivery_tag=method.delivery_tag)
            log.info("Задача %s выполнена: %s предсказаний", task_id, len(results))
        except Exception:
            log.exception("Обработка задачи упала")
            try:
                set_task(json.loads(body)["task_id"], {"status": "failed"})
            except Exception as e:  # noqa: BLE001
                log.warning("Не удалось сохранить статус failed: %s", e)
            ch.basic_ack(delivery_tag=method.delivery_tag)

    params = pika.URLParameters(Config.RABBITMQ_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=Config.RABBITMQ_QUEUE, durable=True)
    ch.basic_qos(prefetch_count=10)
    ch.basic_consume(Config.RABBITMQ_QUEUE, on_message)
    log.info("Воркер готов, слушаем очередь %s", Config.RABBITMQ_QUEUE)
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        log.info("Остановка воркера")
        conn.close()


if __name__ == "__main__":
    main()