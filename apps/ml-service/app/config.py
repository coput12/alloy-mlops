import os


class Config:
    """Все параметры приходят из окружения, чтобы код был одинаковым
    в docker-compose, в Kubernetes и в CI."""

    MODEL_PATH = os.getenv("MODEL_PATH", "models/model_rf.pkl")
    MODEL_VERSION = os.getenv("MODEL_VERSION", "rf-v1")

    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "predict_requests")

    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "predictions.completed")

    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
    REDIS_TASK_TTL = int(os.getenv("REDIS_TASK_TTL", "86400"))
    REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "86400"))

    POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://alloy:alloy@postgres:5432/alloy")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "alloy")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "alloy")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "alloy")

    DEFAULT_TEMP = float(os.getenv("DEFAULT_TEMP", "25.0"))