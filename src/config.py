import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
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
    ALLOWED_UPLOAD_FILETYPES = ('geojson', 'gpkg', 'kml', 'sld',)
    ALLOWED_EXPORT_FILETYPES = ('geojson', 'gpkg', 'kml', 'xlsx', 'pptx')
    ALLOWED_ATTACHMENT_FILETYPES = ('xml', 'pdf', 'docx', 'txt',
      'png', 'jpg', 'jpeg','gif','webp','tif', 'tiff'
      'zip', 'rar', '7z','zip')
    APP_ROOT = '/api_skolkovo'
    SECRET_KEY = os.getenv('SECRET_KEY')
    UPLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '/files'

    GEOSERVER_ROOT = os.getenv('PROXY_BASE_URL', 'http://89.223.68.75/geoserver')
    GEOSERVER_USER = os.getenv('GEOSERVER_ADMIN_USER')
    GEOSERVER_PWD = os.getenv('GEOSERVER_ADMIN_PASSWORD')
    GEOSERVER_WORKSPACE = os.getenv('GEOSERVER_WORKSPACE')
    GEOSERVER_STORE_NAME = os.getenv('GEOSERVER_STORE_NAME')

    #TODO: вынести sql-схемы в константы

    #TILES_DIR = os.path.dirname(os.path.realpath(__file__)) + '/assets/3dtiles'
    
    ENCRYPT_ALG = "HS256"
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024 * 1024 # 4 GB

    SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    MAIL_FROM = os.getenv("MAIL_FROM", "no-reply@skolgis.com")
    PROJECT_NAME = os.getenv("PROJECT_NAME", "Skolkovo GIS")
    INVITE_TTL_HOURS = int(os.getenv("INVITE_TTL_HOURS", "72"))  # срок жизни приглашения