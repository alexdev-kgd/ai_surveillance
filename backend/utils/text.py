from PIL import ImageFont, ImageDraw, Image
import numpy as np
import cv2
import os

TEXT_DEFAULT_POSITION = (20, 20)

def put_text_ru(
    frame,
    text,
    position=TEXT_DEFAULT_POSITION,
    font_size=24,
    color=(255, 0, 0),
    font_scale=0.030, # % of frame height
):
    h, w = frame.shape[:2]

    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    font_size = max(14, int(h * font_scale))
    font_path = os.path.join(os.path.dirname(__file__), "..","fonts", "Roboto.ttf")
    font_path = os.path.abspath(font_path)

    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Text Position
    x, y = position

    # Font Size
    text_bbox = draw.textbbox((0, 0), text, font=font)  # (left, top, right, bottom)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    # Clamp position to frame
    padding = 6
    x = max(padding, min(x, w - text_w - padding))
    y = max(padding, min(y, h - text_h - padding))

    # Draw rectangle background
    overlay = Image.new("RGBA", img_pil.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    rect_color = (0, 0, 0, 150)
    coordinates = [x - padding, y - padding, x + text_w + padding, y + text_h + padding]
    overlay_draw.rectangle(coordinates, fill=rect_color)

    # Composite overlay with original image
    img_pil = Image.alpha_composite(img_pil.convert("RGBA"), overlay)

    # Draw text
    draw = ImageDraw.Draw(img_pil)
    draw.text(position, text, font=font, fill=color + (255,)) 

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
