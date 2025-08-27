import time
import os
import traceback
from flask import Flask, request, send_from_directory, abort, jsonify, send_file
from flask_cors import CORS

from presentation import pptx_from_image
from config import Config
from utils import get_logger

app = Flask(__name__)
cors = CORS(app, supports_credentials=True)

app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

logger = get_logger(__name__)


from layer.views import layers_bp
from user.views import user_bp

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

#TODO: генерить файл и отдавать можно на лету без сохранения на диск
@app.route(f'{Config.APP_ROOT}/file/<filename>', methods=['GET'])
def return_file(filename: str):
    if not any(filename.endswith(el) for el in Config.ALLOWED_EXPORT_FILETYPES):
        abort(404)
    try:
        return send_from_directory(directory=Config.UPLOAD_FOLDER, path=filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)

#TODO: разные фичи, слои и пользователи могут содержать вложения с одинаковыми именами. Это надо предусмотреть.
@app.route(f'{Config.APP_ROOT}/attachment/<filename>', methods=['GET'])
def show_attachment(filename: str):
    if not any(filename.endswith(el) for el in Config.ALLOWED_ATTACHMENT_FILETYPES):
        abort(404)
    try:
        return send_from_directory(Config.UPLOAD_FOLDER + '/attachments', filename, as_attachment=False)
    except FileNotFoundError:
        abort(404)


@app.route(f'{Config.APP_ROOT}/pptx', methods=['POST'])
def create_pptx():
    # Проверяем, что файл есть
    if 'image' not in request.files:
        return {"error": "No image uploaded"}, 400

    image_file = request.files['image']

    pptx_io = pptx_from_image(image_file)

    return send_file(
        pptx_io,
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        as_attachment=True,
        download_name='Карта.pptx'
    )

app.register_blueprint(layers_bp, url_prefix=f'/{Config.APP_ROOT}/layer')
app.register_blueprint(user_bp, url_prefix=f'/{Config.APP_ROOT}/user')


if __name__ == "__main__":
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.mkdir(Config.UPLOAD_FOLDER)
    ##if not os.path.exists(Config.UPLOAD_FOLDER + '/sld'):
    ##    os.mkdir(Config.UPLOAD_FOLDER + '/sld')
    if not os.path.exists(Config.UPLOAD_FOLDER + '/attachments'):
        os.mkdir(Config.UPLOAD_FOLDER + '/attachments')
    app.run(host='0.0.0.0', port=5000, threaded=True)
