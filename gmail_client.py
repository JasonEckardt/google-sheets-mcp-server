"""
Minimal Gmail read-only client for the job-tracker monitor.

Personal @gmail.com accounts can't grant a service account access to their
inbox (domain-wide delegation only works on Google Workspace domains), so
this uses a separate OAuth "Desktop app" client instead of the Sheets
service account.

First run: opens a browser for one-time consent, then caches a refresh
token in gmail_token.json so future (headless/scheduled) runs don't need
a browser.

Setup (see README.md for full steps):
    1. In Google Cloud Console, enable the Gmail API.
    2. Create an OAuth client ID of type "Desktop app".
    3. Download it and save as gmail_client_secret.json in this folder.
    4. Run this script's owning tool once interactively to complete consent.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.environ.get(
    "GMAIL_CLIENT_SECRET_FILE", os.path.join(HERE, "gmail_client_secret.json")
)
TOKEN_FILE = os.environ.get("GMAIL_TOKEN_FILE", os.path.join(HERE, "gmail_token.json"))

_gmail_service = None


def get_gmail_service():
    """Lazily build (and cache) an authenticated Gmail API client."""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                raise FileNotFoundError(
                    f"Gmail OAuth client secret not found at {CLIENT_SECRET_FILE}. "
                    "See README.md's Gmail setup section."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            # Requires an interactive run once (opens a browser). After this,
            # gmail_token.json holds a refresh token for unattended runs.
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def search_threads(query: str, max_results: int = 50) -> list[dict]:
    """Search Gmail threads matching a query. Returns thread stubs with an id."""
    service = get_gmail_service()
    threads = []
    page_token = None
    while True:
        resp = (
            service.users()
            .threads()
            .list(
                userId="me",
                q=query,
                maxResults=min(max_results - len(threads), 100),
                pageToken=page_token,
            )
            .execute()
        )
        threads.extend(resp.get("threads", []))
        page_token = resp.get("nextPageToken")
        if not page_token or len(threads) >= max_results:
            break
    return threads


def get_thread_detail(thread_id: str) -> dict:
    """Fetch a thread's first message: subject, sender, date, and snippet/body text."""
    service = get_gmail_service()
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    message = thread["messages"][0]
    headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}

    body_text = _extract_plain_text(message["payload"])

    return {
        "threadId": thread_id,
        "messageId": message["id"],
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "date": headers.get("Date", ""),
        "snippet": message.get("snippet", ""),
        "body": body_text,
        "link": f"https://mail.google.com/mail/u/0/#all/{thread_id}",
    }


def _extract_plain_text(payload: dict) -> str:
    """Best-effort plain-text extraction from a Gmail message payload."""
    import base64

    def decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return decode(payload["body"]["data"])

    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return decode(part["body"]["data"])
    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    return ""
