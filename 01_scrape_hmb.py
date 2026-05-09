"""
01_scrape_hmb.py
Henter Full-length album fra HeavyMetalBest via Firebase REST API og HTML-scraping.
Output: data/hmb_export.csv
"""

import requests
import csv
import json
import time
import logging
import os
from datetime import datetime, date
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HMB_RECENT   = "https://heavymetalbest.com/newReleases"
HMB_UPCOMING = "https://heavymetalbest.com/upcoming-albums"
OUTPUT_CSV   = "data/hmb_export.csv"
ARKIV_FILE   = "data/hmb_arkiv.json"
REQUEST_DELAY = 1.5

FIREBASE_API_KEY = "AIzaSyCIe5zlVLYvQ68WzYgS6sa76X328gEgfZs"
FIREBASE_PROJECT = "heavy-metal-best"
FIRESTORE_URL    = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)/documents:runQuery"

HMB_GENRE_TAGS = [
    "Death Metal", "Black Metal", "Thrash Metal", "Doom Metal",
    "Heavy Metal", "Power Metal", "Progressive Metal",
]


def firestore_query_genre(genre_tag, limit=50):
    genre_variants = [genre_tag]
    if " Metal" in genre_tag:
        genre_variants.append(genre_tag.replace(" Metal", ""))

    body = {
        "structuredQuery": {
            "from": [{"collectionId": "albums"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "genre"},
                    "op": "ARRAY_CONTAINS_ANY",
                    "value": {
                        "arrayValue": {
                            "values": [{"stringValue": v} for v in genre_variants]
                        }
                    }
                }
            },
            "orderBy": [{"field": {"fieldPath": "releaseDate"}, "direction": "DESCENDING"}],
            "limit": limit
        }
    }
    try:
        resp = requests.post(
            f"{FIRESTORE_URL}?key={FIREBASE_API_KEY}",
            json=body, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        albums = []
        for item in resp.json():
            if "document" not in item:
                continue
            albums.append(_parse_fields(item["document"].get("fields", {})))
        log.info(f"Firebase: {len(albums)} album for '{genre_tag}'")
        return albums
    except Exception as e:
        log.error(f"Firebase feil for '{genre_tag}': {e}")
        return []


def _parse_fields(fields):
    result = {}
    for key, value in fields.items():
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "integerValue" in value:
            result[key] = int(value["integerValue"])
        elif "arrayValue" in value:
            arr = value["arrayValue"].get("values", [])
            result[key] = [v.get("stringValue", "") for v in arr]
        elif "timestampValue" in value:
            result[key] = value["timestampValue"]
        else:
            result[key] = str(value)
    return result


def build_firebase_lookup():
    """Henter sjanger-data fra Firebase for alle HMB-sjangere."""
    lookup = {}
    for genre in HMB_GENRE_TAGS:
        time.sleep(REQUEST_DELAY)
        for album in firestore_query_genre(genre, limit=50):
            band  = (album.get("band") or "").strip()
            title = (album.get("name") or "").strip()
            if not band or not title:
                continue
            key = (band.lower(), title.lower())
            if key not in lookup:
                lookup[key] = {"band": band, "name": title, "genres": set()}
            raw = album.get("genre", [])
            if isinstance(raw, list):
                lookup[key]["genres"].update(raw)
            lookup[key]["genres"].add(genre)
    return {k: list(v["genres"]) for k, v in lookup.items()}


def fetch_hmb_html(url, future_only=False):
    """Henter album fra HMB via HTML-scraping."""
    log.info(f"Henter fra {url} ...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.error(f"Feil: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    out, seen = [], set()
    today = date.today()

    for link in soup.find_all("a", href=True):
        if "/album/" not in link["href"]:
            continue
        texts = [t.strip() for t in link.stripped_strings]
        if len(texts) < 3:
            continue
        album, band, meta = texts[0], texts[1], texts[2]
        if not meta.lower().startswith("full-length"):
            continue
        key = (band.lower(), album.lower())
        if key in seen:
            continue
        seen.add(key)

        sort_key, date_disp, month_key = "", "", "Unknown"
        try:
            dt = datetime.strptime(meta.split(",", 1)[1].strip(), "%b %d, %Y")
            sort_key  = dt.isoformat()
            date_disp = dt.strftime("%B %d, %Y").replace(" 0", " ")
            month_key = dt.strftime("%B %Y")
        except:
            date_disp = meta

        if future_only and sort_key and datetime.fromisoformat(sort_key).date() < today:
            continue

        img_tag = link.find("img")
        img_url  = img_tag["src"] if img_tag and img_tag.get("src") else ""
        full_url = link["href"] if link["href"].startswith("http") else "https://heavymetalbest.com" + link["href"]

        # Hent albumId fra URL
        album_id = ""
        if "albumId=" in full_url:
            album_id = full_url.split("albumId=")[-1].split("&")[0]

        out.append({
            "band":      band,
            "album":     album,
            "release_date": sort_key[:10] if sort_key else "",
            "date_disp": date_disp,
            "month_key": month_key,
            "sort_key":  sort_key,
            "hmb_genre": "",  # fylles inn fra Firebase
            "hmb_url":   full_url,
            "cover_url": img_url,
            "album_id":  album_id,
            "upcoming":  future_only,
        })

    if future_only:
        out.sort(key=lambda x: x["sort_key"])
    else:
        out.sort(key=lambda x: x["sort_key"], reverse=True)

    log.info(f"  Fant {len(out)} full-length utgivelser")
    return out


def load_arkiv():
    if os.path.exists(ARKIV_FILE):
        with open(ARKIV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_arkiv(arkiv):
    os.makedirs("data", exist_ok=True)
    with open(ARKIV_FILE, "w", encoding="utf-8") as f:
        json.dump(arkiv, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs("data", exist_ok=True)

    # 1. Hent fra HMB HTML
    recent   = fetch_hmb_html(HMB_RECENT,   future_only=False)
    upcoming = fetch_hmb_html(HMB_UPCOMING, future_only=True)
    all_albums = recent + upcoming

    # 2. Hent Firebase sjanger-lookup
    log.info("Henter sjanger fra Firebase...")
    firebase_lookup = build_firebase_lookup()
    log.info(f"Firebase: {len(firebase_lookup)} album med sjanger")

    # 3. Legg Firebase-sjanger på albumene
    for a in all_albums:
        lkey = (a["band"].lower(), a["album"].lower())
        if lkey in firebase_lookup:
            genres = firebase_lookup[lkey]
            # Bruk første relevante sjanger som hmb_genre
            a["hmb_genre"] = ", ".join(genres)

    # 4. Last og oppdater arkiv
    arkiv = load_arkiv()
    for a in all_albums:
        key = f"{a['band'].lower()}||{a['album'].lower()}"
        if key not in arkiv:
            arkiv[key] = a
        else:
            # Oppdater dato og sjanger
            if a.get("sort_key"):
                arkiv[key]["sort_key"]     = a["sort_key"]
                arkiv[key]["date_disp"]    = a["date_disp"]
                arkiv[key]["month_key"]    = a["month_key"]
                arkiv[key]["release_date"] = a["release_date"]
            if a.get("hmb_genre"):
                arkiv[key]["hmb_genre"] = a["hmb_genre"]

    save_arkiv(arkiv)
    log.info(f"Arkiv: {len(arkiv)} album totalt")

    # 5. Skriv CSV
    fieldnames = ["band", "album", "release_date", "date_disp", "month_key",
                  "sort_key", "hmb_genre", "hmb_url", "cover_url", "album_id", "upcoming"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        # Skriv alle fra arkiv
        rows = sorted(arkiv.values(), key=lambda x: x.get("sort_key", ""), reverse=True)
        writer.writerows(rows)

    log.info(f"Skrevet {len(arkiv)} album til {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
