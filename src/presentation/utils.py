import re
from pathlib import Path
from typing import Optional, List
from src.config import Config

CAD_RE = re.compile(r"\b\d{2}:\d{2}:\d{1,7}:\d+\b")

def extract_cadastral_numbers(text: str, unique: bool = True) -> List[str]:
    nums = CAD_RE.findall(text or "")
    if unique:
        # уникальные, сохраняя порядок
        nums = list(dict.fromkeys(nums))
    return nums

def read_file_bytes(stored_name: Optional[str]) -> Optional[bytes]:
    """
    Возвращает содержимое файла в байтах.
    Если file_path None / пустой / файл не существует — возвращает None.
    """
    if not stored_name:
        return None
    
    upload_root = Path(Config.UPLOAD_FOLDER + '/attachments').resolve()
    dst_path = upload_root / stored_name
    path = Path(dst_path)
    if not path.is_file():
        return None

    return path.read_bytes()