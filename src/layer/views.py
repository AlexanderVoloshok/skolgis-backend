import json
from flask import Blueprint, request
from src.auth.jwt import verify_jwt_before_request
from src.layer.layer import Layer
from src.layer.files import attatch_file, remove_file
from src.user.user import User
from src.config import Config
from src.validation import FeaturesSchema, valid_id, valid_file, validation_chain, can_edit_layer
from src.consts import RESERVED_WORDS, PROTECTED_COLUMN_NAMES_PROJECTS, PROTECTED_COLUMN_NAMES_PARCELS

layers_bp = Blueprint('layer', __name__)

# Apply jwt check to all routes of layer blueprint
@layers_bp.before_request
def check_jwt():
    if request.method == "OPTIONS":
        return
    return verify_jwt_before_request(request)


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
    ids = request.args.get('ids', '').split(";")
    filters = request.args.get('filter', [])
    user = User()
    layer = Layer(layer_name, user)
    filename = layer.export(file_type, filters=filters, feature_ids=ids)
    if filename is None:
        return "Файл пустой", 401
    return {'status': 'ok', "url": filename}


@layers_bp.route('/<layer_name>/edit', methods=['POST'])
@validation_chain([valid_id, can_edit_layer])
def edit_layer(layer_name: str):
    is_new_project = request.args.get('is_new_project', 'false')
    data = json.loads(request.data)
    #Если появился новый проект - добавляем его как новую строку. плюс, апдейтим project_id здания
    if is_new_project == 'true' and layer_name == "main_buildings":
        projectAttrsLayer = Layer("projects_attrs")
        new_feature = projectAttrsLayer.add_feature({"name": None})
        data["project_id"] = new_feature['id']

    layer = Layer(layer_name)
    if isinstance(data, list):
        for elem in data:
            layer.set_feature_attrs(elem)
        return {"status": "ok", "layer": layer_name}
    return layer.set_feature_attrs(data)


@layers_bp.route('/<layer_name>/add', methods=['POST'])
@validation_chain([can_edit_layer])
def add_feature(layer_name: str):
    data = json.loads(request.data)
    layer = Layer(layer_name)
    return layer.add_feature(data)


@layers_bp.route('/<layer_name>/delete', methods=['POST'])
@validation_chain([valid_id, can_edit_layer])
def delete_feature(layer_name: str):
    data = json.loads(request.data)
    if layer_name == 'projects_full':
        layer_name = "projects_attrs"

        # Если удаляется проект - у зданий должен учищаться project_id
        # TODO: возможно, лучше извлекать id зданий запросом из БД
        buildings_layer = Layer("main_buildings")
        if "buildingIds" in data.keys():
            for fid in data["buildingIds"]:
                buildings_layer.set_feature_attrs({'id': fid, 'project_id': None})

    layer = Layer(layer_name)
    return layer.delete_feature(data['id'])


@layers_bp.route('/<layer_name>/fields/<field_name>/values', methods=['GET'])
def get_field_values(layer_name: str, field_name: str):
    layer = Layer(layer_name)
    return layer.get_field_values(field_name)


@layers_bp.route('/<layer_name>/fields/add', methods=['POST'])
@validation_chain([can_edit_layer])
def add_field(layer_name: str):
    data = json.loads(request.data)
    if data['name'] in RESERVED_WORDS:
        return {"error": f"Field {data['name']} is reserved and cannot be added"}, 403
    layer = Layer(layer_name)
    return layer.add_field(data['name'], data['type'])


@layers_bp.route('/<layer_name>/fields/delete', methods=['POST'])
@validation_chain([can_edit_layer])
def delete_field(layer_name: str):
    data = json.loads(request.data)
    layer = Layer(layer_name)
    if data['name'] not in layer.columns.keys():
        return {"error": f"Поля {data['name']} не существует"}, 403
    #TODO: PROTECTED_COLUMN_NAMES определять запросом к бд
    if data['name'] in ('id', 'project_id', 'geom', 'geometry'):
        return {"error": f"Поле {data['name']} защищённое. Его нельзя удалить"}, 403
    if (layer_name == 'projects_attrs' and data['name'] in PROTECTED_COLUMN_NAMES_PROJECTS):
        return {"error": f"Поле {data['name']} защищённое. Его нельзя удалить"}, 403
    elif (layer_name == 'layer_32' and data['name'] in PROTECTED_COLUMN_NAMES_PARCELS):
        return {"error": f"Поле {data['name']} защищённое. Его нельзя удалить"}, 403
    
    return layer.delete_field(data['name'])


@layers_bp.route('/<layer_name>/<fid>/file/attatch', methods=['POST'])
@validation_chain([valid_file])
def attatch_files(layer_name: str, fid: int):
    # проверяем, нет ли уже файла с таким именем
    #сохраняем файл на  диск
    #добавляем имя файла в бд

    attachments = []
    for f in request.files.items():
        if not f[1].filename:
            continue
        file = attatch_file(layer_name, fid, f[1])
        attachments.append(file)

    return {
        "status": "ok",
        "files": attachments
    }, 201


@layers_bp.route('/<layer_name>/<fid>/file/<filename>/remove', methods=['POST'])
@validation_chain([valid_file, can_edit_layer])
def remove_attatchment(layer_name: str, fid: int, filename: str):
    result = remove_file(layer_name, fid, filename)
    return result