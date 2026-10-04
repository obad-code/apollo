"""Post a Short to your YouTube channel (YouTube Data API - free).

One-time setup:
    1. python -m pip install google-api-python-client google-auth-oauthlib
    2. In Google Cloud Console: enable "YouTube Data API v3", make an OAuth
       client of type "Desktop app", download its JSON and save it as
       Documents\\Apollo\\youtube_client.json
    3. The first upload opens your browser once to allow it; the sign-in is
       kept in %LOCALAPPDATA%\\Apollo\\youtube_token.json after that.

New, unverified Google projects can only post as Private until the app is
verified - SHORTS_PRIVACY=private|unlisted|public (public by default).
"""

import logging
import os

log = logging.getLogger("apollo.youtube_upload")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Apollo", "youtube_token.json")
PRIVACY = os.environ.get("SHORTS_PRIVACY") or "public"


def client_file():
    import files
    return os.path.join(files.root(), "youtube_client.json")


def read_notes(notes_path):
    """(title, description, tags) from the .txt beside the video."""
    try:
        with open(notes_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "Short", "#shorts", ["shorts"]
    parts = [p.strip() for p in text.split("\n\n")]
    title = (parts[0] or "Short")[:95]
    if "#shorts" not in title.lower():
        title = (title[:86] + " #shorts")
    tags = [w.lstrip("#") for w in text.split() if w.startswith("#")][:15]
    return title, text[:4900], tags


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not os.path.exists(client_file()):
            raise RuntimeError(f"YouTube is not set up: save the OAuth JSON as {client_file()}")
        creds = InstalledAppFlow.from_client_secrets_file(client_file(), SCOPES).run_local_server(port=0)
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def upload(video_path, notes_path=""):
    """Upload; returns the watch link."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        raise RuntimeError("Missing a library: run  python -m pip install google-api-python-client google-auth-oauthlib") from e
    title, description, tags = read_notes(notes_path)
    youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
    body = {"snippet": {"title": title, "description": description, "tags": tags, "categoryId": "24"},
            "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
    request = youtube.videos().insert(part="snippet,status", body=body,
                                      media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
    response = None
    while response is None:
        _status, response = request.next_chunk()
    link = f"https://youtube.com/shorts/{response['id']}"
    log.info("uploaded %s", link)
    return link
