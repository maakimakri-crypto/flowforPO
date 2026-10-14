# ProjectFlow — Integration Guide (NOT YET CONNECTED)

> ⚠️ **These integrations are NOT implemented. The code below is a plan stub.
> Do NOT run any of this without explicit user authorization for each account.**

---

## Google Drive Integration

### Purpose
Store and link procurement documents (POs, invoices, delivery evidence) in Google Drive instead of local SQLite blob storage.

### Authorization Flow
```python
# Requirements:
#   pip install google-auth google-auth-oauthlib google-api-python-client

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authorize_drive():
    """Launches browser for user authorization. Requires user confirmation."""
    creds = None
    token_path = 'data/drive_token.json'
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_FILE', 'google_credentials.json')

    if os.path.exists(token_path):
        import google.auth
        creds, _ = google.auth.load_credentials_from_file(token_path)

    if not creds or not creds.valid:
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(
                f"Missing {credentials_path}. "
                "Download from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON"
            )
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)
```

### Storage Functions (stub)
```python
def upload_to_drive(service, local_file_path, folder_id=None, filename=None):
    """Upload a file to Drive. Returns shareable link."""
    from googleapiclient.http import MediaFileUpload
    metadata = {'name': filename or os.path.basename(local_file_path)}
    if folder_id:
        metadata['parents'] = [folder_id]
    media = MediaFileUpload(local_file_path)
    file = service.files().create(body=metadata, media_body=media, fields='id,webViewLink').execute()
    return file['webViewLink']
```

### Steps to Connect (requires user action)
1. Create Google Cloud project at https://console.cloud.google.com
2. Enable Google Drive API
3. Configure OAuth consent screen (External, Testing)
4. Create OAuth 2.0 Client ID (Desktop app type)
5. Download `credentials.json` to project root
6. Run the authorization function — browser will open for user to confirm
7. `token.json` is stored locally; never commit to repo

---

## Gmail Integration

### Purpose
Send automated email notifications for:
- PO approval requests
- Invoice due date reminders
- Payment confirmations

### Authorization Flow
```python
# Uses same OAuth flow, different scope
MAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authorize_gmail():
    """Send emails on behalf of the authorized user."""
    # Same flow as Drive, different scope
    ...
    return build('gmail', 'v1', credentials=creds)

def send_email(service, to, subject, body):
    """Send a plain-text email."""
    import base64
    from email.message import EmailMessage
    msg = EmailMessage()
    msg['To'] = to
    msg['Subject'] = subject
    msg.set_content(body)
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(
        userId='me',
        body={'raw': encoded}
    ).execute()
```

### Steps to Connect (requires user action)
1. Enable Gmail API in same Google Cloud project
2. Add `https://www.googleapis.com/auth/gmail.send` scope to OAuth consent
3. Re-download credentials.json with new scope
4. Re-authorize to grant Gmail scope
5. Test sending from authorized account

---

## Security Notes
- OAuth tokens stored in `data/drive_token.json` and `data/gmail_token.json`
- `GOOGLE_CREDENTIALS_FILE` should point to downloaded credentials JSON
- Set `INTEGRATION_ENABLED=true` in `.env` to activate (disabled by default)
- Both integrations require the user to explicitly authorize each Google account
- Least-privilege: only `drive.file` (app-owned files) and `gmail.send` scopes
- Never log or expose OAuth tokens

---

## Next Steps (requires user authorization)
1. Create Google Cloud project → download credentials.json
2. Run authorization scripts (one-time per account)
3. Test in staging before enabling in production
4. Set `INTEGRATION_ENABLED=true` in `.env`
5. Commit only non-sensitive config — never `.env` or `*_token.json`
