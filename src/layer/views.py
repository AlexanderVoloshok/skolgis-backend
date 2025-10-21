import json
from flask import Blueprint, request, jsonify
from .layer import Layer
from .files import attatch_file, remove_file
from user.user import User
from config import Config
from validation import FeaturesSchema, valid_id, valid_file, validation_chain


layers_bp = Blueprint('layer', __name__)


@layers_bp.route('/<layer_name>/features', methods=['GET'])
def get_layer_features(layer_name: str):
    schema = FeaturesSchema()
    errors = schema.validate(request.args)
    if errors:
        return errors, 403

    x = request.args.get('x')
    y = request.args.get('y')
    layer = Layer(layer_name)
    if x is not None and y is not None:
        return layer.get_feature_at_point(x, y)
    
    return layer.get_features(request.args)


@layers_bp.route('/<layer_name>/features', methods=['POST'])
def get_features_in_bounds(layer_name: str):
    bounds = json.loads(request.data)['bounds']
    are_all_numbers = all([isinstance(value, (int, float)) for value in bounds])
    if not are_all_numbers:
        return {'status': 'bad', 'error': 'invalid bounds'}, 403
    layer = Layer(layer_name)
    return layer.get_features_in_bounds(bounds)
    

@layers_bp.route('/upload', methods=['POST'])
@validation_chain([valid_file])
def upload_layer():
    layers_type_id = 1 #request.args.get('layers_type_id')

    for f in request.files.items():
        filename = f[1].filename       
        data = {
            'source': filename,
            'alias': f'{filename.split(".")[0]}', 
            'layers_type_id': int(layers_type_id)
        }
        upload_result = Layer.upload(f[1], data)

    return upload_result


@layers_bp.route('/<layer_name>/extent', methods=['GET'])
def get_layer_extent(layer_name: str):
    user = User()
    layer = Layer(layer_name, user)
    extent = layer.get_extent()
    return {'box': extent}


@layers_bp.route('/<layer_name>/export', methods=['GET'])
def export_layer(layer_name: str):
    file_type = request.args.get('format', None)
    if file_type not in Config.ALLOWED_EXPORT_FILETYPES:
        return {'status': 'bad', 'error': 'Недопустимое расширение файла'}, 403
    user = User()
    layer = Layer(layer_name, user)
    filename = layer.export(file_type)
    if filename is None:
        return "Файл пустой", 401
    return {'status': 'ok', "url": filename}


@layers_bp.route('/<layer_name>/edit', methods=['POST'])
@validation_chain([valid_id])
def edit_layer(layer_name: str):
    data = json.loads(request.data)
    layer = Layer(layer_name)
    return layer.set_feature_attrs(data)


@layers_bp.route('/<layer_name>/add', methods=['POST'])
def add_feature(layer_name: str):
    data = json.loads(request.data)
    layer = Layer(layer_name)
    return layer.add_feature(data)


@layers_bp.route('/<layer_name>/delete', methods=['POST'])
@validation_chain([valid_id])
def delete_feature(layer_name: str):
    data = json.loads(request.data)
    layer = Layer(layer_name)
    return layer.delete_feature(data['id'])


@layers_bp.route('/<layer_name>/<fid>/file/attatch', methods=['POST'])
@validation_chain([valid_file, valid_id])
def attatch_file(layer_name: str, fid: int):
    files = json.loads(request.data)
    # проверяем, нет ли уже файла с таким именем
    #сохраняем файл на  диск
    #добавляем имя файла в бд

    attachments = []
    for f in files:
        if not f.filename:
            continue
        file = attatch_file(layer_name, fid, f)
        attachments.append(file)

    return jsonify(attachments), 201


@layers_bp.route('/<layer_name>/<fid>/file/<filename>/remove', methods=['POST'])
@validation_chain([valid_file, valid_id])
def remove_attatchment(layer_name: str, fid: int, filename: str):
    result = remove_file(layer_name, fid, filename)
    return result, 201