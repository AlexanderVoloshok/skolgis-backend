import time
import os
import json
import traceback
from flask import Flask, request, send_from_directory, abort, jsonify, send_file
from flask_cors import CORS

import sys
sys.path.insert(1, 'd:/Angular/skolgis-backend')

from src.auth.jwt import jwt_required
from src.presentation.presentation import PresentationCreator
from src.geom_utils import compute_polygons
from src.config import Config
from src.utils import get_logger

app = Flask(__name__)
cors = CORS(app, supports_credentials=True)

app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
#app.json.sort_keys = False

logger = get_logger(__name__)

from src.auth.views import auth_bp
from src.layer.views import layers_bp
from src.user.views import user_bp


@app.before_request
def reqbeg():
    request.beg = time.time()

@app.after_request
def reqend(response):
    logger.info('end: %s %s => %s in %.5fs', request.method, request.path,
                    response.status_code, time.time() - request.beg)
    return response

@app.teardown_request
def reqtear(error = None):
    if error:
        logger.exception('error: %s %s in %.5fs:\n%s', request.method, request.path,
                         time.time() - request.beg, error)
        
@app.errorhandler(Exception)
def handle_error(e: Exception):
    """Handle errors and return a message to the client."""
    error_traceback = traceback.format_exc()
    response = {
        'status': 'bad',
        'error': error_traceback.split("\n")[-2]
    }
    logger.error(error_traceback)
    return jsonify(response), 500


@app.route(Config.APP_ROOT)
def hello():
    # do your things here
    return "Welcome to Skolkovo GIS"

@app.route(f'{Config.APP_ROOT}/geometry/merge_polygons', methods=['POST'])
@jwt_required
def compute_geometry():
    data = json.loads(request.data)['polygons']
    return compute_polygons(data[0], data[1])


@app.route(f'{Config.APP_ROOT}/file/<filename>', methods=['GET'])
def return_file(filename: str):
    if not any(filename.endswith(el) for el in Config.ALLOWED_EXPORT_FILETYPES):
        abort(404)
    try:
        directory = f'{Config.UPLOAD_FOLDER}/tmp' if os.path.exists(f'{Config.UPLOAD_FOLDER}/tmp/{filename}') else f'{Config.UPLOAD_FOLDER}/attachments'
        return send_from_directory(directory=directory, path=filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)


@app.route(f'{Config.APP_ROOT}/attachment/<filename>', methods=['GET'])
@jwt_required
def show_attachment(filename: str):
    if not any(filename.endswith(el) for el in Config.ALLOWED_ATTACHMENT_FILETYPES):
        abort(404)
    try:
        return send_from_directory(Config.UPLOAD_FOLDER + '/attachments', filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)


@app.route(f'{Config.APP_ROOT}/presentation', methods=['POST'])
@jwt_required
def create_pptx():
    project_ids: list = json.loads(request.data)['projects']
    pres = PresentationCreator(project_ids)
    buf = pres.fill_presentation()
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=f"Проект.pptx",
    )

app.register_blueprint(auth_bp, url_prefix=f'/{Config.APP_ROOT}/auth')
app.register_blueprint(layers_bp, url_prefix=f'/{Config.APP_ROOT}/layer')
app.register_blueprint(user_bp, url_prefix=f'/{Config.APP_ROOT}/user')


if __name__ == "__main__":
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.mkdir(Config.UPLOAD_FOLDER)
    if not os.path.exists(Config.UPLOAD_FOLDER + '/attachments'):
        os.mkdir(Config.UPLOAD_FOLDER + '/attachments')
    if not os.path.exists(Config.UPLOAD_FOLDER + '/tmp'):
        os.mkdir(Config.UPLOAD_FOLDER + '/tmp')
    app.run(host='0.0.0.0', port=5000, threaded=True)
