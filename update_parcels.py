# pip install rosreestr2coord geopandas shapely pandas
import re
from typing import Iterable, List, Optional

import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import unary_union
from rosreestr2coord.parser import Area

# --- НАСТРОЙКИ ---
CAD_PATTERN = re.compile(r"\b\d+:\d+:\d+:\d+\b")  # общий паттерн КН
DEFAULT_CRS = "EPSG:4326"  # rosreestr обычно отдаёт в WGS84

# ---- АДАПТЕР ПОД rosreestr2coord ----
def get_geometry_by_cadnum(cadnum: str):
    """
    Вернёт shapely-геометрию по кадастровому номеру из rosreestr2coord.
    """
    # Вариант А: класс Area + .get_coord() -> список контуров (списков [lon, lat])
    try:
        area = Area(cadnum)
        coords = area.get_geometry()['geometry']  # часто: List[List[List[float]]], контуры в lon/lat
        if isinstance(coords, dict) and "type" in coords and "coordinates" in coords:
            return shape(coords)

        # иначе считаем, что это список контуров без дыр
        polygons = []
        for contour in coords:
            if not contour or len(contour) < 3:
                continue
            # rosreestr иногда не замыкает контур — замкнём
            if contour[0] != contour[-1]:
                contour = contour + [contour[0]]
            polygons.append(Polygon(contour))
        if not polygons:
            return None
        if len(polygons) == 1:
            return polygons[0]
        return MultiPolygon(polygons)
    except Exception:
        pass


# ---- УТИЛИТЫ ----
def extract_cadastral_numbers(value: object) -> List[str]:
    """
    Достаёт из ячейки все валидные КН.
    Поддерживает: '77:15:...','77:15:... , 50:20:...' и переносы строк.
    """
    if pd.isna(value):
        return []
    text = str(value)
    # Бывают переносы строк, запятые, точки с запятой — нам всё равно: ищем паттерн КН
    return CAD_PATTERN.findall(text)


def make_geodf_with_parcels(df: pd.DataFrame, cad_column: str = "Номер ЗУ") -> gpd.GeoDataFrame:
    """
    На вход: обычный DataFrame с колонкой cad_column, где содержатся кадастровые номера
    (по одному или списком). На выход: GeoDataFrame с геометрией участков (объединённой
    по строкам, если КН несколько).

    CRS: EPSG:4326.
    """
    geometries = []

    for idx, row in df.iterrows():
        print(f"{idx} out of {len(df)}")
        cad_nums: List[str] = extract_cadastral_numbers(row.get(cad_column))
        row_geoms = []
        for cad in cad_nums:
            geom = get_geometry_by_cadnum(cad)
            if geom is not None and not geom.is_empty:
                row_geoms.append(geom)

        if not row_geoms:
            geometries.append(None)
        else:
            # объединяем все геометрии ячейки
            try:
                merged = unary_union(row_geoms)
            except Exception:
                # на всякий случай fallback
                merged = row_geoms[0] if len(row_geoms) == 1 else MultiPolygon([g for g in row_geoms if g.geom_type == "Polygon"])
            geometries.append(merged)

    gdf = gpd.GeoDataFrame(df.copy(), geometry=geometries, crs=DEFAULT_CRS)
    return gdf


# ---- ПРИМЕР ИСПОЛЬЗОВАНИЯ ----
df = pd.read_excel("c:/Users/PC/Downloads/Telegram Desktop/Реестр_Сколково ГИС ЗУ_13.08.25.xlsx")
gdf = make_geodf_with_parcels(df, cad_column="Номер ЗУ")
gdf.to_file("d:/Angular/skolgis-backend/files/parcels.gpkg", driver="GPKG")
