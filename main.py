from pathlib import Path
import json

from app.selector import select_photos
from app.template_engine import create_just_listed

ROOT = Path(__file__).resolve().parent

def main() -> None:
    listing_path = ROOT / "data" / "listing_2171821.json"
    rules_path = ROOT / "config" / "photo_selector.json"

    listing = json.loads(listing_path.read_text())
    selected = select_photos(listing, rules_path)

    output = create_just_listed(
        project_root=ROOT,
        photo_paths=selected,
        city=listing["city"],
        state=listing["state"],
        output_path=ROOT / "output" / listing["mls"] / "just_listed.png",
    )

    print(f"Listing: {listing['mls']}")
    print("Selected photos:")
    for path in selected:
        print(f"  - {path.name}")
    print(f"Generated: {output}")

if __name__ == "__main__":
    main()
