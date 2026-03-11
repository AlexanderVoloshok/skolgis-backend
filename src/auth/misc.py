import json
import hashlib
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from src.sql_utils import execute_sql_and_commit
from src.config import Config
from src.utils import get_logger

logger = get_logger(__name__)


def drop_user_state(user_id: str, variable: str):
    q = text("""UPDATE skolkovo_general.users SET state = state::jsonb - '{"%s"}'::text[] WHERE id = '%s';""" % (variable, user_id))
    res = execute_sql_and_commit(q)
    return {"status": "ok"}

def invite_payload_json():
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=Config.INVITE_TTL_HOURS)).isoformat()
    return json.dumps({"status": False, "inv_expires_at": expires_at}, ensure_ascii=False)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()