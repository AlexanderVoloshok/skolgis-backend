import uuid
from sqlalchemy import text
from sql_utils import execute_sql_query, execute_sql_and_commit
from utils import get_logger

logger = get_logger(__name__)


def generate_auth_code():
    guid = uuid.uuid4()
    return str(guid)


def drop_user_state(user_id: str, variable: str):
    q = text("""UPDATE skolkovo_general.users SET state = state::jsonb - '{"%s"}'::text[] WHERE id = '%s';""" % (variable, user_id))
    res = execute_sql_and_commit(q)
    return {"status": "ok"}
