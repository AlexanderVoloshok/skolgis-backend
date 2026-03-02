from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from src.config import Config
from src.auth.misc import drop_user_state
from src.auth.jwt import check_token_validity, get_jwt_identity, jwt_required
from src.user.user import User
from src.utils import get_logger

logger = get_logger(__name__)


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"message": "email and password are required"}), 400

    user = User.authenticate(email=email, password=password)
    if not user:
        # не палим, что именно неверно
        return jsonify({"message": "invalid credentials"}), 401
    
    access_token = user.generate_auth_token()
    return jsonify({
        "access_token": access_token, 
        "expires_in": str(datetime.now(timezone.utc) + Config.JWT_LIFETIME),
        "userinfo": user.get_info()
    }), 200


@auth_bp.route('/logout', methods=['GET'])
@jwt_required
def logout():
    user_id = get_jwt_identity()
    if user_id is None:
        return {"status": "ok"}
    return drop_user_state(user_id['id'], 'access_token')


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
@jwt_required
def return_userinfo():
    user_id = get_jwt_identity()
    if user_id is None:
        return {}
    user = User(user_id['id'])
    userinfo = user.get_info()
    return {
        "login": userinfo['login'],
        "alias": userinfo['alias'],
        "role": userinfo['role']
    }