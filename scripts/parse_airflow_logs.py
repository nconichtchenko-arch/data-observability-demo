import os
import re
import glob
import psycopg2
from datetime import datetime
from pathlib import Path

# Настройки подключения к БД (Windows)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "dwh_marketplace",
    "user": "dwh_user",
    "password": "dwh_password",
}

# Путь к логам (папка, куда мы скопировали логи из VM)
LOGS_DIR = Path(r"H:\Projects\data-observability-demo\logs_clean")

def parse_log_file(file_path):
    """Парсит один лог-файл и возвращает метрики."""
    dag_id = None
    task_id = None
    execution_date = None
    status = "unknown"
    duration = None
    error_msg = None

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. Ищем dag_id и task_id в контексте Airflow (AIRFLOW_CTX_DAG_ID / AIRFLOW_CTX_TASK_ID)
    dag_match = re.search(r"AIRFLOW_CTX_DAG_ID='([^']+)'", content)
    task_match = re.search(r"AIRFLOW_CTX_TASK_ID='([^']+)'", content)

    if dag_match:
        dag_id = dag_match.group(1)
    if task_match:
        task_id = task_match.group(1)

    # Если не нашли через контекст, пробуем старый способ (dag_id=...)
    if not dag_id:
        match = re.search(r"dag_id=([a-zA-Z0-9_]+)", content)
        if match:
            dag_id = match.group(1)
    if not task_id:
        match = re.search(r"task_id=([a-zA-Z0-9_]+)", content)
        if match:
            task_id = match.group(1)

    # 2. Ищем статус (Success/Failed)
    if "Task exited with return code 0" in content or "Marking task as SUCCESS" in content:
        status = "success"
    elif "Task exited with return code 1" in content or "Marking task as FAILED" in content:
        status = "failed"

    # 3. Ищем длительность (Duration)
    dur_match = re.search(r"Task duration:\s*([\d.]+)s", content)
    if dur_match:
        duration = float(dur_match.group(1))

    # 4. Ищем ошибку (Exception / Error)
    error_match = re.search(r"(Exception|Error):\s*(.+)", content)
    if error_match:
        error_msg = error_match.group(2).strip()[:500]

    # 5. Ищем дату выполнения (из первой строки, обычно там timestamp)
    date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})", content)
    if date_match:
        try:
            execution_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
        except:
            pass

    return {
        "dag_id": dag_id,
        "task_id": task_id,
        "execution_date": execution_date,
        "status": status,
        "duration_seconds": duration,
        "error_message": error_msg,
        "log_file_path": str(file_path),
    }

def save_to_db(metrics_list):
    """Сохраняет метрики в PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for m in metrics_list:
        if not m["dag_id"] or not m["task_id"]:
            continue  # пропускаем, если не удалось распарсить

        cur.execute("""
            INSERT INTO public.airflow_logs_metrics
            (dag_id, task_id, execution_date, status, duration_seconds, error_message, log_file_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            m["dag_id"], m["task_id"], m["execution_date"],
            m["status"], m["duration_seconds"], m["error_message"], m["log_file_path"]
        ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"Сохранено {len(metrics_list)} записей.")

def main():
    # Ищем все .log файлы в папке logs_clean
    log_files = glob.glob(str(LOGS_DIR / "*.log"))
    print(f"Найдено лог-файлов: {len(log_files)}")

    all_metrics = []
    for lf in log_files:
        metrics = parse_log_file(lf)
        all_metrics.append(metrics)

    if all_metrics:
        save_to_db(all_metrics)
    else:
        print("Нет данных для сохранения.")

if __name__ == "__main__":
    main()
