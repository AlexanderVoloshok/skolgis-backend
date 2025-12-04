import json
import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, MultiPolygon, MultiLineString, Point
from shapely.ops import transform
from src.sql_utils import read_sql

project_3857 = CRS("EPSG:3857")
project_4326 = CRS("EPSG:4326")


def get_geom_type(layer_name: str):
    q = """SELECT type FROM geometry_columns
    WHERE f_table_schema = 'skolkovo_layers' AND f_table_name = '%s' and f_geometry_column = 'geom'
    """ % layer_name
    df = read_sql(q)
    return df.loc[0, 'type'] if df.loc[0, 'type'] != 'GEOMETRY' else 'POLYGON'


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


def compute_polygons(polygon1: list, polygon2: list):
    a_df = gpd.GeoDataFrame.from_features([polygon1])
    b_df = gpd.GeoDataFrame.from_features([polygon2])
    polygon1 = a_df.loc[0].geometry
    polygon2 = b_df.loc[0].geometry
    # Если один полигон полностью внутри другого
    if polygon1.contains(polygon2):
        # Если polygon2 внутри polygon1, создаем отверстие в polygon1
        geom = polygon1.difference(polygon2)
    elif polygon2.contains(polygon1):
        # Если polygon1 внутри polygon2, создаем отверстие в polygon2
        geom = polygon2.difference(polygon1)
    
    # Если полигоны пересекаются
    elif polygon1.intersects(polygon2):
        # Если пересекаются, объединяем их в один полигон
        geom = polygon1.union(polygon2)
    else:
        # Если они не пересекаются и не вложены друг в друга, создаем мультиполигон
        geom = polygon1.union(polygon2)

    if isinstance(geom, MultiPolygon):
        feature = gpd.GeoDataFrame([{'geometry': geom}])
    else:
        feature = gpd.GeoDataFrame([{'geometry': MultiPolygon([geom])}])
    return json.loads(feature.to_json())