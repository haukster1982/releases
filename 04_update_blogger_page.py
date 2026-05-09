"""
04_update_blogger_page.py
Oppdaterer kun området mellom markørene på Blogger-siden.

<!-- HMT NEW RELEASES START -->
...
<!-- HMT NEW RELEASES END -->

Miljøvariabler:
  BLOG_ID
  PAGE_ID
  BLOGGER_CLIENT_SECRET_JSON  (JSON-streng)
  BLOGGER_TOKEN_JSON          (JSON-streng, valgfri)
"""

import os
import json
import pickle
import logging
import tempfile
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BLOG_ID  = os.environ.get("BLOG_ID",  "6149994665074921300")
PAGE_ID  = os.environ.get("PAGE_ID",  "1326759201858341177")
SCOPES   = ["https://www.googleapis.com/auth/blogger"]

HTML_FILE     = "data/blogger_new_releases_block.html"
TOKEN_FILE    = "token.pickle"
CLIENT_SECRET = "client_secret.json"

START_MARKER = "<!-- HMT NEW RELEASES START -->"
END_MARKER   = "<!-- HMT NEW RELEASES END -->"


def get_credentials():
    """Henter Google-credentials fra fil eller miljøvariabel."""
    creds = None

    # GitHub Actions: bruk miljøvariabler
    token_json = os.environ.get("BLOGGER_TOKEN_JSON")
    if token_json:
        token_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Lokal: bruk token.pickle
    elif os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Lokal OAuth-flyt
            client_secret_json = os.environ.get("BLOGGER_CLIENT_SECRET_JSON")
            if client_secret_json:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                    tmp.write(client_secret_json)
                    tmp_path = tmp.name
                flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
                os.unlink(tmp_path)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)

    return creds


def replace_between_markers(existing_content, new_block):
    """Erstatter innhold mellom start/end-markørene."""
    if START_MARKER not in existing_content:
        raise ValueError(f"Finner ikke start-markør: {START_MARKER}")
    if END_MARKER not in existing_content:
        raise ValueError(f"Finner ikke slutt-markør: {END_MARKER}")

    start_idx = existing_content.index(START_MARKER)
    end_idx   = existing_content.index(END_MARKER) + len(END_MARKER)

    return existing_content[:start_idx] + new_block + existing_content[end_idx:]


def main():
    if not os.path.exists(HTML_FILE):
        log.error(f"Finner ikke {HTML_FILE} — kjør 03_build_blogger_html.py først")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        new_block = f.read()

    log.info("Kobler til Blogger API...")
    creds   = get_credentials()
    service = build("blogger", "v3", credentials=creds)

    log.info(f"Henter eksisterende Blogger-side (PAGE_ID={PAGE_ID})...")
    try:
        page = service.pages().get(blogId=BLOG_ID, pageId=PAGE_ID).execute()
    except Exception as e:
        log.error(f"Feil ved henting av side: {e}")
        return

    existing_content = page.get("content", "")
    page_title       = page.get("title", "New Metal Album Releases")

    if START_MARKER not in existing_content:
        log.error(f"Finner ikke '{START_MARKER}' på Blogger-siden.")
        log.error("Legg inn markørene manuelt på siden og kjør igjen.")
        log.error(f"  Start: {START_MARKER}")
        log.error(f"  Slutt: {END_MARKER}")
        return

    try:
        updated_content = replace_between_markers(existing_content, new_block)
    except ValueError as e:
        log.error(str(e))
        return

    log.info("Oppdaterer Blogger-siden...")
    try:
        service.pages().update(
            blogId=BLOG_ID,
            pageId=PAGE_ID,
            body={"title": page_title, "content": updated_content}
        ).execute()
        log.info("Blogger-siden oppdatert!")
    except Exception as e:
        log.error(f"Feil ved oppdatering: {e}")


if __name__ == "__main__":
    main()
