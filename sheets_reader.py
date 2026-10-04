from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def get_credentials():

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if not creds or not creds.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


def get_sheets_service():

    creds = get_credentials()

    return build(
        "sheets",
        "v4",
        credentials=creds
    )


def read_sheet(sheet_id):

    service = get_sheets_service()

    result = (
        service
        .spreadsheets()
        .values()
        .get(
            spreadsheetId=sheet_id,
            range="3000 HR's with Profiles - Weekly Updates!A:D"
        )
        .execute()
    )

    return result.get("values", [])