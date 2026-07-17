import json
from pathlib import Path

def select_photos(listing: dict, rules_path: Path) -> list[Path]:
    rules = json.loads(rules_path.read_text())["standard_residential"]
    available = listing["photos"]
    selected = []

    for category in rules["required_categories"]:
        if category in available:
            selected.append(Path(available[category]))

    for category in rules["preferred_fourth"]:
        if len(selected) >= 4:
            break
        if category in available and Path(available[category]) not in selected:
            selected.append(Path(available[category]))

    if len(selected) != 4:
        raise ValueError(f"Expected 4 unique photo categories, found {len(selected)}.")

    return selected
