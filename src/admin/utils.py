from flask import request, jsonify
from src.consts import UserRoles
from src.auth.jwt import get_jwt_identity


def admin_only(fn):
    """Пропускает только если в токене роль администратора"""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth.split(" ", 1)[1].strip()
        try:
            claims = get_jwt_identity()  # должен вернуть словарь с 'role'
        except Exception:
            return jsonify({"error": "Invalid token"}), 401

        role = claims.get("role")
        if role != UserRoles.ADMIN:
            return jsonify({"error": "Admin role required"}), 403
        # Можно добавить user_id из токена в request.context при необходимости
        return fn(*args, **kwargs)
    return wrapper