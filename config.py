import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData

env_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env')
load_dotenv(env_path)
db = os.getenv('DB')
host = os.getenv('HOST')
port = os.getenv('PORT')
user = os.getenv('USER')
pw = os.getenv('PW')
DB_URI = f"postgresql://{user}:{pw}@{host}:{port}/{db}"

ENGINE = create_engine(DB_URI, pool_size=30)
MAIN_META = MetaData(schema="skolkovo_general")
MAIN_META.reflect(bind=ENGINE)
LAYERS_META = MetaData(schema="skolkovo_layers")
LAYERS_META.reflect(bind=ENGINE)


class Config():
    ALLOWED_UPLOAD_FILETYPES = ('geojson', 'gpkg', 'kml', 'sld')
    ALLOWED_EXPORT_FILETYPES = ('geojson', 'gpkg', 'kml', 'xlsx', 'pptx')
    ALLOWED_ATTACHMENT_FILETYPES = ('.png', '.jpeg', '.pdf', 'xml')
    APP_ROOT = '/api_skolkovo'
    SECRET_KEY = os.getenv('SECRET_KEY')
    UPLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '/files'

    #TODO: вынести sql-схемы в константы

    TILES_DIR = os.path.dirname(os.path.realpath(__file__)) + '/assets/3dtiles'
    
    ENCRYPT_ALG = "HS256"
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024 * 1024 # 4 GB