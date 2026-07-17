from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os

CANVAS_SIZE = (1080, 1080)
PHOTO_BOXES = [
    (30, 28, 522, 493),
    (540, 28, 1050, 493),
    (30, 511, 522, 982),
    (540, 511, 1050, 982),
]

def _font(paths: list[str], size: int):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def _cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    image = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))

def create_just_listed(
    project_root: Path,
    photo_paths: list[Path],
    city: str,
    state: str,
    output_path: Path,
) -> Path:
    if len(photo_paths) != 4:
        raise ValueError("Exactly four selected photos are required.")

    background = "#F5F0E9"
    circle_fill = "#F7F2EC"
    tan = "#B89A76"
    dark = "#332C27"

    canvas = Image.new("RGB", CANVAS_SIZE, background)
    draw = ImageDraw.Draw(canvas)

    for relative_path, box in zip(photo_paths, PHOTO_BOXES):
        path = project_root / relative_path
        x1, y1, x2, y2 = box
        image = _cover_crop(Image.open(path), (x2 - x1, y2 - y1))
        canvas.paste(image, (x1, y1))

    cx, cy, radius = 540, 510, 224
    draw.ellipse(
        (cx-radius-5, cy-radius-5, cx+radius+5, cy+radius+5),
        fill=background,
    )
    draw.ellipse(
        (cx-radius, cy-radius, cx+radius, cy+radius),
        fill=circle_fill,
        outline="#D8C7B2",
        width=3,
    )

    sans = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    serif = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
    ]
    italic = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
    ]

    draw.text(
        (cx, cy-156),
        "FIND YOUR DREAM HOME",
        font=_font(sans, 20),
        fill=dark,
        anchor="mm",
    )
    draw.text(
        (cx, cy-66),
        "Just",
        font=_font(italic, 82),
        fill=tan,
        anchor="mm",
    )
    draw.text(
        (cx, cy+16),
        "LISTED",
        font=_font(serif, 76),
        fill=dark,
        anchor="mm",
    )
    draw.line((cx-130, cy+75, cx+130, cy+75), fill=tan, width=2)
    draw.text(
        (cx, cy+122),
        f"{city.upper()}, {state.upper()}",
        font=_font(sans, 24),
        fill=dark,
        anchor="mm",
    )
    draw.text(
        (cx, 1040),
        "AMBRY & JESSE FISCO  |  REAL BROKER, LLC",
        font=_font(sans, 22),
        fill=dark,
        anchor="mm",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=96)
    return output_path
