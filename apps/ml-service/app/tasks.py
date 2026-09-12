import json
import uuid
from typing import List

import pika
import redis

from .config import Config


def _redis():
    return redis.from_url(Config.REDIS_URL, decode_responses=True)


def publish_batch(rows: List[dict], t_test_c: float, is_tensile: int) -> str:
    """Кладёт задачу в RabbitMQ и записывает статус в Redis."""
    task_id = uuid.uuid4().hex
    body = {
        "task_id": task_id,
        "rows": rows,
        "t_test_c": t_test_c,
        "is_tensile": int(is_tensile),
    }
    params = pika.URLParameters(Config.RABBITMQ_URL)
    conn = pika.BlockingConnection(params)
    try:
        ch = conn.channel()
        ch.queue_declare(queue=Config.RABBITMQ_QUEUE, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=Config.RABBITMQ_QUEUE,
            body=json.dumps(body).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        conn.close()

    _redis().set(f"task:{task_id}", json.dumps({"status": "queued"}), ex=Config.REDIS_TASK_TTL)
    return task_id


def get_task(task_id: str):
    raw = _redis().get(f"task:{task_id}")
    if not raw:
        return None
    return json.loads(raw)


def set_task(task_id: str, value: dict) -> None:
    _redis().set(f"task:{task_id}", json.dumps(value, default=str), ex=Config.REDIS_TASK_TTL)


def cache_get(key: str):
    raw = _redis().get(f"cache:{key}")
    return json.loads(raw) if raw else None


def cache_set(key: str, value: dict) -> None:
    _redis().set(f"cache:{key}", json.dumps(value), ex=Config.REDIS_CACHE_TTL)