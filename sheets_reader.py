from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]
SHEET_ID = os.getenv('SHEET_ID')
RANGE = "3000+ HR's with Profiles - Weekly Updates!A:D" 

def read_sheet():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as t:
            t.write(creds.to_json())
    return build('sheets', 'v4', credentials=creds)

service = read_sheet()
sheet = service.spreadsheets()
result = sheet.values().get(
    spreadsheetId=SHEET_ID, range=RANGE).execute()
rows = result.get('values', [])
for row in rows:
    print(row)