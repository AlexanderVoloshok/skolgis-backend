import tempfile
import fiona
import geopandas as gpd
import pandas as pd
import xml.etree.ElementTree as ET

fiona.drvsupport.supported_drivers['kml'] = 'rw'
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['libkml'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

def parse_kml(file_storage):
    # Сохраняем FileStorage во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='.kml') as tmp:
        file_storage.save(tmp.name)
        tmp_path = tmp.name

    # Читаем геометрию
    gdf = gpd.read_file(tmp_path, engine='pyogrio', use_arrow=True)[['geometry']]

    # Парсим XML
    tree = ET.parse(tmp_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    # Извлекаем список всех полей из <Schema>
    schema_fields = []
    schema = root.find('.//kml:Schema', ns)
    if schema is not None:
        for simple_field in schema.findall('kml:SimpleField', ns):
            field_name = simple_field.get('name')
            schema_fields.append(field_name)

    # Если схема не найдена — работаем только по тем полям, что есть
    schema_fields = schema_fields or []

    # Собираем атрибуты
    attributes_list = []
    for placemark in root.findall('.//kml:Placemark', ns):
        attrs = {field: None for field in schema_fields}  # Заполняем заранее все поля схемы None
        name = placemark.find('kml:name', ns)
        if name is not None:
            attrs['name'] = name.text
        description = placemark.find('kml:description', ns)
        if description is not None:
            attrs['description'] = description.text

        # Парсим ExtendedData -> SimpleData
        extended_data = placemark.find('kml:ExtendedData', ns)
        if extended_data is not None:
            for simple_data in extended_data.findall('.//kml:SimpleData', ns):
                key = simple_data.get('name')
                if key in attrs:
                    attrs[key] = simple_data.text
                else:
                    # Если поля не было в схеме, но оно встретилось — добавляем
                    attrs[key] = simple_data.text

        attributes_list.append(attrs)

    # DataFrame с учётом схемы
    attr_df = pd.DataFrame(attributes_list)

    # Гарантируем порядок столбцов: схема + доп поля
    all_columns = ['name', 'description'] + [col for col in schema_fields if col not in ('name', 'description')]
    final_columns = [col for col in all_columns if col in attr_df.columns] + [col for col in attr_df.columns if col not in all_columns]

    # Объединяем с геометрией
    final_gdf = pd.concat([gdf.reset_index(drop=True), attr_df.reset_index(drop=True)], axis=1)
    final_gdf = final_gdf.loc[:, ~final_gdf.columns.duplicated()]  # убираем дубли столбцов
    final_gdf = final_gdf[final_columns + ['geometry']]  # финальный порядок

    return final_gdf