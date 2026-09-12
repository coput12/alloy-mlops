"""Kafka-audit: потребитель topic predictions.completed -> MySQL audit_log."""
import json
import logging

from confluent_kafka import Consumer

from app.config import Config
from app.db import audit_insert, ensure_mysql

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("kafka-audit")


def main():
    ensure_mysql(Config.MYSQL_HOST, Config.MYSQL_PORT,
                 Config.MYSQL_USER, Config.MYSQL_PASSWORD, Config.MYSQL_DATABASE)

    consumer = Consumer({
        "bootstrap.servers": Config.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": "audit-group",
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    })
    consumer.subscribe([Config.KAFKA_TOPIC])

    log.info("Kafka-audit слушает topic %s", Config.KAFKA_TOPIC)
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                log.warning("Kafka error: %s", msg.error())
                continue
            try:
                data = json.loads(msg.value())
            except json.JSONDecodeError:
                data = {"raw": msg.value().decode(errors="replace")}
            audit_insert(
                Config.MYSQL_HOST, Config.MYSQL_PORT,
                Config.MYSQL_USER, Config.MYSQL_PASSWORD, Config.MYSQL_DATABASE,
                "prediction.completed", data.get("task_id"), data,
            )
            log.info("Продублировано событие %s в MySQL", data.get("task_id"))
    except KeyboardInterrupt:
        log.info("Останавливаю Kafka-audit")


if __name__ == "__main__":
    main()