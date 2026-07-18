
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from playwright.async_api import async_playwright, Page, Response


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
IMAGE_HOST_HINTS = ("img.chime.me", "cdn", "image", "photo", "media")


@dataclass
class CollectedListing:
    source_url: str
    listing_id: str
    mls: str | None
    address: str | None
    city: str | None
    state: str | None
    status: str | None
    photo_urls: list[str]


def _clean_url(url: str) -> str:
    """Remove query-string resizing parameters while retaining the image path."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _looks_like_listing_photo(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if any(token in lowered for token in ("logo", "avatar", "icon", "agent", "broker")):
        return False
    return (
        any(ext in lowered for ext in IMAGE_EXTENSIONS)
        or any(hint in lowered for hint in IMAGE_HOST_HINTS)
    )


def _extract_listing_id(url: str) -> str:
    match = re.search(r"/listing-detail/(\d+)", url)
    if match:
        return match.group(1)
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _deep_find_images(value: Any, found: set[str]) -> None:
    if isinstance(value, str):
        if _looks_like_listing_photo(value):
            found.add(value)
    elif isinstance(value, dict):
        for child in value.values():
            _deep_find_images(child, found)
    elif isinstance(value, list):
        for child in value:
            _deep_find_images(child, found)


def _deep_find_scalar(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in keys and isinstance(child, (str, int, float)):
                return child
        for child in value.values():
            result = _deep_find_scalar(child, keys)
            if result not in (None, ""):
                return result
    elif isinstance(value, list):
        for child in value:
            result = _deep_find_scalar(child, keys)
            if result not in (None, ""):
                return result
    return None


async def _extract_json_scripts(page: Page) -> list[Any]:
    payloads: list[Any] = []
    script_texts = await page.locator(
        'script[type="application/ld+json"], script#__NEXT_DATA__, script'
    ).all_text_contents()

    for text in script_texts:
        text = text.strip()
        if not text or len(text) < 2:
            continue

        candidates = [text]
        # Some sites wrap JSON in a JS assignment.
        match = re.search(r"({.*})", text, re.DOTALL)
        if match and match.group(1) != text:
            candidates.append(match.group(1))

        for candidate in candidates:
            try:
                payloads.append(json.loads(candidate))
                break
            except Exception:
                continue

    return payloads


async def _extract_dom_images(page: Page) -> list[str]:
    urls = await page.evaluate(
        """
        () => {
          const found = new Set();
          const add = value => {
            if (!value || typeof value !== 'string') return;
            value.split(',').forEach(part => {
              const candidate = part.trim().split(/\\s+/)[0];
              if (candidate.startsWith('http')) found.add(candidate);
            });
          };

          document.querySelectorAll('img').forEach(img => {
            add(img.currentSrc);
            add(img.src);
            add(img.getAttribute('data-src'));
            add(img.getAttribute('data-lazy-src'));
            add(img.getAttribute('srcset'));
            add(img.getAttribute('data-srcset'));
          });

          document.querySelectorAll('*').forEach(el => {
            const bg = getComputedStyle(el).backgroundImage;
            const matches = bg && [...bg.matchAll(/url\\(["']?(.*?)["']?\\)/g)];
            matches && matches.forEach(match => add(match[1]));
          });

          return [...found];
        }
        """
    )
    return [url for url in urls if _looks_like_listing_photo(url)]


async def _extract_text_fields(page: Page, payloads: list[Any]) -> dict[str, str | None]:
    body_text = await page.locator("body").inner_text()

    def from_payload(keys: set[str]) -> str | None:
        for payload in payloads:
            value = _deep_find_scalar(payload, keys)
            if value not in (None, ""):
                return str(value).strip()
        return None

    mls = from_payload({"mls", "mlsnumber", "mls_number", "listingid", "listing_id"})
    status = from_payload({"status", "listingstatus", "listing_status"})
    address = from_payload({"streetaddress", "address", "fulladdress", "full_address"})
    city = from_payload({"addresslocality", "city"})
    state = from_payload({"addressregion", "state", "stateorprovince"})

    if not mls:
        match = re.search(r"\bMLS(?:\s*#|\s*Number)?\s*[:#]?\s*([A-Z0-9-]{5,})", body_text, re.I)
        mls = match.group(1) if match else None

    title = await page.title()
    slug_match = re.search(
        r"/listing-detail/\d+/([^?]+)",
        page.url,
    )
    slug = slug_match.group(1) if slug_match else ""

    if not city:
        match = re.search(r"-([A-Za-z]+(?:-[A-Za-z]+)*)-UT$", slug)
        if match:
            city = match.group(1).replace("-", " ")

    if not state and ("-UT" in slug or ", UT" in body_text):
        state = "UT"

    if not address and slug:
        pieces = slug.split("-")
        if city:
            city_tokens = city.upper().split()
            upper_pieces = [piece.upper() for piece in pieces]
            # Remove city/state tokens from the end, leaving the street portion.
            end = len(pieces)
            if upper_pieces and upper_pieces[-1] == "UT":
                end -= 1
            end -= len(city_tokens)
            address = " ".join(pieces[:max(end, 0)]).title()

    return {
        "mls": mls,
        "status": status,
        "address": address,
        "city": city,
        "state": state,
        "page_title": title,
    }


async def collect_listing(url: str, diagnostics_dir: Path | None = None) -> CollectedListing:
    response_image_urls: set[str] = set()
    json_response_payloads: list[Any] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        async def inspect_response(response: Response) -> None:
            content_type = (response.headers.get("content-type") or "").lower()
            if "image/" in content_type and _looks_like_listing_photo(response.url):
                response_image_urls.add(response.url)
            elif "json" in content_type:
                try:
                    payload = await response.json()
                    json_response_payloads.append(payload)
                    _deep_find_images(payload, response_image_urls)
                except Exception:
                    pass

        page.on("response", inspect_response)

        await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            pass

        # Scroll to trigger lazy-loaded gallery images.
        for _ in range(8):
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(600)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(700)

        script_payloads = await _extract_json_scripts(page)
        all_payloads = script_payloads + json_response_payloads

        embedded_urls: set[str] = set()
        for payload in all_payloads:
            _deep_find_images(payload, embedded_urls)

        dom_urls = set(await _extract_dom_images(page))
        fields = await _extract_text_fields(page, all_payloads)

        combined = response_image_urls | embedded_urls | dom_urls
        cleaned: list[str] = []
        seen: set[str] = set()
        for url_value in combined:
            normalized = _clean_url(url_value)
            if normalized not in seen and _looks_like_listing_photo(normalized):
                seen.add(normalized)
                cleaned.append(normalized)

        # Prefer larger/property-hosted images and stable ordering.
        cleaned.sort(
            key=lambda item: (
                "img.chime.me" not in item,
                "original" not in item.lower(),
                item,
            )
        )

        listing_id = _extract_listing_id(url)

        if diagnostics_dir:
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            await page.screenshot(
                path=str(diagnostics_dir / f"{listing_id}_page.png"),
                full_page=True,
            )
            (diagnostics_dir / f"{listing_id}_dom.html").write_text(
                await page.content(),
                encoding="utf-8",
            )
            (diagnostics_dir / f"{listing_id}_image_urls.json").write_text(
                json.dumps(
                    {
                        "network": sorted(response_image_urls),
                        "embedded": sorted(embedded_urls),
                        "dom": sorted(dom_urls),
                        "combined": cleaned,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        await browser.close()

    return CollectedListing(
        source_url=url,
        listing_id=listing_id,
        mls=fields["mls"],
        address=fields["address"],
        city=fields["city"],
        state=fields["state"],
        status=fields["status"],
        photo_urls=cleaned,
    )


def download_photos(
    listing: CollectedListing,
    project_root: Path,
    minimum_bytes: int = 20_000,
) -> list[Path]:
    folder_name = listing.mls or listing.listing_id
    output_dir = project_root / "assets" / "photos" / folder_name / "downloaded"
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            ),
            "Referer": listing.source_url,
        }
    )

    downloaded: list[Path] = []
    hashes: set[str] = set()

    for index, url in enumerate(listing.photo_urls, start=1):
        try:
            response = session.get(url, timeout=35)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").lower()

            if "image" not in content_type or len(content) < minimum_bytes:
                continue

            digest = hashlib.sha256(content).hexdigest()
            if digest in hashes:
                continue
            hashes.add(digest)

            extension = ".webp"
            if "jpeg" in content_type or "jpg" in content_type:
                extension = ".jpg"
            elif "png" in content_type:
                extension = ".png"

            path = output_dir / f"{len(downloaded)+1:03d}{extension}"
            path.write_bytes(content)
            downloaded.append(path)
        except requests.RequestException:
            continue

    return downloaded


async def run(url: str, project_root: Path) -> None:
    diagnostics = project_root / "diagnostics"
    listing = await collect_listing(url, diagnostics_dir=diagnostics)
    photos = download_photos(listing, project_root)

    record = asdict(listing)
    record["downloaded_photos"] = [
        str(path.relative_to(project_root)) for path in photos
    ]

    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    identifier = listing.mls or listing.listing_id
    record_path = data_dir / f"listing_{identifier}_collected.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"Listing ID: {listing.listing_id}")
    print(f"MLS: {listing.mls or 'not detected'}")
    print(f"Address: {listing.address or 'not detected'}")
    print(f"City/State: {listing.city or '?'} / {listing.state or '?'}")
    print(f"Status: {listing.status or 'not detected'}")
    print(f"Candidate image URLs: {len(listing.photo_urls)}")
    print(f"Unique photos downloaded: {len(photos)}")
    print(f"Saved listing record: {record_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect listing data and photos from FiscoRealEstate.com."
    )
    parser.add_argument("url", help="Full FiscoRealEstate.com listing URL")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    asyncio.run(run(args.url, args.project_root.resolve()))


if __name__ == "__main__":
    main()
