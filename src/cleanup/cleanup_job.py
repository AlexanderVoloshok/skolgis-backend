import argparse
import os
import time
from pathlib import Path

def cleanup(dir_path: Path, retention_hours: float) -> int:
    now = time.time()
    cutoff = now - retention_hours * 3600
    removed = 0

    if not dir_path.exists():
        print(f"[cleanup] dir does not exist: {dir_path}")
        return 0

    for root, _, files in os.walk(dir_path):
        for name in files:
            p = Path(root) / name
            try:
                st = p.stat()
                if st.st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    removed += 1
            except Exception as e:
                print(f"[cleanup] failed to remove {p}: {e}")

    # опционально: удаляем пустые директории снизу вверх
    for root, dirs, files in os.walk(dir_path, topdown=False):
        if not dirs and not files:
            try:
                Path(root).rmdir()
            except Exception:
                pass

    print(f"[cleanup] removed={removed} dir={dir_path} retention_hours={retention_hours}")
    return removed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=os.getenv("EXPORT_DIR", "/data/exports"))
    parser.add_argument("--retention-hours", type=float, default=float(os.getenv("RETENTION_HOURS", "4")))
    args = parser.parse_args()

    cleanup(Path(args.dir), args.retention_hours)

if __name__ == "__main__":
    main()
