import json
import logging
import uuid

import pika
import redis
from redis.exceptions import RedisError

from .config import Config

log = logging.getLogger(__name__)


def _redis():
    return redis.from_url(Config.REDIS_URL, decode_responses=True)


def _redis_set(key: str, value: str, ttl: int) -> None:
    try:
        _redis().set(key, value, ex=ttl)
    except RedisError as e:
        log.warning("Redis недоступен, пишем мимо кэша: %s", e)


def _redis_get(key: str):
    try:
        return _redis().get(key)
    except RedisError as e:
        log.warning("Redis недоступен, читаем мимо кэша: %s", e)
        return None


def publish_batch(rows: list[dict], t_test_c: float, is_tensile: int) -> str:
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

    _redis_set(f"task:{task_id}", json.dumps({"status": "queued"}), Config.REDIS_TASK_TTL)
    return task_id


def get_task(task_id: str):
    raw = _redis_get(f"task:{task_id}")
    if not raw:
        return None
    return json.loads(raw)


def set_task(task_id: str, value: dict) -> None:
    _redis_set(f"task:{task_id}", json.dumps(value, default=str), Config.REDIS_TASK_TTL)


def cache_get(key: str):
    raw = _redis_get(f"cache:{key}")
    return json.loads(raw) if raw else None


def cache_set(key: str, value: dict) -> None:
    _redis_set(f"cache:{key}", json.dumps(value), Config.REDIS_CACHE_TTL)