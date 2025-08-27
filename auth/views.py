import json
from flask import Blueprint, request
from config import Config
from auth.misc import run_auth_flow, drop_user_state, get_userid_by_auth_code, get_auth_url
from auth.jwt import check_token_validity, get_jwt_identity, jwt_required
from user.user import User
from utils import get_logger

logger = get_logger(__name__)


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/esia', methods=['GET'])
def auth_esia():
    post_data = {
        "state": request.args.get('state'),
        "code": request.args.get('code'),
        "grant_type": "authorization_code",
        "client_id": Config.ESIA_CLIENT_ID,
        "client_secret": Config.AUTH_SECRET,
        "scope": "openid",
        "redirect_uri": f"{Config.DEV_ROOT}{Config.APP_ROOT}/auth/esia"
    }
    res = run_auth_flow(post_data)
    return res


@auth_bp.route('/logout', methods=['GET'])
@jwt_required
def logout():
    user_id = get_jwt_identity()
    if user_id is None:
        return {"status": "ok"}
    return drop_user_state(user_id, 'access_token')


@auth_bp.route('/check', methods=['GET'])
def check_auth():
    auth_type = request.args.get('auth_type')
    token = request.headers.get('Authorization')
    auth_url = get_auth_url(auth_type)

    token_check = check_token_validity(token)
    if not token_check['valid']:
        return {"status": "bad", "url": auth_url}
    user = User(token_check['payload']['id'])
    permissions = json.loads(user.get_info()['permissions'])
    logout_url = f"https://{'secure' if auth_type == 'secure' else 'auth'}{Config.ENV_PREFIX}.{Config.AUTH_ROOT}"
    return {
        "status": "ok" if user.exists(token) and any(permissions.keys()) else "bad",
        "url": auth_url,
        "logout_url": logout_url
    }


@auth_bp.route('/userinfo', methods=['GET'])
def return_userinfo():
    code = request.args.get('code')
    userid = get_userid_by_auth_code(code)
    if not userid:
        return {"status": "bad", "error": "invalid auth code"}
    drop_user_state(userid, 'auth_code')
    user = User(userid)
    new_token = user.generate_auth_token()
    return {
        'status': 'ok',
        'user_info': user.get_info(),
        'access_token': new_token
    }