import json
from flask import Blueprint, request
from auth.misc import drop_user_state, get_userid_by_auth_code
from auth.jwt import check_token_validity, get_jwt_identity, jwt_required
from user.user import User
from utils import get_logger

logger = get_logger(__name__)


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/logout', methods=['GET'])
@jwt_required
def logout():
    user_id = get_jwt_identity()
    if user_id is None:
        return {"status": "ok"}
    return drop_user_state(user_id, 'access_token')


@auth_bp.route('/check', methods=['GET'])
def check_auth():
    token = request.headers.get('Authorization')
    token_check = check_token_validity(token)
    if not token_check['valid']:
        return {"status": "bad"}
    user = User(token_check['payload']['id'])
    return {
        "status": "ok" if user.exists(token) else "bad",
    }


@auth_bp.route('/userinfo', methods=['GET'])
def return_userinfo():
    user_id = get_jwt_identity()
    print('user_id', user_id)
    user = User(user_id)
    new_token = user.generate_auth_token()
    userinfo = user.get_info()
    return {
        'status': 'ok',
        'user_info': {
            "login": userinfo['login'],
            "alias": userinfo['alias'],
            "role": userinfo['role']
        },
        'access_token': new_token
    }