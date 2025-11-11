from PIL import ImageFont, ImageDraw, Image
import numpy as np

def draw_unicode_text(frame, text, position, font_path="arial.ttf", font_size=32, color=(0, 100, 255)):
    img_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(img_pil)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=color)
    return np.array(img_pil)