"""Ежедневный отчёт: запускается K8s CronJob или системным crontab."""
import logging
import sys
from datetime import datetime

import psycopg2

from app.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("daily-report")


def main():
    conn = psycopg2.connect(Config.POSTGRES_DSN)
    cur = conn.cursor()

    cur.execute(
        "SELECT COALESCE(MAX(created_at)::date, '1970-01-01') FROM predictions"
    )
    last_date = cur.fetchone()[0]
    cur.execute(
        "SELECT model_version, COUNT(*), MAX(created_at) "
        "FROM predictions GROUP BY model_version ORDER BY 2 DESC"
    )
    by_version = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM predictions")
    total = cur.fetchone()[0]
    conn.close()

    print(f"=== ЕЖЕДНЕВНЫЙ ОТЧЁТ {datetime.now().isoformat()} ===")
    print(f"Всего предсказаний в PostgreSQL: {total}")
    print(f"Последний день записи: {last_date}")
    print("По версиям модели:")
    if not by_version:
        print("  (записей пока нет)")
    for version, cnt, ts in by_version:
        print(f"  {version}: {cnt} записей, последняя {ts}")

    if total == 0:
        raise SystemExit("Нет данных — отчёт не сформирован")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log.error("Отчёт упал: %s", e)
        sys.exit(1)