# /app/setup_cron.py
import os
from pathlib import Path

CRON_FILE = Path("/etc/cron.d/export_cleanup")

def main():
    schedule = os.getenv("CLEANUP_CRON", "0 4 * * *")  # каждый день в 04:00
    export_dir = os.getenv("EXPORT_DIR", "/src/files/tmp")
    retention_hours = os.getenv("RETENTION_HOURS", "4")

    # Важно: /etc/cron.d файл должен быть 0644 и с newline в конце
    content = f"""SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

{schedule} root /usr/local/bin/python /src/cleanup/cleanup_job.py --dir "{export_dir}" --retention-hours {retention_hours} >> /proc/1/fd/1 2>> /proc/1/fd/2
"""
    CRON_FILE.write_text(content, encoding="utf-8")
    os.chmod(CRON_FILE, 0o644)

    print(f"[cron] installed: {CRON_FILE} schedule='{schedule}' export_dir='{export_dir}' retention_hours={retention_hours}")

if __name__ == "__main__":
    main()
