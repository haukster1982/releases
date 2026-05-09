"""
02_apply_genre_database.py
Kobler HMB-data mot lokal sjangerbase og overrides.

Prioritet:
1. album_genre_overrides.csv
2. band_genre_overrides.csv  
3. genre_database.csv
4. Firebase/HMB sjanger (hmb_genre felt)
5. Needs Review

Output:
  data/hmb_with_genres.csv
  data/unresolved_genres.csv
"""

import csv
import os
import re
import logging
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

INPUT_CSV       = "data/hmb_export.csv"
OUTPUT_CSV      = "data/hmb_with_genres.csv"
UNRESOLVED_CSV  = "data/unresolved_genres.csv"
ALBUM_OVERRIDES = "data/album_genre_overrides.csv"
BAND_OVERRIDES  = "data/band_genre_overrides.csv"
GENRE_DATABASE  = "data/genre_database.csv"

# Mapping fra HMB/Firebase sjanger-strenger til standardiserte labels
GENRE_MAPPING = {
    "death metal":        "Death Metal",
    "death":              "Death Metal",
    "black metal":        "Black Metal",
    "black":              "Black Metal",
    "thrash metal":       "Thrash Metal",
    "thrash":             "Thrash Metal",
    "doom metal":         "Doom Metal",
    "doom":               "Doom Metal",
    "heavy metal":        "Heavy Metal",
    "heavy":              "Heavy Metal",
    "power metal":        "Power Metal",
    "power":              "Power Metal",
    "progressive metal":  "Progressive Metal",
    "progressive":        "Progressive Metal",
    "prog metal":         "Progressive Metal",
    "folk metal":         "Folk Metal",
    "folk":               "Folk Metal",
    "symphonic metal":    "Symphonic Metal",
    "symphonic":          "Symphonic Metal",
    "gothic metal":       "Gothic Metal",
    "gothic":             "Gothic Metal",
    "melodic death metal": "Melodic Death Metal",
    "melodic death":      "Melodic Death Metal",
    "melodic black metal": "Melodic Black Metal",
    "melodic black":      "Melodic Black Metal",
    "atmospheric black metal": "Atmospheric Black Metal",
    "atmospheric black":  "Atmospheric Black Metal",
    "technical death metal": "Technical Death Metal",
    "technical death":    "Technical Death Metal",
    "blackened death metal": "Blackened Death Metal",
    "blackened death":    "Blackened Death Metal",
    "death doom metal":   "Death Doom Metal",
    "death doom":         "Death Doom Metal",
    "funeral doom metal": "Funeral Doom Metal",
    "funeral doom":       "Funeral Doom Metal",
    "speed metal":        "Speed Metal",
    "speed":              "Speed Metal",
    "grindcore":          "Grindcore",
    "grind":              "Grindcore",
    "metalcore":          "Metalcore",
    "deathcore":          "Deathcore",
    "sludge metal":       "Sludge Metal",
    "sludge":             "Sludge Metal",
    "stoner metal":       "Stoner Metal",
    "stoner":             "Stoner Metal",
    "post-metal":         "Post-Metal",
    "post metal":         "Post-Metal",
    "post":               "Post-Metal",
    "avant-garde metal":  "Avant-garde Metal",
    "avant-garde":        "Avant-garde Metal",
    "avant garde":        "Avant-garde Metal",
    "viking metal":       "Viking Metal",
    "viking":             "Viking Metal",
    "pagan metal":        "Pagan Metal",
    "pagan":              "Pagan Metal",
    "industrial metal":   "Industrial Metal",
    "industrial":         "Industrial Metal",
    "groove metal":       "Groove Metal",
    "groove":             "Groove Metal",
    "symphonic black metal": "Symphonic Black Metal",
    "symphonic death metal": "Symphonic Death Metal",
    "progressive death metal": "Progressive Death Metal",
    "progressive black metal": "Progressive Black Metal",
}


def normalize_genre_string(raw):
    """
    Tar en rå genre-streng fra Firebase og returnerer beste match.
    Firebase-sjangere kan se slik ut: "Death Metal, Death, Thrash Metal (early, later), Gothic Metal"
    """
    if not raw:
        return ""
    
    # Fjern parenteser med innhold
    cleaned = re.sub(r'\([^)]*\)', '', raw)
    
    # Split på komma
    parts = [p.strip().lower() for p in cleaned.split(',')]
    
    # Finn første match i GENRE_MAPPING
    for part in parts:
        part = part.strip()
        if part in GENRE_MAPPING:
            return GENRE_MAPPING[part]
    
    # Prøv å finne delstreng-match
    for part in parts:
        for key, val in GENRE_MAPPING.items():
            if key in part or part in key:
                return val
    
    return ""


def genre_to_filter_slugs(genre_str):
    """Konverterer sjanger til filter-slug."""
    if not genre_str or genre_str == "Needs Review":
        return "needs-review"
    slug = genre_str.lower().replace(" ", "-").replace("/", "-")
    return slug


def load_csv_lookup(filepath, key_fields, value_field="final_genre"):
    lookup = {}
    if not os.path.exists(filepath):
        return lookup
    with open(filepath, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = tuple(row.get(k, "").strip().lower() for k in key_fields)
            if row.get(value_field, "").strip():
                lookup[key] = row.get(value_field, "").strip()
    return lookup


def main():
    os.makedirs("data", exist_ok=True)

    album_overrides = load_csv_lookup(ALBUM_OVERRIDES, ["band", "album"])
    band_overrides  = load_csv_lookup(BAND_OVERRIDES,  ["band"])
    genre_database  = load_csv_lookup(GENRE_DATABASE,  ["band"])

    log.info(f"Album overrides:  {len(album_overrides)}")
    log.info(f"Band overrides:   {len(band_overrides)}")
    log.info(f"Genre database:   {len(genre_database)}")

    if not os.path.exists(INPUT_CSV):
        log.error(f"Finner ikke {INPUT_CSV}")
        return

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info(f"Behandler {len(rows)} album...")

    rows_out   = []
    unresolved = []

    for row in rows:
        band      = row.get("band", "").strip()
        album     = row.get("album", "").strip()
        hmb_genre = row.get("hmb_genre", "").strip()

        band_key  = (band.lower(),)
        album_key = (band.lower(), album.lower())

        final_genre  = ""
        genre_status = ""
        genre_source = ""

        # Prioritet 1: albumspesifikk override
        if album_key in album_overrides:
            final_genre  = album_overrides[album_key]
            genre_status = "verified"
            genre_source = "album_override"

        # Prioritet 2: band-nivå override
        elif band_key in band_overrides:
            final_genre  = band_overrides[band_key]
            genre_status = "verified"
            genre_source = "band_override"

        # Prioritet 3: lokal sjangerdatabase
        elif band_key in genre_database:
            final_genre  = genre_database[band_key]
            genre_status = "verified"
            genre_source = "genre_database"

        # Prioritet 4: Firebase/HMB sjanger
        elif hmb_genre:
            normalized = normalize_genre_string(hmb_genre)
            if normalized:
                final_genre  = normalized
                genre_status = "verified"
                genre_source = "firebase"
            else:
                final_genre  = "Needs Review"
                genre_status = "needs_review"
                genre_source = "no_match"

        # Prioritet 5: ingen sjanger
        else:
            final_genre  = "Needs Review"
            genre_status = "needs_review"
            genre_source = "no_genre"

        filter_slugs = genre_to_filter_slugs(final_genre)
        ma_search    = f"https://www.metal-archives.com/search?searchString={quote(band)}&type=band_name"

        out_row = {
            **row,
            "final_genre":   final_genre,
            "genre_status":  genre_status,
            "genre_source":  genre_source,
            "filter_slugs":  filter_slugs,
            "ma_search_url": ma_search,
        }
        rows_out.append(out_row)

        if genre_status == "needs_review":
            unresolved.append({
                "band":          band,
                "album":         album,
                "release_date":  row.get("release_date", ""),
                "hmb_genre":     hmb_genre,
                "final_genre":   final_genre,
                "genre_status":  genre_status,
                "hmb_url":       row.get("hmb_url", ""),
                "ma_search_url": ma_search,
            })

    if rows_out:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
        log.info(f"Skrevet {len(rows_out)} album til {OUTPUT_CSV}")

    if unresolved:
        with open(UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(unresolved[0].keys()))
            writer.writeheader()
            writer.writerows(unresolved)
        log.info(f"Skrevet {len(unresolved)} usikre album til {UNRESOLVED_CSV}")

    verified     = sum(1 for r in rows_out if r["genre_status"] == "verified")
    needs_review = sum(1 for r in rows_out if r["genre_status"] == "needs_review")
    log.info(f"Verified: {verified} | Needs Review: {needs_review}")


if __name__ == "__main__":
    main()
