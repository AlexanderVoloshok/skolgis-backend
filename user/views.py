from flask import Blueprint
from .user import User

user_bp = Blueprint('user', __name__)


@user_bp.route('/layers', methods=['GET'])
def get_user_layers():
    return User.get_layers()
