import re, os
import json
from flask import request, jsonify
from functools import wraps
from marshmallow import Schema, fields
from marshmallow.validate import Range, OneOf
from marshmallow.exceptions import ValidationError
from src.auth.jwt import get_jwt_identity
from src.config import Config
from src.consts import UserRoles

    
def validate_digits(value):
    if not str(value).isdigit():
        raise ValidationError("Значение должно содержать только цифры.")
    
def validate_json(value):
    try:
        a = json.loads(value)
    except:
        raise ValidationError("Значение должно иметь структуру JSON")


class FeaturesSchema(Schema):
    x = fields.Float(required=False)
    y = fields.Float(required=False)
    limit = fields.Integer(required=False, validate=[Range(min=1, error="invalid features limit")])
    offset = fields.Integer(required=False, validate=[Range(min=0, error="invalid features offset")])
    filter = fields.String(required=False, allow_none=True)
    filterValue = fields.String(required=False, allow_none=True)
    orderBy = fields.String(required=False, allow_none=True)
    orderFn = fields.String(
        allow_none=True,
        validate=OneOf(["ascend", "descend"], error="Invalid value for orderFn. Must be 'ascend' or 'descend'.")
)
        

def validation_chain(validators):
    """
    Декоратор для валидации запросов.
    Args: 
        validators: список валидирующих функций. Каждая функция должна принимать `request` и возвращать
                       (True, None) при успешной валидации или (False, 'сообщение об ошибке') при провале.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for validator in validators:
                if isinstance(validator, tuple):
                    # Если переданы аргументы для валидатора
                    validator_func, *validator_args = validator
                    is_valid, error_message = validator_func(request, *validator_args)
                else:
                    # Если валидатор без аргументов
                    is_valid, error_message = validator(request)

                if not is_valid:
                    return jsonify({"error": error_message}), 403

            return func(*args, **kwargs)
        return wrapper
    return decorator


def valid_id(request):
    data = json.loads(request.data) if request.method == 'POST' else {}
    if isinstance(data, dict):
        data = [data]

    for elem in data:
        oid = (elem['id'] if 'id' in elem.keys() else None) or request.view_args.get('id', -1)
        try:
            oid = int(oid)
        except ValueError:
            return False, f"invalid id format: {oid} of type {type(oid)}"
        if oid < 0:
            return False, f"invalid id format: {oid} of type {type(oid)}"
    return True, None

def valid_symbols_in_name(request):
    data = json.loads(request.data)
    name = data['name'] or request.view_args.get('layer_name', None) or request.view_args.get('group_name', None)
    valid_pattern = re.compile(r'''^[a-zA-Zа-яёА-ЯЁ0-9 -.,:;_()'"]*$''')
    if not valid_pattern.match(name):
        return False, "name contains invalid characters"
    elif len(name) < 1:
        return False, "name must be at least 1 character long"
    elif name.strip() == '':
        return False, "name cannot contain only whitespaces"
    return True, None

def valid_file(request):
    size = Config.MAX_CONTENT_LENGTH
    for f in request.files.items():
        filename = f[1].filename
        f[1].seek(0, os.SEEK_END)
        file_size = f[1].tell()
        f[1].seek(0)
        if file_size/(size **3) > 1:
            return False, f'Разрешено загружать файлы не более {size} МБ'
        if not any([filename.endswith(el) for el in Config.ALLOWED_ATTACHMENT_FILETYPES]):
            return False, f'Недопустимый тип файла. Разрешено загружать только {", ".join(Config.ALLOWED_ATTACHMENT_FILETYPES)}'
    return True, None

def can_edit_layer(request):
    claims = get_jwt_identity()
    role = claims.get("role")
    if role == UserRoles.VISITOR.value:
        return False, 'Нельзя редактировать этот слой'
    return True, None