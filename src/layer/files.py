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

    original_name = f.filename
    stored_name = _unique_store_name(original_name)
    dst_path = upload_root / stored_name

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
    dst_path = upload_root / filename
    try:
        os.remove(dst_path)
    except:
        print(f"{filename}: no such file")
    q = files_table.delete().where(files_table.c.layer == layer_name, files_table.c.fid == fid,  files_table.c.stored_name == filename)
    cursor = execute_sql_and_commit(q)

    return {"status": "ok", "stored_name": filename}, 201


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

