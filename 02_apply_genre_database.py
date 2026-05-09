"""
02_apply_genre_database.py
Kobler HMB-data mot lokal sjangerbase og overrides.
INGEN Metal Archives-requests — kun lokale filer.

Prioritet:
1. album_genre_overrides.csv
2. band_genre_overrides.csv
3. genre_database.csv
4. hmb_genre som fallback
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

INPUT_CSV          = "data/hmb_export.csv"
OUTPUT_CSV         = "data/hmb_with_genres.csv"
UNRESOLVED_CSV     = "data/unresolved_genres.csv"
ALBUM_OVERRIDES    = "data/album_genre_overrides.csv"
BAND_OVERRIDES     = "data/band_genre_overrides.csv"
GENRE_DATABASE     = "data/genre_database.csv"

# Normalisering av korte HMB-tags
HMB_NORMALIZE = {
    "black":       "Black Metal",
    "death":       "Death Metal",
    "doom":        "Doom Metal",
    "heavy":       "Heavy Metal",
    "power":       "Power Metal",
    "progressive": "Progressive Metal",
    "thrash":      "Thrash Metal",
    "prog":        "Progressive Metal",
    "grind":       "Grindcore",
    "stoner":      "Stoner Metal",
    "sludge":      "Sludge Metal",
    "gothic":      "Gothic Metal",
    "folk":        "Folk Metal",
    "viking":      "Viking Metal",
    "pagan":       "Pagan Metal",
    "symphonic":   "Symphonic Metal",
    "industrial":  "Industrial Metal",
    "groove":      "Groove Metal",
    "speed":       "Speed Metal",
    "post":        "Post-Metal",
    "avant":       "Avant-garde Metal",
    "metalcore":   "Metalcore",
    "deathcore":   "Deathcore",
    "grindcore":   "Grindcore",
}


def normalize_hmb_genre(raw):
    """Normaliserer kort HMB-tag til full sjanger."""
    if not raw:
        return ""
    key = raw.lower().strip()
    if key in HMB_NORMALIZE:
        return HMB_NORMALIZE[key]
    # Hvis det allerede er en full sjanger, behold den
    return raw.strip()


def genre_to_filter_slugs(genre_str):
    """
    Splitter kombinerte sjangere til filterbare slugs.
    'Gothic/Doom Metal' -> 'gothic-metal|doom-metal'
    'Death Metal; Grindcore' -> 'death-metal|grindcore'
    """
    if not genre_str or genre_str == "Needs Review":
        return "needs-review"

    parts = re.split(r"[/;,]", genre_str)
    slugs = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Håndter format som "Atmospheric Black/Folk Metal"
        if part and not part.lower().endswith("metal") and not part.lower().endswith("core"):
            part = part + " Metal"
        slug = part.lower().replace(" ", "-")
        if slug not in slugs:
            slugs.append(slug)
    return "|".join(slugs) if slugs else "needs-review"


def load_csv_lookup(filepath, key_fields, value_field="final_genre"):
    """Laster en CSV-fil og returnerer en dict."""
    lookup = {}
    if not os.path.exists(filepath):
        return lookup
    with open(filepath, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = tuple(row.get(k, "").strip().lower() for k in key_fields)
            if row.get(value_field, "").strip():
                lookup[key] = {
                    "final_genre":  row.get(value_field, "").strip(),
                    "verified":     row.get("verified", "").strip(),
                    "source":       row.get("source", "").strip(),
                }
    return lookup


def main():
    os.makedirs("data", exist_ok=True)

    # Last overrides og database
    album_overrides = load_csv_lookup(ALBUM_OVERRIDES, ["band", "album"])
    band_overrides  = load_csv_lookup(BAND_OVERRIDES,  ["band"])
    genre_database  = load_csv_lookup(GENRE_DATABASE,  ["band"])

    log.info(f"Album overrides:  {len(album_overrides)}")
    log.info(f"Band overrides:   {len(band_overrides)}")
    log.info(f"Genre database:   {len(genre_database)}")

    if not os.path.exists(INPUT_CSV):
        log.error(f"Finner ikke {INPUT_CSV} — kjør 01_scrape_hmb.py først")
        return

    rows_out      = []
    unresolved    = []

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info(f"Behandler {len(rows)} album...")

    for row in rows:
        band  = row.get("band", "").strip()
        album = row.get("album", "").strip()
        hmb_genre_raw = row.get("hmb_genre", "").strip()

        band_key  = (band.lower(),)
        album_key = (band.lower(), album.lower())

        final_genre  = ""
        genre_status = ""
        genre_source = ""
        review_reason = ""

        # Prioritet 1: albumspesifikk override
        if album_key in album_overrides:
            entry        = album_overrides[album_key]
            final_genre  = entry["final_genre"]
            genre_status = "verified"
            genre_source = "album_genre_overrides"

        # Prioritet 2: band-nivå override
        elif band_key in band_overrides:
            entry        = band_overrides[band_key]
            final_genre  = entry["final_genre"]
            genre_status = "verified"
            genre_source = "band_genre_overrides"

        # Prioritet 3: lokal sjangerdatabase
        elif band_key in genre_database:
            entry        = genre_database[band_key]
            final_genre  = entry["final_genre"]
            genre_status = "verified"
            genre_source = "genre_database"

        # Prioritet 4: HMB fallback
        elif hmb_genre_raw:
            final_genre   = normalize_hmb_genre(hmb_genre_raw)
            genre_status  = "needs_review"
            genre_source  = "hmb_fallback"
            review_reason = "Only HMB genre available"

        # Prioritet 5: ingen sjanger
        else:
            final_genre   = "Needs Review"
            genre_status  = "needs_review"
            genre_source  = "no_genre_found"
            review_reason = "No genre source found"

        # Bygg filter-slugs
        filter_slugs = genre_to_filter_slugs(final_genre)

        # Metal Archives søkelenke (kun for review — scriptet åpner ikke MA)
        ma_search = f"https://www.metal-archives.com/search?searchString={quote(band)}&type=band_name"

        out_row = {
            **row,
            "final_genre":   final_genre,
            "genre_status":  genre_status,
            "genre_source":  genre_source,
            "review_reason": review_reason,
            "filter_slugs":  filter_slugs,
            "ma_search_url": ma_search,
        }
        rows_out.append(out_row)

        if genre_status == "needs_review":
            unresolved.append({
                "band":               band,
                "album":              album,
                "release_date":       row.get("release_date", ""),
                "hmb_genre":          hmb_genre_raw,
                "final_genre":        final_genre,
                "genre_status":       genre_status,
                "review_reason":      review_reason,
                "hmb_url":            row.get("hmb_url", ""),
                "ma_search_url":      ma_search,
                "suggested_action":   "Check MA manually → add to band_genre_overrides.csv or album_genre_overrides.csv",
            })

    # Skriv output
    if rows_out:
        fieldnames = list(rows_out[0].keys())
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows_out)
        log.info(f"Skrevet {len(rows_out)} album til {OUTPUT_CSV}")

    if unresolved:
        fieldnames_u = list(unresolved[0].keys())
        with open(UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames_u)
            writer.writeheader()
            writer.writerows(unresolved)
        log.info(f"Skrevet {len(unresolved)} usikre album til {UNRESOLVED_CSV}")
    else:
        log.info("Ingen usikre sjangere!")

    # Statistikk
    verified     = sum(1 for r in rows_out if r["genre_status"] == "verified")
    needs_review = sum(1 for r in rows_out if r["genre_status"] == "needs_review")
    log.info(f"Verified: {verified} | Needs Review: {needs_review}")


if __name__ == "__main__":
    main()
