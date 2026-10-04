from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.message import EmailMessage
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'  # ← add this
]

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as t:
            t.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def send_mail(to, subject, body, attachment_bytes=None, filename="resume.pdf"):
    """Send a plain-text email (optionally with a PDF attached) from your Gmail."""
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
 
    if attachment_bytes:
        msg.add_attachment(
            attachment_bytes,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )
 
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return (
        get_service()
        .users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )


# service = get_service()
# results = service.users().messages().list(
#     userId='me', maxResults=5).execute()
# for msg in results.get('messages', []):
#     print(msg['id'])

# with open("resume.pdf", "rb") as f:
#     resume_bytes = f.read()

# send_mail(
#     to="email@gmail.com",
#     subject="Applying for AI intern role",
#     body="Hi,\n\nPlease find my resume attached.\n\nThanks,\nYour Name",
#     attachment_bytes=resume_bytes,
#     filename="resume.pdf",
# )