"""
Example: seed a job-application tracker sheet using server.py's tools directly.

The MCP tools in server.py are plain Python functions under the hood, so a
script can drive them without an MCP client. This one appends a few example
rows to a "Tracker" tab and adds a Status dropdown to column E.

All data below is fictional -- replace it with your own, or use it as a
template for other sheet layouts.

Run from the repo root (so `import server` resolves):
    python examples/seed_tracker.py

Requires .env and the service account key to be set up (see README.md).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import server  # noqa: E402

# Column order matches the sheet header row:
# Company | Role/Title | Job Posting URL | Date Applied | Status |
# Resume Version Used | Cover Letter Sent | Source/Referral | Contact Name |
# Contact Email | Location/Remote | Salary Range | Next Follow-Up Date |
# Interview Date(s) | Notes

ROWS = [
    [
        "Acme Robotics",
        "Computer Vision Engineer",
        "https://example.com/jobs/cv-engineer",
        "2026-07-01",
        "Applied",
        "ML/CV resume v3",
        "Yes",
        "Company site",
        "",
        "",
        "Hybrid",
        "",
        "",
        "",
        "Application confirmed via email.",
    ],
    [
        "Globex Corporation",
        "Site Reliability Engineer",
        "",
        "2026-06-25",
        "Screening",
        "Infra resume v2",
        "No",
        "Referral (J. Doe)",
        "Jane Doe",
        "jane.doe@example.com",
        "Remote",
        "",
        "2026-07-20",
        "",
        "Recruiter screen scheduled.",
    ],
    [
        "Initech",
        "Software Engineer, Backend",
        "",
        "2026-06-15",
        "Interviewing",
        "Backend resume v1",
        "Yes",
        "Job board",
        "",
        "",
        "On-site",
        "$120k-$140k",
        "",
        "2026-07-18",
        "Technical interview round 2.",
    ],
]

STATUS_OPTIONS = [
    "Needs Review",
    "Applied",
    "Screening",
    "Interview Scheduled",
    "Interviewing",
    "Offer",
    "Accepted",
    "Rejected",
    "Withdrawn",
]


def main():
    print("Appending rows...")
    result = server.append_rows(range_a1="Tracker!A1", rows=ROWS)
    print("  ->", result)

    print("Adding Status dropdown to column E...")
    msg = server.set_dropdown_validation(
        sheet_name="Tracker",
        column_letter="E",
        options=STATUS_OPTIONS,
        start_row=2,
        end_row=1000,
    )
    print("  ->", msg)

    print("Done.")


if __name__ == "__main__":
    main()
