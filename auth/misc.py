import json
import uuid
import requests
from sqlalchemy import text
from flask import redirect, make_response, jsonify
from user.user import User
from sql_utils import execute_sql_query, execute_sql_and_commit
from config import Config
from utils import get_logger

logger = get_logger(__name__)


def run_auth_flow(post_data: dict):
    step = 1
    auth_root = f"{Config.ENV_PREFIX}.{Config.AUTH_ROOT}"
    prefix = 'auth'
    r = requests.post(f'https://{prefix}{auth_root}/token', data=post_data)
    if r.status_code == 200:
        resp = r.json()
        token = resp['access_token']
        #userinfo
        logger.info(f"{resp['token_type']} {token}")
        r = requests.get(f'https://api{auth_root}/userinfo', headers={'Authorization': f"{resp['token_type']} {token}"})
        step += 1
        if r.status_code == 200:
            user_info = r.json()
            #with open('user_info_test.json', 'w', encoding="utf-8") as out:
            #    json.dump(user_info, out, ensure_ascii=False, indent = 4)
            
            try:
                User.add(user_info)
            except PermissionError:
                return jsonify("Доступ к модулю СколГИС в данный момент отсутствует. Для решения этой проблемы, пожалуйста, обратитесь в техническую поддержку."), 403
            
            code = generate_auth_code()
            id_code = save_auth_code(user_info['id'], code)
            return make_response(redirect(f"{Config.DEV_ROOT}/skolgis-frontend/#/success?code={code}", code=302))
        
    return f'Auth flow error on step {step}' + r.text, r.status_code


def generate_auth_code():
    guid = uuid.uuid4()
    return str(guid)


def save_auth_code(user_id: str, code: uuid.UUID):
    stmt = text("""               
        UPDATE skolkovo_general.users
        SET state = COALESCE(state::jsonb, '{}') || '{"auth_code": "%s"}'::jsonb
        WHERE id = '%s'
        RETURNING id;
    """ % (code, user_id))
    res = execute_sql_and_commit(stmt)
    return {"status": "ok", "id": res.scalar()}


def get_userid_by_auth_code(code: uuid.UUID):
    q = text("SELECT id from skolkovo_general.users where state ->> 'auth_code' = '%s'" % code)
    userid = execute_sql_query(q).scalar()       
    return userid


def drop_user_state(user_id: str, variable: str):
    q = text("""UPDATE skolkovo_general.users SET state = state::jsonb - '{"%s"}'::text[] WHERE id = '%s';""" % (variable, user_id))
    res = execute_sql_and_commit(q)
    return {"status": "ok"}


def get_auth_url(auth_type: str):
    prefix = 'secure' if auth_type == 'secure' else 'auth'
    client_id = Config.SECURE_CLIENT_ID if auth_type == 'secure' else Config.ESIA_CLIENT_ID
    redirectUri = f"{Config.DEV_ROOT}{Config.APP_ROOT}/auth/{auth_type}"
    state = '4323cf949072d4d0f0619e67e65cfc29'
    return f"https://{prefix}{Config.ENV_PREFIX}.{Config.AUTH_ROOT}/authorize?response_type=code&state={state}&redirect_uri={redirectUri}&client_id={client_id}"