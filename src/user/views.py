import json
from flask import Blueprint, request, jsonify
from src.user.user import User, get_users_list
from src.auth.mail import send_invite_email
from src.auth.jwt import verify_jwt_before_request, get_jwt_identity, admin_only
from src.aliases import FieldAlias
from src.consts import UserRoles

user_bp = Blueprint('user', __name__)

# Apply jwt check to all routes of user blueprint
@user_bp.before_request
def check_jwt():
    if request.method == "OPTIONS":
        return
    return verify_jwt_before_request(request)


@user_bp.route('/layers', methods=['GET'])
def get_user_layers():
    return User.get_layers()


@user_bp.route('', methods=['GET'])
@admin_only
def users_list():
    return get_users_list()


@user_bp.route('/aliases', methods=['GET'])
def get_field_aliases():
    return User.get_field_aliases()


@user_bp.route('/aliases/save', methods=['POST'])
def save_user_aliases():
    data = json.loads(request.data)
    alias = FieldAlias()
    return alias.save(data)


@user_bp.route("/new", methods=["POST"])
@admin_only
def add_user():
    """
    Создать пользователя.
    """
    payload = request.get_json(force=True)
    required = ["login", "first_name", "last_name", "middle_name"]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    new_user = User.add(payload)

    # Отправляем письмо
    #try:
    #    send_invite_email(
    #        new_user['login'], 
    #        alias=f"{payload['first_name']} {payload['middle_name']}".strip(), 
    #        temp_password=new_user['state']['password']
    #    )
    #except Exception as e:
    #    # Почта не критична для создания — сообщим, но 201 оставим
    #    return jsonify({
    #        "id": new_user['id'],
    #        "warning": f"User created, but email not sent: {str(e)}"
    #    }), 201

    return jsonify({"id": new_user['id'], "login": new_user['login'], "alias": new_user['alias'], "role": new_user['role']}), 201


@user_bp.route("/<user_id>/invite", methods=["POST"])
@admin_only
def resend_invitation(user_id: str):
    """
    Переотправка приглашения: продлеваем inv_expires_at и шлём письмо заново.
    Можно передать {"regenerate_password": true} чтобы выдать новый временный пароль.
    """
    body = request.get_json(silent=True) or {}
    regenerate_password = bool(body.get("regenerate_password", False))

    new_user = User(user_id)

    if not new_user.exists():
        return jsonify({"error": "User not found"}), 404

    new_user.refresh_invitation_state(regenerate_password)
    userinfo = new_user.get_info()

    # Шлём письмо
    try:
        send_invite_email(
            userinfo['login'], 
            alias=userinfo['alias'], 
            temp_password=userinfo['state']['invite_token']
        )
    except Exception as e:
        return jsonify({"status": "bad", "warning": f"Invite updated, but email not sent: {str(e)}"}), 200

    return jsonify({"status": "ok"}), 200


@user_bp.route("/<user_id>", methods=["DELETE"])
@admin_only
def delete_user(user_id: str):
    """Удаление пользователя"""
    user = User(user_id)
    return user.remove()


#@user_bp.route("/<user_id>/password", methods=["POST"])
#def change_password(user_id: str):
#    self_user_id = get_jwt_identity()['id']
#    new_password = request.get_json(force=True).get("new_password")
#    user = User(user_id)
#    return user.set_password(new_password)


@user_bp.route("/<user_id>/role", methods=["POST"])
@admin_only
def change_role(user_id: str):
    """
    Изменить роль пользователя.
    JSON: {"role": "VISITOR" | "EDITOR" | "ADMIN"}
    """
    new_role = request.get_json(force=True).get("role")
    if new_role not in (UserRoles.VISITOR.value, UserRoles.EDITOR.value, UserRoles.ADMIN.value):
        return jsonify({"error": "Invalid role"}), 400

    self_user_id = get_jwt_identity()['id']
    if self_user_id == user_id:
        return jsonify({"status": "bad", "error": "Нельзя изменить роль самого себя"}), 400
    user = User(user_id)
    return user.set_role(new_role)