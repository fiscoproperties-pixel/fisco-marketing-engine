from pathlib import Path

from app.photo_ranker import rank_photos


def main() -> None:
    photo_folder = Path("assets/photos/2171821")

    results = rank_photos(photo_folder)

    print("\nPhoto Rankings\n")

    for index, result in enumerate(results, start=1):
        print(
            f"{index}. {result.filename} | "
            f"Total: {result.total_score} | "
            f"Brightness: {result.brightness_score} | "
            f"Sharpness: {result.sharpness_score} | "
            f"Contrast: {result.contrast_score} | "
            f"Resolution: {result.resolution_score}"
        )


if __name__ == "__main__":
    main()