"""
03_build_blogger_html.py
Bygger SEO-vennlig HTML for Blogger med automatisk sjanger-dropdown.
Albumkortene er ekte HTML — ikke JavaScript-generert.

Output: data/blogger_new_releases_block.html
"""

import csv
import os
import logging
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

INPUT_CSV   = "data/hmb_with_genres.csv"
OUTPUT_HTML = "data/blogger_new_releases_block.html"


def slug_to_label(slug):
    """Konverterer 'death-metal' til 'Death Metal'."""
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


def ma_search_url(band):
    return f"https://www.metal-archives.com/search?searchString={quote(band)}&type=band_name"


def build_html(rows):
    updated   = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
    year      = datetime.now().year

    # Samle alle sjangere for dropdown
    all_genre_slugs = set()
    for r in rows:
        for slug in r.get("filter_slugs", "").split("|"):
            if slug:
                all_genre_slugs.add(slug)

    # Sorter sjangere — "needs-review" sist
    sorted_genres = sorted(
        [s for s in all_genre_slugs if s != "needs-review"]
    ) + (["needs-review"] if "needs-review" in all_genre_slugs else [])

    genre_options = "\n".join(
        f'    <option value="{slug}">{slug_to_label(slug)}</option>'
        for slug in sorted_genres
    )

    # Grupper etter måned
    by_month = defaultdict(list)
    month_order = {}
    for r in rows:
        if r.get("upcoming") == "True":
            continue
        m = r.get("month_key", "Unknown")
        if m not in month_order:
            month_order[m] = r.get("sort_key", "")
        by_month[m].append(r)

    upcoming_rows = [r for r in rows if r.get("upcoming") == "True"]

    recent_count  = sum(len(v) for v in by_month.values())
    upcoming_count = len(upcoming_rows)

    css = """<style>
.hmt-hidden{display:none}
.hmt-filter-box{margin:1rem 0 1.5rem}
.hmt-filter-box label{font-size:.75rem;font-weight:bold;text-transform:uppercase;letter-spacing:.1em;color:#9b30d0;display:block;margin-bottom:.3rem}
.hmt-genre-select,.hmt-status-select{width:100%;padding:.5rem .8rem;background:#111;border:1px solid #9b30d0;color:#e0e0e0;font-size:.85rem;box-sizing:border-box;margin-bottom:.6rem;cursor:pointer}
.hmt-genre-select:focus,.hmt-status-select:focus{outline:none;border-color:#c060f0}
.hmt-count{font-size:.65rem;color:#555;margin-top:.3rem}
.hmt-sec{font-size:.68rem;font-weight:bold;letter-spacing:.2em;text-transform:uppercase;color:#fff;background:#9b30d0;padding:.35rem .9rem;margin:1.5rem 0 .4rem;display:inline-block}
.hmt-month-label{font-size:.62rem;text-transform:uppercase;letter-spacing:.18em;color:#9b30d0;border-bottom:1px solid #1e1e1e;padding-bottom:.25rem;margin-bottom:.15rem}
.hmt-release-card{display:flex;align-items:center;gap:.6rem;border:none;border-bottom:1px solid #1a1a1a;padding:.35rem .2rem;background:transparent}
.hmt-cover{width:52px;height:52px;object-fit:cover;flex-shrink:0;display:block;background:#111}
.hmt-release-info{flex:1;display:flex;flex-direction:column;gap:.05rem}
.hmt-release-info h3{font-size:.84rem;font-weight:bold;color:#f0f0f0;margin:0;line-height:1.2}
.hmt-date{font-size:.6rem;color:#444;margin:0}
.hmt-genre-text{font-size:.65rem;color:#888;margin:0;font-style:italic}
.hmt-review-badge{font-size:.55rem;color:#c060f0;margin:0}
.hmt-links{display:flex;gap:.4rem;margin-top:.2rem;flex-wrap:wrap}
.hmt-links a{font-size:.6rem;color:#9b30d0;text-decoration:none;border:1px solid #3a1a5a;padding:.1rem .4rem;transition:all .12s}
.hmt-links a:hover{background:#9b30d0;color:#fff}
</style>"""

    # Bygg album-kort
    def make_card(r):
        band     = r.get("band", "")
        album    = r.get("album", "")
        date_disp = r.get("date_disp", r.get("release_date", ""))
        final_genre = r.get("final_genre", "")
        genre_status = r.get("genre_status", "")
        filter_slugs = r.get("filter_slugs", "")
        hmb_url  = r.get("hmb_url", "")
        cover_url = r.get("cover_url", "")
        ma_url   = ma_search_url(band)

        img_html = f'<img class="hmt-cover" src="{cover_url}" alt="{band} - {album} album cover" loading="lazy">' if cover_url else '<div class="hmt-cover"></div>'

        review_badge = ""
        if genre_status == "needs_review":
            review_badge = '<p class="hmt-review-badge">Genre needs review</p>'

        genre_display = f'<p class="hmt-genre-text">{final_genre}</p>' if final_genre and final_genre != "Needs Review" else ""

        return f"""<article class="hmt-release-card" data-genres="{filter_slugs}" data-review-status="{genre_status}">
  {img_html}
  <div class="hmt-release-info">
    <h3>{band} – {album}</h3>
    <p class="hmt-date">{date_disp}</p>
    {genre_display}
    {review_badge}
    <div class="hmt-links">
      <a href="{hmb_url}" target="_blank" rel="nofollow noopener">HMB</a>
      <a href="{ma_url}" target="_blank" rel="nofollow noopener">Metal Archives</a>
    </div>
  </div>
</article>"""

    # Bygg månedsseksjoner
    month_sections = []
    for month in sorted(month_order.keys(), key=lambda m: month_order[m], reverse=True):
        cards = "\n".join(make_card(r) for r in by_month[month])
        month_sections.append(f'<div class="hmt-month"><p class="hmt-month-label">{month}</p>\n{cards}\n</div>')

    # Bygg upcoming-seksjon
    upcoming_section = ""
    if upcoming_rows:
        upcoming_cards = "\n".join(make_card(r) for r in sorted(upcoming_rows, key=lambda x: x.get("sort_key", "")))
        upcoming_section = f"""<span class="hmt-sec">&#9654; Upcoming Releases</span>
<p class="hmt-count">{upcoming_count} confirmed upcoming releases</p>
{upcoming_cards}"""

    js = """<script>
(function(){
  var genreSelect  = document.getElementById("hmt-genre-filter");
  var statusSelect = document.getElementById("hmt-status-filter");
  var countEl      = document.getElementById("hmt-release-count");
  var cards        = Array.from(document.querySelectorAll(".hmt-release-card"));

  function updateFilter(){
    var selGenre  = genreSelect  ? genreSelect.value  : "";
    var selStatus = statusSelect ? statusSelect.value : "";
    var visible   = 0;
    cards.forEach(function(card){
      var genres = (card.dataset.genres  || "").split("|");
      var status =  card.dataset.reviewStatus || "";
      var gMatch = !selGenre  || genres.indexOf(selGenre)  > -1;
      var sMatch = !selStatus || status === selStatus;
      if(gMatch && sMatch){
        card.classList.remove("hmt-hidden");
        visible++;
      } else {
        card.classList.add("hmt-hidden");
      }
    });
    var label = "";
    if(selGenre && genreSelect){
      label = genreSelect.options[genreSelect.selectedIndex].text;
    }
    countEl.textContent = visible + " album" + (label ? " — " + label : "");
  }

  if(genreSelect)  genreSelect.addEventListener("change",  updateFilter);
  if(statusSelect) statusSelect.addEventListener("change", updateFilter);
  updateFilter();
})();
</script>"""

    html = f"""<!-- HMT NEW RELEASES START -->
{css}

<div class="hmt-filter-box">
  <label for="hmt-genre-filter">Filter by Genre</label>
  <select class="hmt-genre-select" id="hmt-genre-filter">
    <option value="">-- All Genres --</option>
{genre_options}
  </select>

  <label for="hmt-status-filter">Filter by Status</label>
  <select class="hmt-status-select" id="hmt-status-filter">
    <option value="">-- All Statuses --</option>
    <option value="verified">Verified</option>
    <option value="needs_review">Needs Review</option>
  </select>

  <div class="hmt-count" id="hmt-release-count">{recent_count} full-length albums in {year}</div>
</div>

<span class="hmt-sec">&#9654; Recently Released</span>
<p class="hmt-count">{recent_count} full-length albums in {year} &mdash; last updated {updated}</p>

{"".join(month_sections)}

{upcoming_section}

{js}
<!-- HMT NEW RELEASES END -->"""

    return html


def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(INPUT_CSV):
        log.error(f"Finner ikke {INPUT_CSV} — kjør 02_apply_genre_database.py først")
        return

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info(f"Leste {len(rows)} album fra {INPUT_CSV}")

    html = build_html(rows)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"HTML skrevet til {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
