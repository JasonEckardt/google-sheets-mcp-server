"""
Incremental job-response monitor.

Meant to be run on a schedule (Windows Task Scheduler / cron). Each run:
  1. Searches Gmail for messages that look like application responses,
     received since the last run (or the last LOOKBACK_DAYS on first run).
  2. Skips anything already processed (tracked in job_monitor_state.json)
     and anything that looks like a rejection.
  3. Appends new candidate rows to the Tracker sheet with Status =
     "Needs Review" so you can confirm/correct Company, Role, etc.
  4. Updates job_monitor_state.json so nothing is processed twice.

IMPORTANT LIMITATION: this script uses keyword matching, not a language
model. It cannot reliably tell "interview scheduled" from "still reviewing,
no news yet" the way a human (or Claude, reading the email) can -- it can
only catch obvious rejection phrasing. Review rows marked "Needs Review"
rather than trusting them blindly.

Run with:
    python monitor_job_responses.py

First run will open a browser once for Gmail consent (see README.md).
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

import gmail_client
import server

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "job_monitor_state.json")
SHEET_NAME = "Tracker"
LOOKBACK_DAYS = 45  # used only if there's no prior state file yet

SEARCH_QUERY = (
    '(interview OR "next steps" OR application OR "moving forward" OR offer '
    'OR "phone screen" OR "technical screen" OR assessment OR "schedule a call" '
    'OR "screening" OR "candidate pool") -in:sent'
)

# Phrases that indicate a rejection -- matched case-insensitively against
# subject + snippet + body. Keep this list updated as you spot new phrasing
# (recruiting emails are often templated per-company/ATS).
REJECTION_PATTERNS = [
    r"will not be moving forward",
    r"decided to move forward with (another|a different)",
    r"we(?:'|’)ve decided to pursue other candidates",
    r"pursue other candidates",
    r"not be (?:selected|proceeding)",
    r"regret to inform",
    r"unfortunately[,]? (?:we|your)",
    r"other candidates? whose",
    r"selected a(?:nother)? candidate",
    r"not moving forward with your application",
    # Ubisoft/SmartRecruiters-style French rejection phrasing seen in testing:
    r"ne donnerons pas suite",
    r"s(?:é|e)lectionner un autre profil",
    r"d(?:é|e)cid(?:é|e) de s(?:é|e)lectionner un autre",
]
_REJECTION_RE = re.compile("|".join(REJECTION_PATTERNS), re.IGNORECASE)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    return {"last_checked_epoch": int(cutoff.timestamp()), "processed_thread_ids": []}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_rejection(text: str) -> bool:
    return bool(_REJECTION_RE.search(text or ""))


def guess_company(from_header: str) -> str:
    display_name, email_addr = parseaddr(from_header)
    if display_name:
        # Trim common noise like "XYZ Careers" / "XYZ Recruiting" -> keep as-is,
        # since stripping too aggressively risks losing the real company name.
        return display_name.strip()
    domain = email_addr.split("@")[-1] if "@" in email_addr else email_addr
    # Drop common ATS/mailer subdomains so e.g. "notify.dayforce.com" -> "dayforce"
    parts = domain.split(".")
    return parts[-2].title() if len(parts) >= 2 else domain


def parse_date(date_header: str) -> str:
    try:
        return parsedate_to_datetime(date_header).date().isoformat()
    except Exception:
        return ""


def build_row(detail: dict) -> list[str]:
    company = guess_company(detail["from"])
    role = detail["subject"] or ""
    date_applied = parse_date(detail["date"])
    note = f"Auto-detected — please verify. {detail['snippet']} ({detail['link']})"
    # Matches the sheet's column order:
    # Company | Role/Title | Job Posting URL | Date Applied | Status |
    # Resume Version Used | Cover Letter Sent | Source/Referral | Contact Name |
    # Contact Email | Location/Remote | Salary Range | Next Follow-Up Date |
    # Interview Date(s) | Notes
    return [
        company,
        role,
        "",
        date_applied,
        "Needs Review",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        note,
    ]


def main():
    state = load_state()
    processed = set(state.get("processed_thread_ids", []))
    since = datetime.fromtimestamp(state["last_checked_epoch"], tz=timezone.utc)
    query = f'{SEARCH_QUERY} after:{since.strftime("%Y/%m/%d")}'

    print(f"Searching Gmail: {query}")
    threads = gmail_client.search_threads(query, max_results=100)
    print(f"Found {len(threads)} matching threads.")

    new_rows = []
    newly_processed = []
    skipped_rejections = 0
    skipped_already_seen = 0

    for t in threads:
        thread_id = t["id"]
        if thread_id in processed:
            skipped_already_seen += 1
            continue

        detail = gmail_client.get_thread_detail(thread_id)
        combined_text = f"{detail['subject']} {detail['snippet']} {detail['body']}"

        if is_rejection(combined_text):
            skipped_rejections += 1
            newly_processed.append(thread_id)
            continue

        new_rows.append(build_row(detail))
        newly_processed.append(thread_id)

    if new_rows:
        result = server.append_rows(range_a1=f"{SHEET_NAME}!A1", rows=new_rows)
        print(f"Appended {len(new_rows)} new row(s): {result}")
    else:
        print("No new (non-rejection) rows to add.")

    state["processed_thread_ids"] = list(processed | set(newly_processed))
    state["last_checked_epoch"] = int(datetime.now(timezone.utc).timestamp())
    save_state(state)

    print(
        f"Done. Skipped {skipped_rejections} rejection(s), "
        f"{skipped_already_seen} already-seen thread(s)."
    )


if __name__ == "__main__":
    main()
