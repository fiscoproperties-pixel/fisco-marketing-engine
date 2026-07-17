from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


@dataclass
class PhotoScore:
    filename: str
    total_score: float
    brightness_score: float
    sharpness_score: float
    contrast_score: float
    resolution_score: float


def _clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(value, maximum))


def _brightness_score(image: Image.Image) -> float:
    grayscale = image.convert("L").resize((200, 200))
    average = ImageStat.Stat(grayscale).mean[0]

    # Real-estate photos generally look best when bright but not overexposed.
    ideal = 170
    difference = abs(average - ideal)

    return _clamp(100 - difference * 1.2)


def _contrast_score(image: Image.Image) -> float:
    grayscale = image.convert("L").resize((200, 200))
    standard_deviation = ImageStat.Stat(grayscale).stddev[0]

    # Reward healthy contrast while avoiding extremely flat images.
    return _clamp(standard_deviation * 2.2)


def _sharpness_score(image: Image.Image) -> float:
    grayscale = image.convert("L").resize((500, 500))
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_variation = ImageStat.Stat(edges).stddev[0]

    return _clamp(edge_variation * 5)


def _resolution_score(image: Image.Image) -> float:
    width, height = image.size
    megapixels = (width * height) / 1_000_000

    return _clamp(megapixels * 28)


def score_photo(path: Path) -> PhotoScore:
    with Image.open(path) as opened:
        image = opened.convert("RGB")

        brightness = _brightness_score(image)
        sharpness = _sharpness_score(image)
        contrast = _contrast_score(image)
        resolution = _resolution_score(image)

    total = (
        brightness * 0.30
        + sharpness * 0.30
        + contrast * 0.25
        + resolution * 0.15
    )

    return PhotoScore(
        filename=path.name,
        total_score=round(total, 2),
        brightness_score=round(brightness, 2),
        sharpness_score=round(sharpness, 2),
        contrast_score=round(contrast, 2),
        resolution_score=round(resolution, 2),
    )


def rank_photos(folder: Path) -> list[PhotoScore]:
    supported_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    photos = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in supported_extensions
    ]

    scores = [score_photo(path) for path in photos]

    return sorted(
        scores,
        key=lambda result: result.total_score,
        reverse=True,
    )