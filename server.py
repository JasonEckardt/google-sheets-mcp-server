"""
Google Sheets MCP server.

Exposes a small set of tools for reading/writing a Google Sheet via a
service account, so an MCP-aware client (e.g. Claude) can edit cells,
append rows, and set dropdown (data validation) rules.

Run with:
    python server.py

Configuration (environment variables):
    GOOGLE_SERVICE_ACCOUNT_FILE   Path to the service account JSON key.
                                  Defaults to "service_account.json" in this folder.
    DEFAULT_SPREADSHEET_ID        Optional. Spreadsheet ID to use when a tool
                                  call omits spreadsheet_id.
"""

import os

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

load_dotenv()  # reads .env in this folder into os.environ, if present

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json"),
)
DEFAULT_SPREADSHEET_ID = os.environ.get("DEFAULT_SPREADSHEET_ID", "")

mcp = FastMCP("google-sheets")

_service = None


def get_service():
    """Lazily build (and cache) the Sheets API client."""
    global _service
    if _service is None:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(
                f"Service account key not found at {SERVICE_ACCOUNT_FILE}. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE or place service_account.json next to server.py."
            )
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _resolve_spreadsheet_id(spreadsheet_id: str | None) -> str:
    sid = spreadsheet_id or DEFAULT_SPREADSHEET_ID
    if not sid:
        raise ValueError(
            "No spreadsheet_id provided and DEFAULT_SPREADSHEET_ID is not set."
        )
    return sid


def _col_letter_to_index(column_letter: str) -> int:
    """Convert a column letter ("A", "Z", "AA", ...) to a 0-indexed column number."""
    col_index = 0
    for ch in column_letter.upper():
        col_index = col_index * 26 + (ord(ch) - ord("A") + 1)
    return col_index - 1


def _sheet_id_for_name(spreadsheet_id: str, sheet_name: str) -> int:
    """Look up the numeric sheetId for a given tab name."""
    meta = get_service().spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            return props.get("sheetId")
    raise ValueError(f"No tab named '{sheet_name}' found in spreadsheet {spreadsheet_id}.")


@mcp.tool()
def list_sheet_tabs(spreadsheet_id: str | None = None) -> list[dict]:
    """List the tabs (sheets) in a spreadsheet, with their names, IDs, and row/column counts.

    Args:
        spreadsheet_id: The spreadsheet's ID (from its URL). Uses DEFAULT_SPREADSHEET_ID if omitted.
    """
    sid = _resolve_spreadsheet_id(spreadsheet_id)
    try:
        meta = get_service().spreadsheets().get(spreadsheetId=sid).execute()
    except HttpError as e:
        raise RuntimeError(f"Failed to read spreadsheet metadata: {e}") from e

    tabs = []
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        grid = props.get("gridProperties", {})
        tabs.append(
            {
                "title": props.get("title"),
                "sheetId": props.get("sheetId"),
                "rowCount": grid.get("rowCount"),
                "columnCount": grid.get("columnCount"),
            }
        )
    return tabs


@mcp.tool()
def read_range(range_a1: str, spreadsheet_id: str | None = None) -> list[list[str]]:
    """Read cell values from a range.

    Args:
        range_a1: A1 notation range, e.g. "Sheet1!A1:O10".
        spreadsheet_id: The spreadsheet's ID. Uses DEFAULT_SPREADSHEET_ID if omitted.
    """
    sid = _resolve_spreadsheet_id(spreadsheet_id)
    try:
        result = (
            get_service()
            .spreadsheets()
            .values()
            .get(spreadsheetId=sid, range=range_a1)
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"Failed to read range {range_a1}: {e}") from e
    return result.get("values", [])


@mcp.tool()
def append_rows(
    range_a1: str,
    rows: list[list[str]],
    spreadsheet_id: str | None = None,
) -> dict:
    """Append one or more rows after the last row of data in a range.

    Args:
        range_a1: A1 notation range identifying the sheet/table to append to,
                  e.g. "Sheet1!A1" or "Sheet1!A:O".
        rows: List of rows, each row a list of cell values (strings/numbers).
        spreadsheet_id: The spreadsheet's ID. Uses DEFAULT_SPREADSHEET_ID if omitted.
    """
    sid = _resolve_spreadsheet_id(spreadsheet_id)
    body = {"values": rows}
    try:
        result = (
            get_service()
            .spreadsheets()
            .values()
            .append(
                spreadsheetId=sid,
                range=range_a1,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"Failed to append rows: {e}") from e
    return {
        "updatedRange": result.get("updates", {}).get("updatedRange"),
        "updatedRows": result.get("updates", {}).get("updatedRows"),
    }


@mcp.tool()
def update_range(
    range_a1: str,
    rows: list[list[str]],
    spreadsheet_id: str | None = None,
) -> dict:
    """Overwrite cell values in an exact range (does not shift/insert rows).

    Args:
        range_a1: A1 notation range to overwrite, e.g. "Sheet1!A2:O2".
        rows: List of rows, each row a list of cell values.
        spreadsheet_id: The spreadsheet's ID. Uses DEFAULT_SPREADSHEET_ID if omitted.
    """
    sid = _resolve_spreadsheet_id(spreadsheet_id)
    body = {"values": rows}
    try:
        result = (
            get_service()
            .spreadsheets()
            .values()
            .update(
                spreadsheetId=sid,
                range=range_a1,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"Failed to update range {range_a1}: {e}") from e
    return {"updatedRange": result.get("updatedRange"), "updatedCells": result.get("updatedCells")}


@mcp.tool()
def set_dropdown_validation(
    sheet_name: str,
    column_letter: str,
    options: list[str],
    start_row: int = 2,
    end_row: int = 1000,
    spreadsheet_id: str | None = None,
    strict: bool = True,
) -> str:
    """Add a dropdown (data validation list) to a column.

    Args:
        sheet_name: Tab name, e.g. "Sheet1".
        column_letter: Column to apply the dropdown to, e.g. "E".
        options: The allowed values shown in the dropdown,
                 e.g. ["Applied", "Interviewing", "Offer", "Rejected"].
        start_row: First row (1-indexed) to apply validation to. Default 2 (skips the header row).
        end_row: Last row (1-indexed, inclusive) to apply validation to. Default 1000.
        spreadsheet_id: The spreadsheet's ID. Uses DEFAULT_SPREADSHEET_ID if omitted.
        strict: If True, rejects input that isn't in the list. If False, only shows a warning.
    """
    sid = _resolve_spreadsheet_id(spreadsheet_id)
    numeric_sheet_id = _sheet_id_for_name(sid, sheet_name)

    col_index = _col_letter_to_index(column_letter)

    request_body = {
        "requests": [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": numeric_sheet_id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [{"userEnteredValue": opt} for opt in options],
                        },
                        "strict": strict,
                        "showCustomUi": True,
                    },
                }
            }
        ]
    }

    try:
        get_service().spreadsheets().batchUpdate(
            spreadsheetId=sid, body=request_body
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"Failed to set data validation: {e}") from e

    return (
        f"Dropdown added to {sheet_name}!{column_letter}{start_row}:{column_letter}{end_row} "
        f"with options: {', '.join(options)}"
    )


if __name__ == "__main__":
    # "stdio" works with Claude Desktop's local claude_desktop_config.json.
    # "streamable-http" is required for Cowork custom connectors, which only
    # accept remotely-hosted HTTP servers (see README for details).
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
