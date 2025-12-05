import os
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from pathlib import Path
from src.config import Config, MAIN_META
from src.sql_utils import execute_sql_and_commit

files_table = MAIN_META.tables['skolkovo_general.file_attachments'] 

def attatch_file(layer_name: str, fid: int, f) -> dict:
    """Сохраняет вложение как файл

    Args:
        layer_name (str): _description_
        fid (int): _description_
        f (_type_): _description_

    Returns:
        _type_: _description_
    """
    upload_root = Path(Config.UPLOAD_FOLDER + '/attachments').resolve()
    target_dir = upload_root / secure_filename(layer_name) / str(fid)

    #TODO: проверить, что такого файла ещё нет
    original_name = f.filename
    stored_name = _unique_store_name(original_name)
    dst_path = target_dir / stored_name
    target_dir.mkdir(parents=True, exist_ok=True)

    # 2) Сохраняем файл на диск
    f.save(dst_path)
    size_bytes = dst_path.stat().st_size
    mime = mimetypes.guess_type(original_name)[0]

    # 3) Обновляем БД (одна запись на файл)
    
    payload = {
        'layer': layer_name,
        'fid': fid,
        'original_name': original_name,
        'stored_name': stored_name,
        'mime': mime,
        'size_bytes': size_bytes
    }
    q = files_table.insert()\
        .values(payload)\
        .returning(files_table.c.id)
    cursor = execute_sql_and_commit(q)
    payload['id'] = cursor.fetchone()[0]
    return payload


def remove_file(layer_name: str, fid: int, filename: str):
    upload_root = Path(Config.UPLOAD_FOLDER + '/attachments').resolve()
    target_dir = upload_root / secure_filename(layer_name) / str(fid)
    stored_name = _unique_store_name(filename)
    dst_path = target_dir / stored_name
    os.remove(dst_path)

    q = files_table.delete().where(files_table.c.layer_name == layer_name and files_table.c.fid == fid and files_table.c.stored_name == stored_name)
    cursor = execute_sql_and_commit(q)
    return {"status": "ok", "stored_name": stored_name}


def _unique_store_name(original: str) -> str:
    """
    Возвращает уникальное имя вида {stem}__{uuid4}.{ext}
    чтобы одинаковые имена не конфликтовали в пределах одного объекта.
    """
    original = secure_filename(original) or "file"
    stem, dot, ext = original.rpartition(".")
    if not dot:  # нет точки
        stem, ext = original, ""
    uid = uuid.uuid4().hex
    if ext:
        return f"{stem}__{uid}.{ext}"
    return f"{stem}__{uid}"

