import os, re
import requests
from requests.auth import HTTPBasicAuth
from geo.Geoserver import Geoserver, GeoserverException
from config import Config
from utils import get_logger

logger = get_logger(__name__)

geo = Geoserver(Config.GEOSERVER_ROOT, username=Config.GEOSERVER_USER, password=Config.GEOSERVER_PWD)


def convert_svg_to_css(sld_content: str):
    # Replace `se:SvgParameter` with `CssParameter`
    sld_content = re.sub(r"<se:SvgParameter", "<CssParameter", sld_content)
    sld_content = re.sub(r"</se:SvgParameter>", "</CssParameter>", sld_content)
    return sld_content


def hex_to_opacity(hex_color: str) -> float:
    """
    Преобразует прозрачность из HEX-цвета в значение от 0 до 1.
    :param hex_color: Цвет в формате HEX (например, #RRGGBBAA).
    :return: Прозрачность в виде числа от 0 до 1.
    """
    if len(hex_color) == 9:  # Формат #RRGGBBAA
        alpha_hex = hex_color[-2:]  # Последние 2 символа — это прозрачность
        alpha_int = int(alpha_hex, 16)  # Преобразуем в десятичное число
        return alpha_int / 255  # Нормализуем в диапазон [0, 1]
    elif len(hex_color) == 7:  # Формат #RRGGBB (без прозрачности)
        return 1.0  # Полностью непрозрачно
    else:
        raise ValueError("Некорректный формат HEX-цвета. Используйте #RRGGBB или #RRGGBBAA.")
    

def create_sld(geometry_type: str, style: dict):
    """
    Создает SLD-файл для Geoserver слоя.
    """
    if geometry_type not in ["POINT", "LINESTRING", "MULTILINESTRING", "POLYGON", "MULTIPOLYGON"]:
        raise ValueError("Недопустимый тип геометрии. Выберите из 'point', 'line', 'polygon'.")

    outline_width, outline_color = style['outlineWidth'], style['outlineColor']
    outline_color = outline_color[:-2] if len(outline_color) == 9 else outline_color
    stroke_opacity = hex_to_opacity(outline_color)
    if geometry_type not in ("LINESTRING", "MULTILINESTRING"):
        fill_color = style['fillColor'][:-2] if len(style['fillColor']) == 9 else style['fillColor']
        fill_opacity = hex_to_opacity(style['fillColor'])

    if geometry_type == "POINT":
        symbolizer = f"""
            <PointSymbolizer>
                <Graphic>
                    <Mark>
                        <WellKnownName>circle</WellKnownName>
                        <Fill>
                            <CssParameter name="fill">{fill_color}</CssParameter>
                        </Fill>
                        <Stroke>
                            <CssParameter name="stroke">{outline_color}</CssParameter>
                            <CssParameter name="stroke-width">{outline_width}</CssParameter>
                        </Stroke>
                    </Mark>
                    <Size>10</Size>
                </Graphic>
            </PointSymbolizer>
        """
    elif geometry_type in ("LINESTRING", "MULTILINESTRING"):
        symbolizer = f"""
            <LineSymbolizer>
                <Stroke>
                    <CssParameter name="stroke">{outline_color}</CssParameter>
                    <CssParameter name="stroke-width">{outline_width}</CssParameter>
                    <CssParameter name="stroke-opacity">{stroke_opacity}</CssParameter>
                </Stroke>
            </LineSymbolizer>
        """
    elif geometry_type in  ("POLYGON", "MULTIPOLYGON"):
        symbolizer = f"""
            <PolygonSymbolizer>
                <Fill>
                    <CssParameter name="fill">{fill_color}</CssParameter>
                    <CssParameter name="fill-opacity">{fill_opacity}</CssParameter>
                </Fill>
                <Stroke>
                    <CssParameter name="stroke">{outline_color}</CssParameter>
                    <CssParameter name="stroke-width">{outline_width}</CssParameter>
                    <CssParameter name="stroke-opacity">{stroke_opacity}</CssParameter>
                </Stroke>
            </PolygonSymbolizer>
        """

    sld_template = """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
        <NamedLayer>
            <Name>Simple Style</Name>
            <UserStyle>
                <Title>Default Style</Title>
                <Abstract>A simple default style</Abstract>
                <FeatureTypeStyle>
                    <Rule>
                        <Name>Default Rule</Name>
                        <Title>Default</Title>
                        {symbolizer}
                    </Rule>
                </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>
    """

    return sld_template.format(symbolizer=symbolizer)


def publish_on_geoserver(table_name: str):
    """Публикует слой на Geoserver
    """

    sql = 'SELECT * FROM geo.%s' % table_name
    try:
        geo.delete_layer(layer_name=table_name, workspace=Config.GEOSERVER_WORKSPACE)
    except GeoserverException:
        pass
    except Exception as e:
        raise e
    result = geo.publish_featurestore_sqlview(store_name=Config.GEOSERVER_STORE_NAME, name=table_name, 
        sql=sql, workspace=Config.GEOSERVER_WORKSPACE)
    return table_name


def clear_geoserver_cache(name: str):
    """Очищает кэш слоя на geoserver
    """
    url = f"{Config.GEOSERVER_ROOT}/gwc/rest/seed/rgis:{name}" #.json
    headers = {
        "Content-Type": "application/json"
    }
    data = {"seedRequest": {
        "name": f"rgis:{name}",
        "gridSetId": "EPSG:900913",
        "zoomStart": 0,
        "zoomStop": 30,
        "format": "image/png8",
        "type": "truncate"
    }}
    response = requests.post(
        url,
        headers=headers,
        data=data, 
        auth=HTTPBasicAuth(Config.GEOSERVER_USER, Config.GEOSERVER_PWD)
    )
    # Проверка ответа
    if response.status_code == 200:
        return {'status': 'ok'}
    else:
        logger.info(f'cache not cleared for layer {name}')


def upload_style_to_geoserver(layer_name: str, xml_str: str = None, style_name: str = None, delete_father:bool=True):
    """Загружает стиль на геосервер
    Args:
        path (str): Если указан - xml string стиля
        style_name (str): Если указан - имя стиля
    """
    style_path = f"{Config.UPLOAD_FOLDER}/sld/{layer_name}.sld"

    if xml_str is None and os.path.exists(style_path):
        with open(style_path, 'r') as sld_file:
            xml_str = sld_file.read().encode('utf-8')
    if xml_str is not None:
        if type(xml_str) == bytes:
            xml_str = xml_str.decode('utf-8')
        xml_str = convert_svg_to_css(xml_str)
    #если есть предыдущий стиль - удаляем. Это опциональный параметр
    if delete_father:
        try:
            geo.delete_style(style_name=layer_name, workspace=Config.GEOSERVER_WORKSPACE)
        except GeoserverException:
            pass
        except Exception as e:
            raise e
    if xml_str is None or xml_str == '':
        return
    geo.upload_style(path=xml_str.encode('utf-8'), name=style_name or layer_name, workspace=Config.GEOSERVER_WORKSPACE)
    geo.publish_style(layer_name=layer_name, style_name=layer_name, workspace=Config.GEOSERVER_WORKSPACE)


def delete_geoserver_style(style_name: str):
    try:
        result = geo.delete_layer(style_name, workspace=Config.GEOSERVER_WORKSPACE)
        geo.delete_style(style_name=style_name, workspace=Config.GEOSERVER_WORKSPACE)
    except GeoserverException as e:
        result = {"status": "bad", "error": "failed to delete layer from geoserver"}
    return result
