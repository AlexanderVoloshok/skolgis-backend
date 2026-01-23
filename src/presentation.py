from __future__ import annotations


import os
from pyproj import datadir

proj_dir = datadir.get_data_dir()
os.environ["PROJ_DATA"] = proj_dir
os.environ["PROJ_LIB"] = proj_dir
print('proj_dir', proj_dir)

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import contextily as cx
import geopandas as gpd
from copy import deepcopy
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Tuple, List
from src.aliases import FieldAlias
from src.sql_utils import read_postgis
from src.utils import timeit


def replace_picture_on_slide(
    prs: Presentation,
    slide_index: int,
    image_bytes: bytes,
    *,
    shape_name: str | None = None,
    alt_text: str | None = None,
):
    """
    Заменяет картинку в существующей рамке слайда,
    не меняя её размер и позицию.
    """
    slide = prs.slides[slide_index]

    for shape in slide.shapes:
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue

        if shape_name and shape.name != shape_name:
            continue

        if alt_text and shape.alternative_text != alt_text:
            continue

        # 💡 магия подмены blob
        rId = shape._element.blipFill.blip.rEmbed
        image_part = shape.part.related_part(rId)
        image_part._blob = image_bytes
        return True

    raise ValueError("Picture placeholder not found on slide")

def replace_picture(slide, shape_name: str, image_bytes: bytes) -> None:
    for shape in slide.shapes:
        if shape.name == shape_name:
            left, top, width, height = shape.left, shape.top, shape.width, shape.height

            # удалить старую фигуру (заглушку)
            shape.element.getparent().remove(shape.element)

            # вставить новую — создаст корректные rels/rId
            slide.shapes.add_picture(
                BytesIO(image_bytes),
                left,
                top,
                width=width,
                height=height
            )
            return

    raise ValueError(f"Shape '{shape_name}' not found on slide")

class PresentationCreator():
    PRESENTATION_TEMPLATE = Presentation("d:/Angular/skolgis-backend/src/assets/slide_sample.pptx")

    def __init__(self, project_ids: List[int]):
        self.project_ids = project_ids
        self.skolkovo_gdf = read_postgis("SELECT * FROM skolkovo_layers.skolkovo_boundaries")

    @timeit
    def render_project_map_png(self, obj_gdf: gpd.GeoDataFrame) -> bytes:
        """
        Рендерит карту:
          - ESRI спутник (World Imagery)
          - границы Сколково красным, без заливки
          - объект (геометрия из obj_gdf)
        Зум: по bounds Сколково.

        Возвращает PNG bytes.
        """

        figsize: Tuple[float, float] = (10, 6)
        dpi: int = 220
        padding_ratio: float = 0.06
        obj_edgecolor: str = "blue"
        obj_lw: float = 2.2
        obj_facecolor: str = "#66CCFF"   # голубой

        target_crs = "EPSG:3857"
        sk = self.skolkovo_gdf.to_crs(target_crs)
        obj = obj_gdf.to_crs(target_crs)

        # bounds по Сколково + паддинг
        minx, miny, maxx, maxy = sk.total_bounds
        dx = maxx - minx
        dy = maxy - miny
        pad_x = dx * padding_ratio
        pad_y = dy * padding_ratio

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_y, maxy + pad_y)

        # ---------- СПУТНИКОВАЯ OPEN-SOURCE ПОДЛОЖКА ----------
        #cx.add_basemap(ax, source=cx.providers.NASAGIBS.BlueMarble, crs=target_crs, attribution=False, zorder=0)

        obj.plot(ax=ax, facecolor=obj_facecolor, edgecolor=obj_edgecolor, linewidth=obj_lw, alpha=0.35, zorder=20)
        # Контур поверх — чтобы был насыщенный
        obj.boundary.plot(ax=ax, color=obj_edgecolor, linewidth=obj_lw, alpha=1.0, zorder=25)

        sk.boundary.plot(ax=ax, color="red", linewidth=2.6, zorder=18)

        # --- Легенда ---
        # Для проекта легенду делаем как Patch (заливка + контур),
        # для Сколково — как Line2D (только контур).
        handles = [
            Line2D([0], [0], color="red", lw=2.6, label="Границы ИЦ Сколково"),
            Patch(facecolor=obj_facecolor, edgecolor=obj_edgecolor, linewidth=obj_lw, alpha=0.35, label="Границы проекта"),
        ]
        ax.legend(
            handles=handles, loc="upper left", fontsize=9, framealpha=0.9, borderpad=0.6, labelspacing=0.5, handlelength=2.2
        )

        ax.set_axis_off()
        plt.tight_layout(pad=0)

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        png_bytes = buf.read()

        #out_path = Path('d:/Angular/skolgis-backend/output.png')
        #out_path.parent.mkdir(parents=True, exist_ok=True)
        #out_path.write_bytes(png_bytes)

        return png_bytes

    def _prepare_all_payloads(self):
        """В многопоточном режиме подготавливает данные для каждого слайда.

        Args:
            slide_params_list (_type_): _description_

        Returns:
            _type_: _description_
        """
        #with ThreadPoolExecutor(max_workers=6) as pool:
        #    results = list(pool.map(self._prepare_slide_payload, self.project_ids))
        #return results
        return [self._prepare_slide_payload(pid) for pid in self.project_ids]

    def _prepare_slide_payload(self, project_id: int):
        """
        params: любые параметры для генерации этого слайда
        возвращаем:
          {
            "map_bytes": b"...",
            "attributes": { (row, col): "text", ... }
          }
        """
        obj_gdf = read_postgis(f"SELECT * FROM skolkovo_layers.layer_9 where id = {project_id}")
        map_bytes = self.render_project_map_png(obj_gdf)

        fields = FieldAlias()
        columns_dict = fields.get_field_aliases(orient="dict")
        obj_gdf = obj_gdf.rename(columns=columns_dict)
        
        return {
            "map_bytes": map_bytes,
            "attributes": obj_gdf.to_dict(),
        }
    
    def _clone_slide_template(self):
        """
        Клонирует source_slide в эту же презентацию.
        Внимание: это XML-копирование shapes; подходит для “однотипных” слайдов.

        Ограничения:
          - если на слайде есть диаграммы (charts), media, сложные связи — может потребовать доп. обработки.
          - для картинок/таблиц/текста обычно достаточно.
        """
        source_slide = self.PRESENTATION_TEMPLATE.slides[1]
        layout = source_slide.slide_layout
        new_slide = self.PRESENTATION_TEMPLATE.slides.add_slide(layout)

        # удалить авто-плейсхолдеры, которые добавил layout
        for shp in list(new_slide.shapes):
            try:
                shp.element.getparent().remove(shp.element)
            except Exception:
                pass

        # копируем shapes из source_slide
        for shp in source_slide.shapes:
            new_el = deepcopy(shp.element)
            new_slide.shapes._spTree.insert_element_before(new_el, "p:extLst")

        return new_slide

    def fill_presentation(self):
        # 1) Параллельно готовим всё тяжёлое
        payloads = self._prepare_all_payloads()

        # 2) Открываем PPTX и в ОДНОМ потоке обновляем
        for idx, payload in enumerate(payloads):
            slide = self._clone_slide_template()
            # находим картинку и подменяем её blob — без изменения рамки
            replace_picture(slide, "MapImage", payload["map_bytes"])

        buf = BytesIO()
        self.PRESENTATION_TEMPLATE.save(buf)
        buf.seek(0)

        return buf.getvalue()



if __name__ == '__main__':
    project_ids = [34, 60]

    pres = PresentationCreator(project_ids)
    pres.fill_presentation()

    pres.PRESENTATION_TEMPLATE.save('d:/Angular/skolgis-backend/output.pptx')