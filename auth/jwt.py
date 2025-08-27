import jwt
from datetime import datetime, timezone, timedelta
from flask import request, jsonify, Request
from jwt import ExpiredSignatureError, InvalidTokenError
from config import Config
from consts import UserRoles


def create_access_token(identity, role: UserRoles, expires_delta=timedelta(1*3600*24)):
    payload = {
        "id": identity,
        "role": role,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.ENCRYPT_ALG)


def check_token_validity(token: str):
    try:
        # Decode the token
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.ENCRYPT_ALG])
        return {"valid": True, "payload": payload}
    except ExpiredSignatureError:
        return {"valid": False, "error": "Token has expired"}
    except InvalidTokenError:
        return {"valid": False, "error": "Invalid token"}
    

def jwt_required(f):
    def wrapper(*args, **kwargs):
        verify_jwt_before_request(request)
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__  # Preserve function name
    return wrapper


def verify_jwt_before_request(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:# or not auth_header.startswith("Bearer "):
        return jsonify({"status":"bad", "error": "Token is missing or invalid"}), 401

    ##token = auth_header.split(" ")[1]  # Extract the token
    validate_result = check_token_validity(auth_header)
    if not validate_result['valid']:
        return jsonify(validate_result), 401
    

def get_jwt_identity():
    token = request.headers.get("Authorization")
    if token is None:
        return token
    decode = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.ENCRYPT_ALG])
    return decode