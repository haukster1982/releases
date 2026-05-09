# Heavy Metal Talks — Automatisk sjanger-oppdatering

Automatisert system for å hente metalutgivelser fra HeavyMetalBest og publisere dem på Blogger med riktige sjangere.

---

## Prosjektstruktur

```
├── 01_scrape_hmb.py                  # Henter album fra HMB + Firebase
├── 02_apply_genre_database.py        # Kobler sjangere fra lokale filer
├── 03_build_blogger_html.py          # Bygger SEO-vennlig HTML
├── 04_update_blogger_page.py         # Oppdaterer Blogger-siden
├── data/
│   ├── genre_database.csv            # Lokal verifisert sjangerbase
│   ├── band_genre_overrides.csv      # Band-nivå manuelle overrides
│   ├── album_genre_overrides.csv     # Album-spesifikke overrides
│   ├── hmb_export.csv                # Generert av 01
│   ├── hmb_with_genres.csv           # Generert av 02
│   ├── unresolved_genres.csv         # Album som trenger manuell sjekk
│   └── blogger_new_releases_block.html  # Generert av 03
└── .github/workflows/update-releases.yml
```

---

## Sjanger-prioritet

```
1. album_genre_overrides.csv   (albumspesifikk override — vinner over alt)
2. band_genre_overrides.csv    (band-nivå override)
3. genre_database.csv          (verifisert lokal sjangerbase)
4. HMB/Firebase tag            (fallback — status: needs_review)
5. Needs Review                (ingen sjanger funnet)
```

---

## Automatisk kjøring (GitHub Actions)

Workflowen kjører daglig kl 06:00 UTC og ved manuell trigger.

**Viktig: GitHub Actions kontakter IKKE Metal Archives.**
Metal Archives blokkerer GitHub Actions med HTTP 403 (Cloudflare).

---

## Ukentlig sjanger-review

1. Åpne `data/unresolved_genres.csv`
2. Se hvilke album som har `genre_status = needs_review`
3. Bruk `ma_search_url`-kolonnen til å søke manuelt i Metal Archives
4. Legg riktig sjanger inn i riktig fil:

**For hele bandet:**
```csv
# data/band_genre_overrides.csv
band,final_genre,source,verified,notes
Darkthrone,Black Metal,manual_metal_archives,yes,Checked manually
```

**For ett spesifikt album:**
```csv
# data/album_genre_overrides.csv
band,album,final_genre,source,verified,notes
Opeth,Damnation,Progressive Rock,manual_metal_archives,yes,Album-specific style
```

5. Commit og push:
```bash
git add data/band_genre_overrides.csv data/album_genre_overrides.csv
git commit -m "Update genre overrides"
git push
```

Neste kjøring bruker riktig sjanger automatisk og fjerner albumet fra `unresolved_genres.csv`.

---

## Blogger-siden — viktig

Siden må ha disse markørene for at scriptet skal fungere:

```html
<!-- HMT NEW RELEASES START -->
<!-- HMT NEW RELEASES END -->
```

Legg dem inn manuelt på Blogger-siden én gang. Alt mellom markørene oppdateres automatisk.

---

## GitHub Secrets som trengs

```
BLOG_ID
PAGE_ID
BLOGGER_CLIENT_SECRET_JSON
BLOGGER_TOKEN_JSON
```

---

## Lokal kjøring

```bash
pip install -r requirements.txt
python 01_scrape_hmb.py
python 02_apply_genre_database.py
python 03_build_blogger_html.py
python 04_update_blogger_page.py
```
