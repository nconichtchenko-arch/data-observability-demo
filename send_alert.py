import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
import os
from dotenv import load_dotenv

# Загружаем переменные окружения (SMTP и БД)
load_dotenv()

# Настройки SMTP (Mail.ru)
SMTP_HOST = "smtp.mail.ru"
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER", "pavloni@mail.ru")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Пароль из .env
SMTP_TO = os.getenv("SMTP_TO", "pavloni@mail.ru")

# Настройки БД (Windows)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "dwh_marketplace",
    "user": "dwh_user",
    "password": "dwh_password",
}

def check_logs():
    """Проверяет БД на наличие ошибок в логах Airflow."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Ищем задачи, которые упали за последние 24 часа
    cur.execute("""
        SELECT dag_id, task_id, error_message, log_file_path
        FROM public.airflow_logs_metrics
        WHERE status = 'failed'
          AND parsed_at >= NOW() - INTERVAL '24 hours'
        ORDER BY parsed_at DESC
        LIMIT 10;
    """)
    
    errors = cur.fetchall()
    cur.close()
    conn.close()
    return errors

def send_email(errors):
    """Отправляет письмо с ошибками."""
    if not errors:
        print("✅ Ошибок нет, письмо не отправляем.")
        return
    
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg["Subject"] = f"🚨 Data Observability Alert: {len(errors)} упавших задач"
    
    body = "Обнаружены ошибки в пайплайнах Airflow:\n\n"
    for i, (dag_id, task_id, error_msg, log_path) in enumerate(errors, 1):
        body += f"{i}. DAG: {dag_id}, Task: {task_id}\n"
        body += f"   Ошибка: {error_msg}\n"
        body += f"   Лог: {log_path}\n\n"
    
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Письмо отправлено на {SMTP_TO} (ошибок: {len(errors)})")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

if __name__ == "__main__":
    print("🔍 Проверяю логи Airflow...")
    errors = check_logs()
    send_email(errors)