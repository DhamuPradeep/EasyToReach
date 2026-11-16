import os
import json
import time
import uuid
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from database import get_connection

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email"

DEFAULT_HOST_EMAIL = os.environ.get("DEMO_NOTIFY_EMAIL", "jaisuriya17092002@gmail.com")

def get_google_config():
    """Returns (client_id, client_secret, host_email, is_connected)"""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

    conn = get_connection()
    row = conn.execute("SELECT * FROM google_calendar_tokens ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    if row:
        if not client_id and row["client_id"]:
            client_id = row["client_id"]
        if not client_secret and row["client_secret"]:
            client_secret = row["client_secret"]
        host_email = row["user_email"] or DEFAULT_HOST_EMAIL
        has_refresh_token = bool(row["refresh_token"])
        return client_id, client_secret, host_email, has_refresh_token

    return client_id, client_secret, DEFAULT_HOST_EMAIL, False

def save_google_credentials(client_id, client_secret):
    """Saves or updates client_id and client_secret in DB."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM google_calendar_tokens ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        conn.execute("UPDATE google_calendar_tokens SET client_id = ?, client_secret = ? WHERE id = ?",
                     (client_id, client_secret, row["id"]))
    else:
        conn.execute("INSERT INTO google_calendar_tokens (client_id, client_secret) VALUES (?, ?)",
                     (client_id, client_secret))
    conn.commit()
    conn.close()

def get_auth_url(redirect_uri):
    """Generates the Google OAuth 2.0 authorization URL."""
    client_id, _, _, _ = get_google_config()
    if not client_id:
        return None, "Google Client ID is not configured."

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent"
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return url, None

def exchange_code_for_tokens(code, redirect_uri):
    """Exchanges authorization code for access & refresh tokens."""
    client_id, client_secret, _, _ = get_google_config()
    if not client_id or not client_secret:
        return False, "Google Client ID or Secret missing."

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }).encode("utf-8")

    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return False, f"Token exchange failed: {e}"

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    expires_at = time.time() + expires_in

    # Fetch user's Gmail address
    user_email = DEFAULT_HOST_EMAIL
    try:
        info_req = urllib.request.Request(GOOGLE_USERINFO_URL)
        info_req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(info_req, timeout=10) as info_resp:
            user_info = json.loads(info_resp.read().decode("utf-8"))
            user_email = user_info.get("email") or user_email
    except Exception:
        pass

    conn = get_connection()
    row = conn.execute("SELECT id, refresh_token FROM google_calendar_tokens ORDER BY id DESC LIMIT 1").fetchone()
    # Google doesn't always return refresh_token on re-authorization if already granted
    final_refresh_token = refresh_token or (row["refresh_token"] if row else "")

    if row:
        conn.execute("""
            UPDATE google_calendar_tokens
            SET user_email = ?, access_token = ?, refresh_token = ?, expires_at = ?, client_id = ?, client_secret = ?
            WHERE id = ?
        """, (user_email, access_token, final_refresh_token, expires_at, client_id, client_secret, row["id"]))
    else:
        conn.execute("""
            INSERT INTO google_calendar_tokens (user_email, access_token, refresh_token, expires_at, client_id, client_secret)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_email, access_token, final_refresh_token, expires_at, client_id, client_secret))
    conn.commit()
    conn.close()

    return True, f"Connected to Google Calendar as {user_email}"

def get_valid_access_token():
    """Retrieves access token, automatically refreshing it if expired."""
    client_id, client_secret, _, _ = get_google_config()
    conn = get_connection()
    row = conn.execute("SELECT * FROM google_calendar_tokens ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    if not row or not row["refresh_token"]:
        return None

    # Check if current access token is valid
    if row["access_token"] and row["expires_at"] and time.time() < (row["expires_at"] - 60):
        return row["access_token"]

    # Refresh the token
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": row["refresh_token"],
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
        new_token = token_data.get("access_token")
        new_expires_at = time.time() + token_data.get("expires_in", 3600)

        conn = get_connection()
        conn.execute("UPDATE google_calendar_tokens SET access_token = ?, expires_at = ? WHERE id = ?",
                     (new_token, new_expires_at, row["id"]))
        conn.commit()
        conn.close()
        return new_token
    except Exception as e:
        print(f"❌ Failed to refresh Google Calendar token: {e}")
        return None

def create_meet_event(name, email, phone, shop, appt_date, appt_time):
    """
    Creates an event on Google Calendar with a real Google Meet video conference link,
    and invites both the host and visitor.
    Returns: {"success": True/False, "meet_link": str, "event_id": str, "error": str}
    """
    token = get_valid_access_token()
    if not token:
        return {"success": False, "error": "Google Calendar is not connected via OAuth"}

    _, _, host_email, _ = get_google_config()

    try:
        dt = datetime.strptime(f"{appt_date} {appt_time}", "%Y-%m-%d %I:%M %p")
    except Exception:
        dt = datetime.now() + timedelta(days=1)

    start_iso = dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    end_iso = (dt + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S+05:30")

    summary = f"EasyToReach Demo: {name} ({shop or 'Store'})"
    description = (
        f"EasyToReach WhatsApp CRM & Marketing Platform Demo\n\n"
        f"👤 Visitor Name: {name}\n"
        f"📱 WhatsApp: {phone}\n"
        f"📧 Email: {email}\n"
        f"🏪 Business: {shop or 'N/A'}\n"
        f"📅 Date & Time: {appt_date} at {appt_time} IST (30 Minutes)\n\n"
        f"This meeting was automatically scheduled via EasyToReach."
    )

    attendees = [{"email": email, "displayName": name}]
    if host_email and host_email != email:
        attendees.append({"email": host_email, "displayName": "EasyToReach Host"})

    payload = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        "attendees": attendees,
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 15}
            ]
        }
    }

    url = f"{GOOGLE_CALENDAR_API_URL}?conferenceDataVersion=1&sendUpdates=all"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            event = json.loads(resp.read().decode("utf-8"))

        meet_link = event.get("hangoutLink") or ""
        # If hangoutLink is inside conferenceData entryPoints
        if not meet_link and "conferenceData" in event:
            for ep in event["conferenceData"].get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri")
                    break

        print(f"🎉 Google Calendar event created! Meet link: {meet_link}")
        return {
            "success": True,
            "meet_link": meet_link,
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink")
        }
    except Exception as e:
        print(f"❌ Failed to create Google Calendar event: {e}")
        return {"success": False, "error": str(e)}

def generate_calendar_template_link(name, email, shop, appt_date, appt_time):
    """
    Fallback: Generates an instant 'Add to Google Calendar' template URL.
    Works with 1 click for any user without any API keys!
    """
    try:
        dt = datetime.strptime(f"{appt_date} {appt_time}", "%Y-%m-%d %I:%M %p")
    except Exception:
        dt = datetime.now() + timedelta(days=1)

    # Google Calendar template format: YYYYMMDDTHHMMSS
    start_utc = dt.strftime("%Y%m%dT%H%M%S")
    end_utc = (dt + timedelta(minutes=30)).strftime("%Y%m%dT%H%M%S")

    title = f"EasyToReach Demo: {name}"
    details = f"EasyToReach WhatsApp CRM Demo for {name} ({shop or 'Store'}). WhatsApp: {phone if 'phone' in locals() else ''}"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_utc}/{end_utc}",
        "details": details,
        "add": f"{email},{DEFAULT_HOST_EMAIL}"
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

