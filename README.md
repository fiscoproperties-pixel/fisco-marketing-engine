# Fisco Marketing Engine — Prototype 0.1

This first working version takes one listing record, selects four unique photo
categories, and generates a branded 1080 × 1080 Just Listed graphic.

## Current photo-selection rule

For a standard residential listing:

1. Exterior
2. Kitchen
3. Living room
4. Primary bathroom

The selector never intentionally chooses two photos from the same category.

## Run locally

```bash
python -m pip install -r requirements.txt
python main.py
```

The finished graphic is saved to:

```text
output/2171821/just_listed.png
```

## Project structure

```text
app/
  selector.py
  template_engine.py
assets/photos/2171821/
config/photo_selector.json
data/listing_2171821.json
output/2171821/
main.py
```

## Next build step

Replace the manually labeled photo map with a listing collector that downloads
all listing photos, followed by automatic room classification and ranking.


## Listing collector

The collector opens a FiscoRealEstate.com listing in Chromium, captures listing
data and image URLs from:

1. Embedded structured data
2. JSON/network responses
3. Loaded and lazy-loaded page images

It then downloads unique full-size images and saves diagnostics.

### One-time setup on Windows

Double-click:

```text
setup_windows.bat
```

Or run:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### Collect the Hiawatha listing

```bash
python collect.py "https://fiscorealestate.com/listing-detail/1185830733/3612-S-HIAWATHA-CIR-E-Saratoga-Springs-UT"
```

Expected outputs:

```text
assets/photos/<MLS>/downloaded/
data/listing_<MLS>_collected.json
diagnostics/
```

The diagnostics folder includes a full-page screenshot, saved HTML, and a JSON
file showing which image URLs were discovered through each method.

### Current boundary

The collector downloads and deduplicates the gallery. The next module will
classify those downloaded images into exterior, kitchen, living room, primary
bathroom, and other categories.
