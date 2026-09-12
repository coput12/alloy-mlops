import json
import logging

import psycopg2
import pymysql
from psycopg2.extras import Json

log = logging.getLogger(__name__)

# PostgreSQL: история batch-предсказаний
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id            BIGSERIAL PRIMARY KEY,
    task_id       TEXT NOT NULL,
    n_rows        INT  NOT NULL,
    model_version TEXT,
    payload       JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_predictions_task    ON predictions(task_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at);
"""

# MySQL: аудит событий Kafka (используем вторую СУБД для демонстрации мульти-DB стека)
MYSQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type VARCHAR(64)  NOT NULL,
    task_id    VARCHAR(64),
    payload    JSON,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_postgres(dsn: str) -> None:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_SCHEMA)
        conn.commit()


def insert_predictions(dsn: str, task_id: str, n_rows: int, model_version: str, payload: dict) -> None:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO predictions (task_id, n_rows, model_version, payload) "
                "VALUES (%s, %s, %s, %s)",
                (task_id, n_rows, model_version, Json(payload)),
            )
        conn.commit()


def _mysql_connect(host, port, user, password, database):
    return pymysql.connect(host=host, port=port, user=user, password=password,
                           database=database, autocommit=False)


def ensure_mysql(host, port, user, password, database) -> None:
    cnx = _mysql_connect(host, port, user, password, database)
    try:
        with cnx.cursor() as cur:
            cur.execute(MYSQL_SCHEMA)
        cnx.commit()
    finally:
        cnx.close()


def audit_insert(host, port, user, password, database, event_type, task_id, payload) -> None:
    cnx = _mysql_connect(host, port, user, password, database)
    try:
        with cnx.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (event_type, task_id, payload) VALUES (%s, %s, %s)",
                (event_type, task_id, json.dumps(payload, default=str)),
            )
        cnx.commit()
    finally:
        cnx.close()