import os
import re
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.auth

load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
RANGE_NAME = os.getenv("GOOGLE_SHEETS_RANGE", "availability!A:F")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service():
    if SERVICE_ACCOUNT_FILE:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES,
        )
    else:
        credentials, _ = google.auth.default(scopes=SCOPES)

    return build("sheets", "v4", credentials=credentials)


def read_slots():
    service = get_sheets_service()
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME
    ).execute()

    values = result.get("values", [])
    if not values:
        return []

    headers = values[0]
    rows = values[1:]

    slots = []
    for idx, row in enumerate(rows, start=2):
        row += [""] * (len(headers) - len(row))
        slot = dict(zip(headers, row))
        slot["_row_number"] = idx
        slots.append(slot)

    return slots


def get_sheet_id(sheet, sheet_name: str) -> int | None:
    metadata = sheet.get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets(properties(sheetId,title))",
    ).execute()

    for item in metadata.get("sheets", []):
        properties = item.get("properties", {})
        if properties.get("title") == sheet_name:
            return properties.get("sheetId")

    return None


def update_slot_status(row_number: int, new_status: str, notes: str = ""):
    service = get_sheets_service()
    sheet = service.spreadsheets()

    status_and_notes_range = f"availability!E{row_number}:F{row_number}"

    result = sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=status_and_notes_range,
        valueInputOption="RAW",
        body={"values": [[new_status, notes]]},
    ).execute()

    return result


def append_slot(values: list[str], highlight_yellow: bool = False) -> dict:
    service = get_sheets_service()
    sheet = service.spreadsheets()
    sheet_name = RANGE_NAME.split("!")[0]

    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()

    updated_range = (((result.get("updates") or {}).get("updatedRange")) or "").split("!")[-1]
    match = re.search(r"[A-Z]+(\d+):[A-Z]+(\d+)", updated_range)
    row_number = int(match.group(1)) if match else None

    if highlight_yellow and row_number:
        sheet_id = get_sheet_id(sheet, sheet_name)
        if sheet_id is None:
            return {
                "append_result": result,
                "row_number": row_number,
            }

        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_number - 1,
                                "endRowIndex": row_number,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {
                                        "red": 1.0,
                                        "green": 0.95,
                                        "blue": 0.6,
                                    }
                                }
                            },
                            "fields": "userEnteredFormat.backgroundColor",
                        }
                    }
                ]
            },
        ).execute()

    return {
        "append_result": result,
        "row_number": row_number,
    }
