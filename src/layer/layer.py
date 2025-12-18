import json
import geopandas as gpd
import fiona
from datetime import datetime, time, date
from werkzeug.datastructures import FileStorage
from typing import Union
from sqlalchemy import select, text, exc, sql, func, literal, Column
from geoalchemy2.shape import from_shape
from geoalchemy2 import Geometry
from src.aliases import FieldAlias
from src.config import Config, ENGINE, MAIN_META, LAYERS_META
from src.geom_utils import parse_geometry, reproject_to_wgs, get_geom_type, enforce_geom_type
from src.sql_utils import read_sql, read_postgis, execute_sql_query, execute_sql_and_commit
from src.layer.utils import parse_order, build_where, resolve_type
from src.layer.geoserver import clear_geoserver_cache
from src.layer.kml import parse_kml
import src.consts as consts
from src.utils import get_logger


logger = get_logger(__name__)

fiona.drvsupport.supported_drivers['kml'] = 'rw'
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['libkml'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

DEFAULT_FEATURES_LIMIT = 5000
MAX_FEATURES_LIMIT = 10000

class LayerNotExistException(Exception):
    pass


class Layer():
    layers_table = MAIN_META.tables['skolkovo_general.layers']

    def __init__(self, name: str, owner=None) -> None:
        self.name = name
        self.props = self._get_layer_props(name)
        self.owner = owner
        if 'skolkovo_layers.' + self.name in LAYERS_META.tables.keys():
            self.layer_table = LAYERS_META.tables['skolkovo_layers.' + self.name]
            self.columns = {column.name: str(column.type) for column in self.layer_table.columns}
            self.geom_type = get_geom_type(name)
            self.layer_table.c.geom.type = Geometry(self.geom_type, srid=4326)
        else:
            pass
    

    def get_features(self, options: dict):
        """Возвращает слой в формате geojson

        Args:
            options (dict): ограничение по выдаче

        Returns:
            json: 
        """

        filters_raw = options.get("filter")
        limit_raw = options.get("limit", type=int)
        offset_raw = options.get("offset", type=int)
        order_raw = options.get("order")

        ALLOWED_COLUMNS = {c.name: c for c in self.layer_table.columns}
        GEOM_COL = sql.literal_column("geom").label("geom")
        CALC_AREA_COL = sql.literal_column(
            "round((ST_Area(ST_Transform(ST_MakeValid(geom), 4326)::geography)/ 10000)::numeric, 3)"
        ).label("calc_area")
        
        where_expr = build_where(filters_raw, ALLOWED_COLUMNS)

        limit = DEFAULT_FEATURES_LIMIT if not limit_raw or limit_raw <= 0 else min(limit_raw, MAX_FEATURES_LIMIT)
        offset = 0 if not offset_raw or offset_raw < 0 else offset_raw

        order_items = parse_order(order_raw)

        # Основные колонки + calc_area.
        select_cols = [
            col for col in self.layer_table.c  if col.name in self.columns and col.name != 'geom'
        ]
        select_cols.append(GEOM_COL)
        select_cols.append(CALC_AREA_COL)

        stmt = select(*select_cols).where(where_expr)
        filtered_features = execute_sql_query(
            select(func.count(literal(1))).select_from(stmt)
        ).scalar_one()
        for name, direction in order_items:
            col = self.layer_table.c[name]
            stmt = stmt.order_by(col.desc() if direction == "desc" else col.asc())
        stmt = stmt.limit(limit).offset(offset)

        # Отдельно total
        count_stmt = select(func.count(literal(1))).select_from(self.layer_table)
        total = execute_sql_query(count_stmt).scalar_one()

        # Компилируем SELECT в строку с ЛИТЕРАЛИЗОВАННЫМИ значениями (безопасно: всё биндилось SQLAlchemy)
        features = read_postgis(stmt)
        result = json.loads(features.to_json(default=str))
        result["total"] = int(total)
        result['filtered'] = filtered_features

        return result
       

    def get_features_in_bounds(self, bounds: list):
        bounds = ", ".join([str(i) for i in bounds])
        q = """
            WITH bbox AS (
                SELECT ST_MakeEnvelope(%s, 3857) AS geom
            ),

            expanded_bbox AS (
                SELECT 
                    ST_Expand(geom, 0.2 * LEAST(
                        ST_XMax(geom) - ST_XMin(geom), -- ширина
                        ST_YMax(geom) - ST_YMin(geom)  -- высота
                    )) AS geom
                FROM bbox
            ),

            bbox_4326 AS (
                SELECT ST_Transform(geom, 4326) AS geom FROM expanded_bbox
            )

            SELECT l.* FROM skolkovo_layers.%s l
            JOIN bbox_4326 b ON ST_Intersects(l.geom, b.geom)
        """ % (bounds, self.name)
        gdf = read_postgis(q)
        for col in [c for c in gdf.columns if c not in ('geom')]:
            fields_might_be_datetime = gdf[col].map(lambda v: isinstance(v, (time, datetime, date))).fillna(False)
            if fields_might_be_datetime.any():
                gdf[col] = gdf[col].astype(str)
        return json.loads(gdf.to_json())


    def get_feature_at_point(self, x: float, y: float):
        calc_area = ', round((ST_Area(ST_Transform(ST_MakeValid(geom), 4326)::geography)/ 10000)::numeric,  3) as calc_area' 
        not_polygon = self.geom_type not in ('POLYGON', 'MULTIPOLYGON')
        q = f"""
            SELECT * {'' if not_polygon else calc_area} FROM skolkovo_layers.{self.name} lyr
            WHERE ST_DWithin(
                st_transform(ST_GeomFromText('POINT({x} {y})', 3857), 4326)
            , lyr.geom, {0.0001 if not_polygon else 0})
        """
        feature = read_postgis(q)
        if len(feature) == 0:
            return {"type": "FeatureCollection", "features": [], 'files': []}
        fid = feature.loc[0, 'id']
        files = read_sql(f"""
            select * from skolkovo_general.file_attachments where layer = '{self.name}' and fid = {fid}
        """)
        feature = json.loads(feature.to_json(default=str))
        feature['files'] = json.loads(files.to_json(orient="records"))
        return feature


    def get_extent(self, crs:int=3857):
        """Возвращает экстент слоя"""

        q = text(f"""
            SELECT ST_Extent(ST_Transform(geom, {crs})) from (     
                SELECT ST_SetSRID(ST_Extent(geom), 4326) as geom FROM skolkovo_layers.{self.name}
                where st_isvalid(geom)
            )a
        """)
        result = execute_sql_query(q)
        row = result.scalar()
        return row


    def get_alias(self):
        cols = self.layers_table.c
        q = select(cols.alias, cols.layers_type_id).where(cols.table_name == self.name)
        rows = execute_sql_query(q).fetchall()
        return rows[0]
    

    def set_attrs(self, attrs: dict):
        """Обновляет свойства слоя в таблице skolkovo_general.layers

        Args:
            attrs (dict): словарь с атрибутами на обновление

        Returns:
            int: id слоя
        """

        attrs = {k:v for k,v in attrs.items() if k not in ('id')}
        q = self.layers_table.update().returning(self.layers_table.c.table_name)\
            .where(self.layers_table.c.table_name == self.name)\
            .values(attrs)
        cursor = execute_sql_and_commit(q)
        return {"status": "ok", "layer": self.name }
    

    def set_feature_attrs(self, attrs: dict):
        """Обновляет свойства фичи в слое

        Args:
            attrs (dict): новые атирбуты фичи, в т.ч. её id

        Returns:
            int: id фичи
        """
        #TODO: вынести кусок обработки геометрии, т.к. он идентичен с add_feature
        id = attrs['id']
        attrs = {k:v for k,v in attrs.items() if k not in ('id', 'calc_area', 'table_name')}
        if 'geom' in attrs.keys():
            geometry = parse_geometry(attrs['geom'], self.geom_type)
            #reproject
            geom = reproject_to_wgs(geometry)
            attrs['geom'] = from_shape(geom)

        #Преобразование '' в None у числовых полей
        for k,v in attrs.items():
            if self.columns[k] in ('INTEGER', 'DOUBLE_PRECISION') and v == '':
                attrs[k] = None
        q = self.layer_table.update()\
            .where(self.layer_table.c.id == id)\
            .values(attrs)
        cursor = execute_sql_and_commit(q)
        clear_geoserver_cache(self.name)
        return {"status": "ok", "layer": self.name}
    

    def add_feature(self, attrs: dict):
        """Добавляет новую фичу в слой

        Args:
            attrs (dict): новые атирбуты фичи, в т.ч. её id

        Returns:
            int: id фичи
        """

        attrs = {k:v for k,v in attrs.items() if k not in ('id')}
        if 'geom' in attrs.keys():
            geometry = parse_geometry(attrs['geom'], self.geom_type)
            geom = reproject_to_wgs(geometry)
            attrs['geom'] = from_shape(geom)

        q = self.layer_table.insert()\
            .values(attrs)\
            .returning(self.layer_table.c.id)
        cursor = execute_sql_and_commit(q)
        id = cursor.fetchone()[0]
        clear_geoserver_cache(self.name)
        return {"status": "ok", "layer": self.name, "id": id}


    def delete_feature(self, id: int):
        """Удаляет фичу слоя по id

        Args:
            id (int): id фичи
        """
        q = self.layer_table.delete()\
            .returning(self.layer_table.c.id)\
            .where(self.layer_table.c.id == id)
        cursor = execute_sql_and_commit(q)
        res = cursor.fetchone()[0]
        clear_geoserver_cache(self.name)
        return {"status": "ok", "layer": self.name, "feature": res}


    def get_field_values(self, field_name: str):
        col = self.layer_table.c[field_name]
        stmt = (
            select(col)
            .distinct()
            .where(col.is_not(None))   # опционально, если не нужны NULL
            .order_by(col.asc())
        )
        res = execute_sql_query(stmt).scalars().all()
        return res


    def add_field(self, field_name: str, field_type: str):
        # описываем новую колонку
        col_type = resolve_type(field_type)

        # 1. ALTER TABLE ... ADD COLUMN ... в БД
        ddl_type = col_type.compile(dialect=ENGINE.dialect)
        table_name = self.layer_table.fullname  # учитывает схему, если есть
    
        q = text(f'ALTER TABLE {table_name} ADD COLUMN "{field_name}" {ddl_type}')
        result = execute_sql_and_commit(q)
            
        # 2. Обновить метаданные SQLAlchemy в памяти
        new_col = Column(field_name, col_type, nullable=True)
        self.layer_table.append_column(new_col)
        LAYERS_META.reflect(bind=ENGINE)
        return {"status": "ok", "layer": self.name, "column": field_name}


    def delete_field(self, field_name: str):
        with ENGINE.begin() as conn:
            self.layer_table.c[field_name].drop(bind=conn)
        LAYERS_META.reflect(bind=ENGINE)
        return {"status": "ok", "layer": self.name, "column": field_name}


    def export(self, file_type: str, feature_ids: list = []):
        """Сохраняет слой в файл указанного формата
        """

        alias = self.get_alias()
        filename = f'{alias}_{str(datetime.now()).split(".")[0].replace(":", "_")}.{file_type}'
        file_path = f'{Config.UPLOAD_FOLDER}/{filename}'
        is_polygon = self.geom_type in ('POLYGON', 'MULTIPOLYGON')
        calc_area = ', round((ST_Area(ST_Transform(ST_MakeValid(geom), 4326)::geography)/ 10000)::numeric,  3) as calc_area'
        where = f'WHERE id in ({", ".join(feature_ids)})' if feature_ids else ''

        q = f"""
            SELECT *{calc_area if file_type == 'xlsx' and is_polygon else ''} FROM skolkovo_layers.{self.name}
            {where}
            {'LIMIT 1048575' if file_type == 'xlsx' else ''}
        """
        gdf = read_postgis(q)

        if len(gdf) < 1:
            return

        for col in gdf.columns:
            if gdf[col].apply(lambda x: isinstance(x, (time, datetime, date))).any():
                gdf[col] = gdf[col].astype(str)
        
        if file_type == 'xlsx':
            fields = FieldAlias()
            columns_dict = fields.get_field_aliases(orient="dict")
            gdf = gdf.rename(columns=columns_dict)
            gdf.to_excel(file_path)
        elif file_type in ('kml', 'gpkg'):
            gdf.to_file(file_path, driver=file_type.upper())
        elif file_type == 'geojson':
            gdf.to_file(file_path)
        return filename


    def delete(self):
        output = {'status': 'ok'}
        #delete in layers table and table itself
        q = self.layers_table.delete().returning(self.layers_table.c.id)\
            .where(self.layers_table.c.table_name == self.name)
        result = execute_sql_and_commit(q)
        remove_id = result.fetchone()[0]
        try:
            q1 = text(f'DROP TABLE skolkovo_layers.{self.name}')
            result = execute_sql_and_commit(q1) 
        except exc.ProgrammingError:
            return {'status': 'bad', "error": "Удаляемого слоя не существует или он назван другим именем"}, 500

        LAYERS_META.reflect(bind=ENGINE)
        output['remove_id'] = remove_id
        return output

    @classmethod
    def upload(cls, file: Union[FileStorage, gpd.GeoDataFrame], payload: dict):
        """Загружает слой в БД и заносит инфу о нём в таблицу слоёв

        Args:
            file (_type_): объект загружаемого файла
            payload (dict): параметры post-запроса с фронта
        """

        output = {"status": "ok"}
        if isinstance(file, FileStorage):
            ext = payload['source'].split(".")[1]
            try:
                if ext.lower() == 'kml':
                    layer = parse_kml(file)
                else:
                    layer = gpd.read_file(file, engine='pyogrio', use_arrow=True)

            except fiona.errors.DriverError:
                output['status'] = "bad"
                output['error'] = "layer is corrupt or is not supported"
                return output
        else:
            layer = file

        layer = layer.set_crs(4326) if not layer.crs else layer.to_crs(4326)

        #drop id column and rename reserved columns
        if 'id' in layer.columns:
            layer = layer.drop(columns=['id'])
        
        unwanted_column_names = set.intersection(set(layer.columns), consts.RESERVED_WORDS)
        if len(unwanted_column_names) > 0:
            return {"status": "bad", "error": f"Недоспустимые имена колонок {', '.join(unwanted_column_names)}. Их необходимо переименовать"}, 403
        
        #check if geom_col is "geom"
        geom_col = 'geom' if 'geom' in layer.columns else 'geometry'
        layer = layer.rename(columns = {geom_col: 'geom'})
        layer = layer.set_geometry("geom")
        if len(layer) > 0:
            layer = layer[~layer.geometry.isnull()]
            layer['geom'] = layer['geom'].apply(lambda g: enforce_geom_type(g))
        layer.columns = [c.lower() for c in layer.columns]
        
        geom_type = layer.geom_type.unique()[0] if len(layer) > 0 else 'MultiPolygon'
        if geom_type is None or geom_type == 'MultiPolygon':
            payload['geom_type'] = 'Polygon'
        elif geom_type == 'MultiLineString':
            payload['geom_type'] = 'LineString'
        else:
            payload['geom_type'] = geom_type

        #есть ещё layer_type_id и надо проверить, может ли этот пользователь грузить этот тип слоя
        payload['alias'] = payload['alias'] if 'alias' in payload.keys() else "Новый слой"

        updated_layer_id = cls._update_layers_table(cls, payload)[0] #update layers table first
        payload['table_name'] = f"layer_{updated_layer_id}" ##update layer name

        layer.to_postgis(payload['table_name'], ENGINE, schema="skolkovo_layers", if_exists='replace', index=False)
        cls.add_primary_key(cls, payload['table_name'], replace="id" in layer.columns)
        LAYERS_META.reflect(bind=ENGINE)

        df = read_sql("SELECT * FROM skolkovo_general.layers where id = %s", params=(updated_layer_id,))
        output['layer'] = df.to_dict(orient="records")[0]
        if len(layer) > 0:
            output['bbox'] = list(layer.to_crs(3857).geometry.total_bounds)
        return output


    def _update_layers_table(self, payload: dict):
        """Обновляет таблицу слоёв в БД, добавляя в неё строчку с новым слоем

        Args:
            payload (dict): строка таблицы для добавления
            rewrite_table_name (bool)
        """

        q = self.layers_table.insert().returning(self.layers_table.c.id)
        result = execute_sql_and_commit(q, payload)
        row = result.fetchone()

        attrs = {'table_name': f"layer_{row[0]}"}

        q1 = self.layers_table.update()\
            .where(self.layers_table.c.id == row[0])\
            .values(attrs)

        execute_sql_and_commit(q1)

        return row

    @classmethod
    def create_spatial_index(cls, layer_name: str):
        """Создаёт пространственный индекс в слое

        Args:
            layer_name (str): имя слоя в таблице skolkovo_general.layers
        """
        q = text(f'CREATE INDEX sidx_{layer_name}_geom ON skolkovo_layers.{layer_name} USING gist (geom);')
        result = execute_sql_and_commit(q)

        return result
    

    def add_primary_key(self, layer_name: str = None, replace=False):
        """Создаёт первичный ключ в слое

        Args:
            layer_name (str): имя слоя в таблице skolkovo_general.layers
            replace(bool): заменять колонку id или нет (на случай, если уже существует)
        """
        if layer_name == None:
            layer_name = self.name
        if replace:
            q = text(f'ALTER TABLE skolkovo_layers.{layer_name} DROP COLUMN id')
            res = execute_sql_and_commit(q)
        q = text(f'ALTER TABLE skolkovo_layers.{layer_name} ADD id serial;')
        q1 = text(f'ALTER TABLE skolkovo_layers.{layer_name} ADD CONSTRAINT {layer_name}_pk PRIMARY KEY (id);')
        result = execute_sql_and_commit([q, q1])
        return result
    

    def _get_layer_props(self, name: str):
        """Проверяет существование в БД слоя с именем name и возвращает его свойства из таблицы layers

        Args:
            name (Union[int, str]): layer name

        Raises:
            LayerNotExistException: 
        """
        cols = self.layers_table.c
        q = select(cols.alias, cols.layers_type_id).where(cols.table_name == name)
        row = execute_sql_query(q).fetchall()
        if len(row) == 0:
            raise LayerNotExistException('layer does not exist')
        return {
            'alias': row[0][0],
            'layers_type_id': row[0][1]
        }
           

    def _get_where_condition(self, filterField: str, filterValue):
        if filterField is not None and filterField != '':
            if filterValue != '':
                col_type = self.columns[filterField]
                if col_type in ('INTEGER', 'DOUBLE_PRECISION'):
                    return f" WHERE {filterField} = {filterValue}"
                else:
                    return f" WHERE lower({filterField}) like '%%{filterValue.lower()}%%'"
        return ""

