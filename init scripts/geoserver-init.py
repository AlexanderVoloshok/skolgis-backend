from src.config import db, host, port, user, pw
from src.layer.geoserver import geo
from geo.Geoserver import GeoserverException
from utils import get_logger


logger = get_logger('__main__')

try:
    geo.create_workspace(workspace='skolgis')
except GeoserverException:
    logger.info('geoserver workspace not created')

try:
    geo.create_featurestore(store_name='skolgis_postgis', workspace='skolgis', db=db, host=host, port=port, schema="geo",  pg_user=user, pg_password=pw)
except GeoserverException:
    logger.info('geoserver featurestore not created')