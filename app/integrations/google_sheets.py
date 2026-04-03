import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
RANGE_NAME = os.getenv("GOOGLE_SHEETS_RANGE", "availability!A:F")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service():
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )
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
    for idx, row in enumerate(rows, start=2):  # строка 2 = первая строка данных
        row += [""] * (len(headers) - len(row))
        slot = dict(zip(headers, row))
        slot["_row_number"] = idx
        slots.append(slot)

    return slots


def update_slot_status(row_number: int, new_status: str):
    service = get_sheets_service()
    sheet = service.spreadsheets()

    status_column_range = f"availability!E{row_number}"

    result = sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=status_column_range,
        valueInputOption="RAW",
        body={"values": [[new_status]]},
    ).execute()

    return result