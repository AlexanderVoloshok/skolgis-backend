from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from werkzeug.datastructures import FileStorage
from io import BytesIO

def pptx_from_image(image_file: FileStorage):
    # Создаём презентацию
    prs = Presentation()
    slide_layout = prs.slide_layouts[6]  # пустой слайд
    slide = prs.slides.add_slide(slide_layout)

    # Добавляем заголовок как текстовый блок
    left = Inches(0.5)
    top = Inches(0.3)
    width = Inches(9)
    height = Inches(1)

    title_box = slide.shapes.add_textbox(left, top, width, height)
    tf = title_box.text_frame
    tf.text = "Карта"

    # Настройка шрифта и выравнивания
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.runs[0]
    run.font.name = 'Montserrat'
    run.font.size = Pt(32)

    # Добавляем картинку
    img_left = Inches(0.5)
    img_top = Inches(1.5)
    slide.shapes.add_picture(image_file, img_left, img_top, width=Inches(8))

    # Сохраняем в буфер
    pptx_io = BytesIO()
    prs.save(pptx_io)
    pptx_io.seek(0)

    return pptx_io