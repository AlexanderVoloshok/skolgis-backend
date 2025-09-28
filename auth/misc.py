import json
import bcrypt
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sql_utils import execute_sql_and_commit
from config import Config
from utils import get_logger

logger = get_logger(__name__)


def drop_user_state(user_id: str, variable: str):
    q = text("""UPDATE skolkovo_general.users SET state = state::jsonb - '{"%s"}'::text[] WHERE id = '%s';""" % (variable, user_id))
    res = execute_sql_and_commit(q)
    return {"status": "ok"}


def password_hash_json():
    plain_password = bcrypt.gensalt().decode("utf-8")[:12]  # временный пароль
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    payload = {"password_hash": hashed, "must_change_password": True, "password_set_at": datetime.now(timezone.utc).isoformat()}
    return json.dumps(payload, ensure_ascii=False)


def invite_payload_json():
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=Config.INVITE_TTL_HOURS)).isoformat()
    return json.dumps({"status": False, "inv_expires_at": expires_at}, ensure_ascii=False)