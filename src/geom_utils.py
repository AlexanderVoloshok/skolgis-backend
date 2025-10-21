from pyproj import CRS, Transformer
from shapely.geometry import Polygon, MultiPolygon, MultiLineString, Point
from shapely.ops import transform
from sql_utils import read_sql

project_3857 = CRS("EPSG:3857")
project_4326 = CRS("EPSG:4326")


def get_geom_type(layer_name: str):
    q = """SELECT type FROM geometry_columns
    WHERE f_table_schema = 'skolkovo_layers' AND f_table_name = '%s' and f_geometry_column = 'geom'
    """ % layer_name
    df = read_sql(q)
    return df.loc[0, 'type']


def enforce_geom_type(geom):
    if geom.geom_type == 'Polygon':
        return MultiPolygon([geom])
    elif geom.geom_type == 'LineString':
        return MultiLineString([geom])
    return geom


def parse_geometry(data, geom_type):
    if geom_type in ('POLYGON', 'MULTIPOLYGON'):
        if isinstance(data[0][0][0], (float)):
            polygons = [Polygon(shell=data[0], holes=data[1:] if len(data) > 1 else [])]
        elif isinstance(data[0][0], (list, tuple)):  # Проверяем тип данных
            # Это мультиполигон
            polygons = [Polygon(shell=poly[0], holes=poly[1:] if len(poly) > 1 else []) for poly in data]
        else:
            # Это полигон
            polygons = [Polygon(shell=data[0], holes=data[1:] if len(data) > 1 else [])]
        return MultiPolygon(polygons)
    elif geom_type in ('LINESTRING', 'MULTILINESTRING'):
        if isinstance(data[0][0], (list, tuple)):
            return MultiLineString(data)
        else:
            return MultiLineString([data])
    else:
        return Point(data)


def reproject_to_wgs(geometry):
    transformer = Transformer.from_crs(project_3857, project_4326, always_xy=True)
    return transform(lambda x, y: transformer.transform(x, y), geometry)
