import http.server
import socketserver
import json
import urllib.parse
import os
import re
import csv
import io
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from database import get_connection, init_db, sync_subscription_statuses
from whatsapp import send_whatsapp_message, render_template, format_phone_number
from scheduler import (check_and_send_birthday_wishes, check_and_send_miss_you_reminders,
                        check_and_send_points_reminders, start_background_scheduler,
                        DEFAULT_BIRTHDAY_TEMPLATE, DEFAULT_MISS_YOU_TEMPLATE, DEFAULT_POINTS_REMINDER_TEMPLATE)
import auth
import google_calendar

# ── Demo Notification Email Config ──────────────────────────────────────────
DEMO_NOTIFY_EMAIL = os.environ.get("DEMO_NOTIFY_EMAIL", "dhamupradeep17@gmail.com")
# Set GMAIL_APP_PASSWORD environment variable (16-char Google App Password)
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

def send_demo_notification_email(name, phone, shop, city, biz_type, customers, goal,
                                  appt_date="", appt_time="", email_addr=""):
    """Send demo booking emails (to admin and to user if configured). Runs asynchronously."""
    if not GMAIL_APP_PASSWORD:
        print("ℹ️  GMAIL_APP_PASSWORD not set. Booking saved in database; email notifications skipped.")
        return

    def _send():
        try:
            subject = f"📅 Demo Appointment: {name} · {appt_date} {appt_time}" if (appt_date and appt_time) else f"🎯 New Demo Request: {name} — {shop or 'New Lead'}"

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = DEMO_NOTIFY_EMAIL
            msg["To"]      = DEMO_NOTIFY_EMAIL

            appt_row = ""
            if appt_date and appt_time:
                appt_row = f"""<tr style="background:#f0fdf4;"><td style="padding:10px 8px;color:#166534;font-size:0.85rem;font-weight:700;">📅 Date & Time</td>
                    <td style="padding:10px 8px;font-weight:800;color:#14532d;">{appt_date} at {appt_time} IST (30 mins via Google Meet)</td></tr>"""
            if email_addr:
                appt_row += f"""<tr><td style="padding:8px 8px;color:#666;font-size:0.85rem;">📧 User Email</td>
                    <td style="padding:8px 8px;font-weight:700;color:#111;">{email_addr}</td></tr>"""

            html_body = f"""
<html><body style="font-family:'Segoe UI',Inter,sans-serif;background:#f4f4f4;padding:20px;">
  <div style="max-width:580px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#25d366,#008069);padding:24px 28px;color:#fff;">
      <h1 style="color:#fff;margin:0;font-size:1.3rem;">{"📅 Demo Appointment Confirmed" if appt_date else "🎯 New Demo Booking Request"}</h1>
      <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:0.88rem;">EasyToReach WhatsApp CRM Demo Lead</p>
    </div>
    <div style="padding:24px 28px;">
      <table style="width:100%;border-collapse:collapse;">
        {appt_row}
        <tr><td style="padding:8px 8px;color:#666;font-size:0.85rem;width:38%;">👤 Name</td>
            <td style="padding:8px 8px;font-weight:700;color:#111;">{name}</td></tr>
        <tr style="background:#f9fafb;"><td style="padding:8px 8px;color:#666;font-size:0.85rem;">📱 WhatsApp</td>
            <td style="padding:8px 8px;font-weight:700;color:#111;">{phone}</td></tr>
        <tr><td style="padding:8px 8px;color:#666;font-size:0.85rem;">🏪 Business / Shop</td>
            <td style="padding:8px 8px;font-weight:700;color:#111;">{shop or '—'}</td></tr>
        <tr style="background:#f9fafb;"><td style="padding:8px 8px;color:#666;font-size:0.85rem;">📍 City</td>
            <td style="padding:8px 8px;color:#333;">{city or '—'}</td></tr>
        <tr><td style="padding:8px 8px;color:#666;font-size:0.85rem;">🏷️ Category</td>
            <td style="padding:8px 8px;color:#333;">{biz_type or '—'}</td></tr>
        <tr style="background:#f9fafb;"><td style="padding:8px 8px;color:#666;font-size:0.85rem;">🎯 Goal / Notes</td>
            <td style="padding:8px 8px;color:#333;">{goal or '—'}</td></tr>
      </table>
      <div style="margin-top:22px;padding-top:18px;border-top:1px solid #eee;">
        <a href="https://wa.me/{phone.replace('+','').replace(' ','').replace('-','')}"
           style="display:inline-block;background:linear-gradient(135deg,#25d366,#008069);color:#fff;text-decoration:none;padding:12px 24px;border-radius:100px;font-weight:700;font-size:0.9rem;">
          💬 Chat with {name} on WhatsApp
        </a>
      </div>
    </div>
  </div>
</body></html>"""
            msg.attach(MIMEText(html_body, "html"))

            # Connect with STARTTLS (port 587) or SSL (port 465)
            server = None
            try:
                server = smtplib.SMTP("smtp.gmail.com", 587, timeout=12)
                server.ehlo()
                server.starttls()
                server.login(DEMO_NOTIFY_EMAIL, GMAIL_APP_PASSWORD)
            except Exception:
                # Fallback to SSL 465
                server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12)
                server.login(DEMO_NOTIFY_EMAIL, GMAIL_APP_PASSWORD)

            # 1. Send to Admin
            server.sendmail(DEMO_NOTIFY_EMAIL, DEMO_NOTIFY_EMAIL, msg.as_string())
            print(f"✅ Demo notification email sent to admin ({DEMO_NOTIFY_EMAIL}) for {name}")

            # 2. Also send confirmation to user if email provided
            if email_addr and "@" in email_addr and email_addr != DEMO_NOTIFY_EMAIL:
                try:
                    user_msg = MIMEMultipart("alternative")
                    user_msg["Subject"] = f"Your EasyToReach Demo is Confirmed: {appt_date} at {appt_time}" if (appt_date and appt_time) else "Thank you for requesting an EasyToReach Demo"
                    user_msg["From"] = DEMO_NOTIFY_EMAIL
                    user_msg["To"] = email_addr

                    user_html = f"""
<html><body style="font-family:'Segoe UI',Inter,sans-serif;background:#f4f4f4;padding:20px;">
  <div style="max-width:580px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#25d366,#008069);padding:24px 28px;color:#fff;">
      <h1 style="color:#fff;margin:0;font-size:1.3rem;">🎉 Demo Appointment Confirmed!</h1>
      <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:0.88rem;">EasyToReach WhatsApp Marketing & CRM</p>
    </div>
    <div style="padding:24px 28px;">
      <p style="font-size:0.95rem;color:#111;">Hi <strong>{name}</strong>,</p>
      <p style="color:#444;font-size:0.9rem;line-height:1.6;">Thank you for scheduling a live demo of EasyToReach WhatsApp CRM!</p>
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:16px;margin:16px 0;">
        <div style="font-size:0.88rem;color:#166534;font-weight:700;">📅 Scheduled Date & Time:</div>
        <div style="font-size:1.05rem;font-weight:800;color:#14532d;margin-top:4px;">{appt_date or 'Within 2 hours'} {('at ' + appt_time + ' IST') if appt_time else ''}</div>
        <div style="font-size:0.8rem;color:#666;margin-top:6px;">📹 Google Meet video link will be sent to your WhatsApp and email prior to the call.</div>
      </div>
      <p style="color:#555;font-size:0.88rem;">Need to reschedule or have questions? WhatsApp us directly anytime:</p>
      <a href="https://wa.me/918754702610?text=Hi!%20I%20scheduled%20a%20demo%20for%20{appt_date}"
         style="display:inline-block;background:linear-gradient(135deg,#25d366,#008069);color:#fff;text-decoration:none;padding:12px 24px;border-radius:100px;font-weight:700;font-size:0.88rem;margin-top:8px;">
        💬 Chat with our team on WhatsApp
      </a>
    </div>
  </div>
</body></html>"""
                    user_msg.attach(MIMEText(user_html, "html"))
                    server.sendmail(DEMO_NOTIFY_EMAIL, email_addr, user_msg.as_string())
                    print(f"✅ Demo confirmation email sent to customer ({email_addr})")
                except Exception as ue:
                    print(f"⚠️ Could not send customer confirmation email: {ue}")

            server.quit()
        except smtplib.SMTPAuthenticationError:
            print("❌ Gmail Authentication Failed: Invalid Google App Password.")
            print("   👉 Generate a 16-character Google App Password at: https://myaccount.google.com/apppasswords")
            print("   👉 Then run: export GMAIL_APP_PASSWORD='your-16-char-code'")
        except Exception as ex:
            print(f"❌ Failed to send demo email: {ex}")

    threading.Thread(target=_send, daemon=True).start()

PORT = 5050
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT_DIR, "static")

def match_flow_by_trigger_keyword(shop_id, incoming_text):
    """
    Checks incoming text message against active flows' trigger_keywords.
    Returns starting node and buttons if a keyword matches.
    """
    if not incoming_text:
        return None
    text_clean = incoming_text.lower().strip()
    words = set(re.findall(r'\b\w+\b', text_clean))
    conn = get_connection()
    flows = conn.execute("""
        SELECT id, name, trigger_keyword, flow_data_json 
        FROM chatbot_flows 
        WHERE shop_id = ? AND is_active = 1
        ORDER BY id DESC
    """, (shop_id,)).fetchall()
    conn.close()

    for f in flows:
        raw_kw = f["trigger_keyword"] or ""
        keywords = [k.strip().lower() for k in raw_kw.split(",") if k.strip()]
        matched = False
        for kw in keywords:
            if kw in words or (len(kw) > 3 and kw in text_clean):
                matched = True
                break
        if matched and f["flow_data_json"]:
            try:
                fdata = json.loads(f["flow_data_json"])
                nodes = fdata.get("nodes", [])
                q_node = next((n for n in nodes if n.get("type") in ("buttons", "reply_buttons")), None)
                if not q_node and nodes:
                    q_node = nodes[0]
                if q_node:
                    return {
                        "flow_id": f["id"],
                        "flow_name": f["name"],
                        "message": q_node.get("message") or q_node.get("title") or "",
                        "buttons": q_node.get("buttons") or []
                    }
            except Exception:
                pass
    return None

def resolve_custom_auto_reply(shop_id, cid, recipient_phone, button_id, button_title):
    """
    Finds the customized auto-reply for an interactive button press:
    1. First checks if the clicked button had a custom `auto_reply` field in the originating interactive message.
    2. Second checks the shop's global custom_auto_replies_json settings.
    3. Fallback to smart contextual responses.
    """
    conn = get_connection()
    phone_clean = recipient_phone.replace("+", "").replace(" ", "").replace("-", "")
    phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

    # 1. Per-button custom auto reply from the last interactive message
    last_interactive = conn.execute("""
        SELECT buttons_json FROM whatsapp_logs 
        WHERE shop_id = ? AND (
            recipient_phone = ? OR recipient_phone = ? OR recipient_phone LIKE ?
        ) AND direction = 'OUTBOUND' AND buttons_json != ''
        ORDER BY id DESC LIMIT 1
    """, (shop_id, recipient_phone, phone_clean, f"%{phone_ten}")).fetchone()

    if last_interactive and last_interactive["buttons_json"]:
        try:
            btns = json.loads(last_interactive["buttons_json"])
            for b in btns:
                if isinstance(b, dict):
                    b_id = b.get("id", "")
                    b_title = b.get("title", "")
                    b_reply = (b.get("auto_reply") or "").strip()
                    if (b_id and b_id == button_id) or (b_title and b_title.lower() == button_title.lower()):
                        if b_reply:
                            conn.close()
                            return b_reply
        except Exception:
            pass

    # 2. Visual Chatbot Flows (User-customized interactive graph flows)
    shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
    cust = conn.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone() if cid else None
    points = cust["loyalty_points"] if cust else 0
    cust_name = cust["name"] if cust else "Valued Customer"
    shop_name = (shop["sender_display_name"] or shop["name"]) if shop else "EasyToReach Store"

    b_clean = (button_title or button_id or "").strip().lower()

    try:
        flows = conn.execute("""
            SELECT flow_data_json FROM chatbot_flows 
            WHERE shop_id = ? AND is_active = 1
            ORDER BY id DESC
        """, (shop_id,)).fetchall()

        for f_row in flows:
            if not f_row["flow_data_json"]:
                continue
            fdata = json.loads(f_row["flow_data_json"])
            nodes_by_id = {n["id"]: n for n in fdata.get("nodes", []) if "id" in n}
            for n in fdata.get("nodes", []):
                if n.get("type") in ("buttons", "reply_buttons"):
                    for btn in n.get("buttons", []):
                        bid = (btn.get("id") or "").strip().lower()
                        btitle = (btn.get("title") or "").strip().lower()
                        matches = False
                        if bid and (bid == button_id.lower() or bid == b_clean):
                            matches = True
                        elif btitle and (btitle == b_clean or btitle in b_clean or b_clean in btitle):
                            matches = True
                        elif b_clean in ("yes", "y", "ha", "sure", "ok") and "yes" in btitle:
                            matches = True
                        elif b_clean in ("no", "n", "nah", "stop", "not now") and "no" in btitle:
                            matches = True

                        if matches:
                            target_id = btn.get("target")
                            target_node = nodes_by_id.get(target_id)
                            if target_node:
                                msg = (target_node.get("message") or target_node.get("content") or "").strip()
                                if msg:
                                    conn.close()
                                    return msg.replace("{name}", cust_name).replace("{points}", str(points)).replace("{shop}", shop_name)
    except Exception:
        pass

    # 3. Shop-level custom auto replies from shop settings
    shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
    cust = conn.execute("SELECT * FROM customers WHERE id = ?", (cid,)).fetchone() if cid else None
    conn.close()

    points = cust["loyalty_points"] if cust else 0
    cust_name = cust["name"] if cust else "Valued Customer"
    shop_name = (shop["sender_display_name"] or shop["name"]) if shop else "EasyToReach Store"

    custom_replies = {}
    if shop and shop["custom_auto_replies_json"]:
        try:
            custom_replies = json.loads(shop["custom_auto_replies_json"])
        except Exception:
            pass

    b_lower = (button_title or button_id or "").lower()

    if any(w in b_lower for w in ["plan", "catalog", "collection", "view", "see"]):
        if custom_replies.get("plans"):
            return custom_replies["plans"].replace("{name}", cust_name).replace("{shop}", shop_name)
        return f"🌸 Thank you for your interest! View our latest collection & festive catalog here: https://srilakshmisilks.in/festive-collections\nNeed assistance? Feel free to reply directly!"

    elif any(w in b_lower for w in ["point", "loyalty", "balance"]):
        if custom_replies.get("points"):
            return custom_replies["points"].replace("{points}", str(points)).replace("{name}", cust_name).replace("{shop}", shop_name)
        return f"✨ Namaste *{cust_name}*! Your current loyalty points balance is *{points} Points* (Worth ₹{points}). You can redeem this directly on your next billing at *{shop_name}*!"

    elif any(w in b_lower for w in ["birthday", "offer", "discount", "voucher"]):
        if custom_replies.get("offers"):
            return custom_replies["offers"].replace("{name}", cust_name).replace("{shop}", shop_name)
        return f"🎁 Special Privilege Offer: Use voucher code *FESTIVE15* at checkout for an instant 15% discount on sarees & garments!"

    elif any(w in b_lower for w in ["staff", "chat", "talk", "agent", "call", "help"]):
        if custom_replies.get("staff"):
            return custom_replies["staff"].replace("{name}", cust_name).replace("{shop}", shop_name)
        return f"Namaste *{cust_name}*! A showroom associate from *{shop_name}* has been notified and will reply directly in this chat shortly."

    elif any(w in b_lower for w in ["not interested", "stop", "unsubscribe", "no"]):
        if custom_replies.get("opt_out"):
            return custom_replies["opt_out"].replace("{name}", cust_name).replace("{shop}", shop_name)
        return f"Understood! We have noted your preference and will not disturb you regarding this offer. Have a wonderful day!"

    # General / Default
    if custom_replies.get("general"):
        return custom_replies["general"].replace("{name}", cust_name).replace("{shop}", shop_name)
    return f"Thank you for reaching out to *{shop_name}*! We have received your response and our team will get back to you shortly."

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    allow_reuse_address = True

class TextileCRMRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def get_current_user(self):
        """Extract and authenticate user from Authorization header, Cookie, or query param."""
        token = None
        auth_header = self.headers.get("Authorization")
        if auth_header:
            token = auth_header.strip()
        else:
            cookie_header = self.headers.get("Cookie", "")
            for part in cookie_header.split(";"):
                part = part.strip()
                if part.startswith("session_token="):
                    token = part.split("session_token=")[1].strip()
                    break
        if not token:
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            if "token" in q:
                token = q["token"][0]

        if token:
            return auth.get_user_from_token(token)
        return None

    def check_shop_access(self, user, requested_shop_id):
        """
        Verify if the authenticated user has access to requested_shop_id.
        Admins can access any shop. Shop owners can ONLY access their assigned shop.
        """
        if not user:
            return False  # Strict access control: No access without valid authenticated user session
        if user.get("role") == "admin":
            return True
        if str(user.get("shop_id")) == str(requested_shop_id):
            return True
        return False

    def parse_json_body(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            raw_body = self.rfile.read(content_len)
            try:
                return json.loads(raw_body.decode("utf-8"))
            except Exception:
                return {}
        return {}

    def send_json(self, data, status_code=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        user = self.get_current_user()

        # 0. API: Current Auth Session
        if path == "/api/auth/me":
            if user:
                return self.send_json({"authenticated": True, "user": user})
            return self.send_json({"authenticated": False, "user": None})

        # Google Calendar OAuth Callback & Status (No App Password required!)
        if path == "/api/google/oauth2callback":
            code = query.get("code", [""])[0]
            if not code:
                self.send_response(302)
                self.send_header("Location", "/book-demo?google_error=missing_code")
                self.end_headers()
                return
            host_header = self.headers.get("Host", f"localhost:{PORT}")
            scheme = "https" if "https" in self.headers.get("X-Forwarded-Proto", "") else "http"
            if "localhost" in host_header or "127.0.0.1" in host_header:
                redirect_uri = f"http://localhost:{PORT}/api/google/oauth2callback"
            else:
                redirect_uri = f"{scheme}://{host_header}/api/google/oauth2callback"
            ok, msg = google_calendar.exchange_code_for_tokens(code, redirect_uri)
            self.send_response(302)
            if ok:
                # Retroactively create Google Meet events for recent demo bookings that were waiting for connection
                try:
                    conn = get_connection()
                    pending = conn.execute("""
                        SELECT id, name, email, phone, shop_name, appointment_date, appointment_time
                        FROM demo_requests
                        WHERE appointment_date IS NOT NULL AND appointment_time IS NOT NULL 
                          AND email IS NOT NULL AND (meet_link IS NULL OR meet_link = '')
                        ORDER BY id DESC LIMIT 5
                    """).fetchall()
                    for req in pending:
                        try:
                            res = google_calendar.create_meet_event(
                                req["name"], req["email"], req["phone"], req["shop_name"],
                                req["appointment_date"], req["appointment_time"]
                            )
                            if res.get("success") and res.get("meet_link"):
                                conn.execute("UPDATE demo_requests SET meet_link = ? WHERE id = ?", (res["meet_link"], req["id"]))
                                conn.commit()
                                print(f"✅ Retroactively scheduled Google Meet for Demo #{req['id']} ({req['email']}): {res['meet_link']}")
                        except Exception as sync_err:
                            print(f"Sync error for Demo #{req['id']}: {sync_err}")
                    conn.close()
                except Exception as db_sync_err:
                    print(f"DB sync notice: {db_sync_err}")

                self.send_header("Location", "/book-demo?google_connected=1")
            else:
                self.send_header("Location", f"/book-demo?google_error={urllib.parse.quote(msg)}")
            self.end_headers()
            return

        if path == "/api/google/status":
            client_id, _, host_email, is_connected = google_calendar.get_google_config()
            return self.send_json({
                "connected": is_connected,
                "host_email": host_email,
                "client_id_configured": bool(client_id)
            })

        if path == "/api/google/connect":
            host_header = self.headers.get("Host", f"localhost:{PORT}")
            scheme = "https" if "https" in self.headers.get("X-Forwarded-Proto", "") else "http"
            if "localhost" in host_header or "127.0.0.1" in host_header:
                redirect_uri = f"http://localhost:{PORT}/api/google/oauth2callback"
            else:
                redirect_uri = f"{scheme}://{host_header}/api/google/oauth2callback"
            url, err = google_calendar.get_auth_url(redirect_uri)
            if err:
                return self.send_json({"error": err}, 400)
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()
            return

        # Meta WhatsApp Webhook Verification
        if path == "/api/webhooks/whatsapp":
            mode = query.get("hub.mode", [""])[0]
            token = query.get("hub.verify_token", [""])[0]
            challenge = query.get("hub.challenge", [""])[0]
            if mode == "subscribe":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(challenge.encode("utf-8"))
                return
            return self.send_json({"error": "Forbidden"}, 403)

        # Public: Booked demo slots for calendar availability & double-booking prevention
        if path == "/api/demo-booked-slots":
            conn = get_connection()
            rows = conn.execute("""
                SELECT appointment_date, appointment_time
                FROM demo_requests
                WHERE appointment_date IS NOT NULL 
                  AND appointment_date != ''
                  AND appointment_time IS NOT NULL 
                  AND appointment_time != ''
            """).fetchall()
            conn.close()
            booked_slots = {}
            for row in rows:
                d = row["appointment_date"]
                t = row["appointment_time"]
                if d not in booked_slots:
                    booked_slots[d] = []
                if t not in booked_slots[d]:
                    booked_slots[d].append(t)
            return self.send_json({"booked_slots": booked_slots})

        # Strict authentication required for all data and WhatsApp API routes
        if path.startswith("/api/"):
            if not user:
                return self.send_json({"error": "Authentication required. Please log in."}, 401)

        # 0b. API: Admin Summary (all shops overview)
        if path == "/api/admin/summary":
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            try:
                sync_subscription_statuses()
            except Exception:
                pass
            conn = get_connection()
            shops = [dict(r) for r in conn.execute("SELECT * FROM shops ORDER BY id ASC").fetchall()]
            summary = []
            totals = {
                "total_shops": len(shops),
                "total_messages": 0,
                "total_meta_amount": 0.0,
                "active_subscriptions": 0,
                "suspended_subscriptions": 0
            }
            today_str = datetime.now().strftime("%Y-%m-%d")

            for shop in shops:
                sid = shop["id"]
                msgs = conn.execute("SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id=?", (sid,)).fetchone()[0]
                meta_amount = float(msgs * 1.0) # 1 message = 1 rupee

                sub_plan = shop.get("subscription_plan") or "Standard Annual"
                sub_start = shop.get("subscription_start") or "2026-01-01"
                sub_end = shop.get("subscription_end") or "2026-12-31"
                is_expired = bool(sub_end and sub_end < today_str)
                status = "SUSPENDED" if (shop.get("status") == "SUSPENDED" or is_expired) else "ACTIVE"

                if status == "ACTIVE":
                    totals["active_subscriptions"] += 1
                else:
                    totals["suspended_subscriptions"] += 1

                summary.append({
                    "id": sid,
                    "name": shop.get("name", ""),
                    "city": shop.get("city", "") or "—",
                    "messages_sent": msgs,
                    "meta_amount": meta_amount,
                    "subscription_plan": sub_plan,
                    "subscription_start": sub_start,
                    "subscription_end": sub_end,
                    "status": status,
                    "is_expired": is_expired
                })
                totals["total_messages"] += msgs
                totals["total_meta_amount"] += meta_amount
            conn.close()
            return self.send_json({"shops": summary, "totals": totals})

        # 0c. API: Admin List Users
        if path == "/api/admin/users":
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            return self.send_json({"users": auth.list_users()})

        # 0d. API: Admin List Demo Requests
        elif path == "/api/admin/demo-requests":
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            conn = get_connection()
            rows = [dict(r) for r in conn.execute("SELECT * FROM demo_requests ORDER BY id DESC").fetchall()]
            conn.close()
            return self.send_json({"demo_requests": rows})

        # 1. API: List Shops
        elif path == "/api/shops":
            conn = get_connection()
            # If logged in as shop_owner, restrict to their assigned shop only
            if user.get("role") == "shop_owner" and user.get("shop_id"):
                shops = [dict(row) for row in conn.execute("SELECT * FROM shops WHERE id = ?", (user["shop_id"],)).fetchall()]
            else:
                shops = [dict(row) for row in conn.execute("SELECT * FROM shops ORDER BY id ASC").fetchall()]
            conn.close()
            return self.send_json({"shops": shops})

        # 2. API: Get Single Shop
        elif path.startswith("/api/shops/") and len(path.split("/")) == 4:
            shop_id = path.split("/")[3]
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
            conn.close()
            if shop:
                return self.send_json({"shop": dict(shop)})
            return self.send_json({"error": "Shop not found"}, 404)

        # 3. API: Dashboard Stats
        elif path == "/api/dashboard/stats":
            shop_id = query.get("shop_id", [None])[0]
            if shop_id and not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            
            conn = get_connection()
            now = datetime.now()
            today_mm_dd = now.strftime("%m-%d")

            cust_count = conn.execute("SELECT COUNT(*) FROM customers WHERE shop_id = ?", (shop_id,)).fetchone()[0]
            rev_total = conn.execute("SELECT SUM(net_amount) FROM purchases WHERE shop_id = ?", (shop_id,)).fetchone()[0] or 0.0
            points_issued = conn.execute("SELECT SUM(points_earned) FROM purchases WHERE shop_id = ?", (shop_id,)).fetchone()[0] or 0
            points_redeemed = conn.execute("SELECT SUM(points_redeemed) FROM purchases WHERE shop_id = ?", (shop_id,)).fetchone()[0] or 0
            msg_count = conn.execute("SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id = ?", (shop_id,)).fetchone()[0]

            # Today's birthdays count
            bday_count = conn.execute("""
                SELECT COUNT(*) FROM customers 
                WHERE shop_id = ? AND (
                    substr(date_of_birth, -5) = ? OR 
                    substr(date_of_birth, 6, 5) = ?
                )
            """, (shop_id, today_mm_dd, today_mm_dd)).fetchone()[0]

            conn.close()
            return self.send_json({
                "total_customers": cust_count,
                "total_revenue": round(rev_total, 2),
                "points_issued": points_issued,
                "points_redeemed": points_redeemed,
                "messages_dispatched": msg_count,
                "today_birthdays": bday_count
            })

        # 4. API: List / Filter Customers
        elif path == "/api/customers":
            shop_id = query.get("shop_id", [None])[0]
            if shop_id and not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            search = query.get("search", [""])[0].strip().lower()
            tag_filter = query.get("tag", [""])[0].strip()

            conn = get_connection()
            sql = "SELECT * FROM customers WHERE shop_id = ?"
            params = [shop_id]

            if search:
                sql += " AND (LOWER(name) LIKE ? OR phone LIKE ? OR LOWER(category_preference) LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

            if tag_filter:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag_filter}%")

            sql += " ORDER BY id DESC"
            customers = [dict(row) for row in conn.execute(sql, params).fetchall()]
            conn.close()

            # Parse tags JSON
            for c in customers:
                try:
                    c["tags"] = json.loads(c.get("tags") or "[]")
                except Exception:
                    c["tags"] = []

            return self.send_json({"customers": customers})

        # 5. API: Today & Upcoming Birthdays
        elif path == "/api/birthdays/today":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            now = datetime.now()
            today_mm_dd = now.strftime("%m-%d")
            current_year = now.year

            all_custs = conn.execute("SELECT * FROM customers WHERE shop_id = ?", (shop_id,)).fetchall()
            today_list = []
            upcoming_list = []

            for row in all_custs:
                cust = dict(row)
                dob = cust.get("date_of_birth") or ""
                if not dob or len(dob) < 5:
                    continue
                mm_dd = dob[-5:]

                # Check if wish already sent this year
                already_sent = conn.execute(
                    "SELECT id FROM birthday_logs WHERE shop_id = ? AND customer_id = ? AND year = ?",
                    (shop_id, cust["id"], current_year)
                ).fetchone() is not None
                cust["wish_sent_this_year"] = already_sent

                if mm_dd == today_mm_dd:
                    today_list.append(cust)
                else:
                    # Check next 7 days
                    try:
                        month, day = map(int, mm_dd.split("-"))
                        bday_date = datetime(current_year, month, day)
                        if 0 < (bday_date - now).days <= 7:
                            cust["days_until"] = (bday_date - now).days
                            upcoming_list.append(cust)
                    except Exception:
                        pass

            conn.close()
            return self.send_json({
                "today": today_list,
                "upcoming": upcoming_list,
                "date": now.strftime("%d %B %Y")
            })

        # 6. API: Campaigns List
        elif path == "/api/campaigns":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            campaigns = [dict(row) for row in conn.execute(
                "SELECT * FROM campaigns WHERE shop_id = ? ORDER BY id DESC", (shop_id,)
            ).fetchall()]
            conn.close()
            return self.send_json({"campaigns": campaigns})

        # 7. API: WhatsApp Message Logs (Default: Last 3 Days)
        elif path == "/api/whatsapp/logs":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            limit = int(query.get("limit", [50])[0])
            days_str = query.get("days", ["3"])[0]
            conn = get_connection()
            if days_str == "all":
                logs = [dict(row) for row in conn.execute(
                    "SELECT * FROM whatsapp_logs WHERE shop_id = ? ORDER BY id DESC LIMIT ?",
                    (shop_id, limit)
                ).fetchall()]
            else:
                try:
                    days = int(days_str)
                except ValueError:
                    days = 3
                logs = [dict(row) for row in conn.execute(
                    "SELECT * FROM whatsapp_logs WHERE shop_id = ? AND sent_at >= datetime('now', '-' || ? || ' days') ORDER BY id DESC LIMIT ?",
                    (shop_id, days, limit)
                ).fetchall()]
            conn.close()
            return self.send_json({"logs": logs, "days": days_str})

        # 8. API: Purchases / Customer ledger
        elif path.startswith("/api/customers/") and path.endswith("/purchases"):
            parts = path.split("/")
            cust_id = parts[3]
            conn = get_connection()
            # If user is shop owner, verify customer belongs to shop
            if user.get("role") == "shop_owner":
                cust = conn.execute("SELECT shop_id FROM customers WHERE id = ?", (cust_id,)).fetchone()
                if not cust or not self.check_shop_access(user, cust["shop_id"]):
                    conn.close()
                    return self.send_json({"error": "Unauthorized customer access"}, 403)

            purchases = [dict(row) for row in conn.execute(
                "SELECT * FROM purchases WHERE customer_id = ? ORDER BY id DESC", (cust_id,)
            ).fetchall()]
            conn.close()
            return self.send_json({"purchases": purchases})

        # 8b. API: Two-Way Conversations List
        elif path == "/api/conversations":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            rows = conn.execute("""
                SELECT 
                    w.recipient_phone,
                    w.customer_id,
                    COALESCE(c.name, w.recipient_name, 'Customer') as customer_name,
                    c.phone as registered_phone,
                    COALESCE(c.loyalty_points, 0) as total_points,
                    w.message_text as last_message,
                    w.sent_at as last_time,
                    w.direction as last_direction,
                    w.status as last_status,
                    (SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id = w.shop_id AND recipient_phone = w.recipient_phone) as total_messages,
                    (SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id = w.shop_id AND recipient_phone = w.recipient_phone AND direction = 'INBOUND' AND is_read = 0) as unread_count
                FROM whatsapp_logs w
                LEFT JOIN customers c ON (w.customer_id = c.id OR w.recipient_phone = c.phone)
                LEFT JOIN (
                    SELECT shop_id, 
                           CASE WHEN LENGTH(REPLACE(REPLACE(phone, '+', ''), ' ', '')) >= 10 
                                THEN SUBSTR(REPLACE(REPLACE(phone, '+', ''), ' ', ''), -10) 
                                ELSE phone END as phone_key,
                           MAX(hidden_at) as max_hidden_at
                    FROM hidden_conversations
                    GROUP BY shop_id, phone_key
                ) hc ON (
                    hc.shop_id = w.shop_id AND (
                        CASE WHEN LENGTH(REPLACE(REPLACE(w.recipient_phone, '+', ''), ' ', '')) >= 10 
                             THEN SUBSTR(REPLACE(REPLACE(w.recipient_phone, '+', ''), ' ', ''), -10) 
                             ELSE w.recipient_phone END = hc.phone_key
                    )
                )
                WHERE w.shop_id = ?
                  AND w.id IN (
                      SELECT MAX(id) FROM whatsapp_logs WHERE shop_id = ? GROUP BY recipient_phone
                  )
                  AND (
                      hc.max_hidden_at IS NULL 
                      OR w.sent_at > hc.max_hidden_at
                      OR (SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id = w.shop_id AND recipient_phone = w.recipient_phone AND direction = 'INBOUND' AND is_read = 0) > 0
                  )
                ORDER BY w.id DESC
            """, (shop_id, shop_id)).fetchall()
            conversations = [dict(r) for r in rows]

            # NOTE: We no longer auto-include customers without messages.
            # The conversation list only shows customers with actual message history.
            # Customers removed from the window stay hidden until a new inbound message arrives
            # or the shop owner adds them back via /api/conversations/unhide or "New Chat".
            conn.close()
            return self.send_json({"conversations": conversations})

        # 8c. API: Conversation Message History for Single Phone / Customer
        elif path == "/api/conversations/messages":
            shop_id = query.get("shop_id", [None])[0]
            phone = query.get("phone", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)
            if not phone:
                return self.send_json({"error": "phone required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
            phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

            conn = get_connection()
            # Mark all incoming messages for this customer as read
            conn.execute("""
                UPDATE whatsapp_logs 
                SET is_read = 1 
                WHERE shop_id = ? AND (
                    recipient_phone = ? OR recipient_phone = ? OR REPLACE(REPLACE(recipient_phone, '+', ''), ' ', '') = ? OR recipient_phone LIKE ?
                ) AND is_read = 0
            """, (shop_id, phone, phone_clean, phone_clean, f"%{phone_ten}"))
            conn.commit()

            customer = conn.execute("""
                SELECT * FROM customers 
                WHERE shop_id = ? AND (
                    phone = ? OR phone = ? OR REPLACE(REPLACE(phone, '+', ''), ' ', '') = ? OR phone LIKE ?
                )
            """, (shop_id, phone, phone_clean, phone_clean, f"%{phone_ten}")).fetchone()

            messages = conn.execute("""
                SELECT * FROM whatsapp_logs 
                WHERE shop_id = ? AND (
                    recipient_phone = ? OR recipient_phone = ? OR REPLACE(REPLACE(recipient_phone, '+', ''), ' ', '') = ? OR recipient_phone LIKE ?
                )
                ORDER BY id ASC
            """, (shop_id, phone, phone_clean, phone_clean, f"%{phone_ten}")).fetchall()
            conn.close()

            return self.send_json({
                "customer": dict(customer) if customer else None,
                "messages": [dict(m) for m in messages]
            })

        # 8d. API: Mark Conversation as Read
        elif path == "/api/conversations/mark-read":
            shop_id = query.get("shop_id", [None])[0]
            phone = query.get("phone", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            if shop_id and phone:
                phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
                phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean
                conn = get_connection()
                conn.execute("""
                    UPDATE whatsapp_logs 
                    SET is_read = 1 
                    WHERE shop_id = ? AND (
                        recipient_phone = ? OR recipient_phone = ? OR recipient_phone LIKE ?
                    ) AND is_read = 0
                """, (shop_id, phone, phone_clean, f"%{phone_ten}"))
                conn.commit()
                conn.close()
            return self.send_json({"success": True})

        # 8e. API: Customer search for conversations (search by name or phone)
        elif path == "/api/conversations/customer-search":
            shop_id = query.get("shop_id", [None])[0]
            q = (query.get("q", [""])[0] or "").strip().lower()
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)

            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            if q:
                customers = conn.execute("""
                    SELECT id, name, phone, loyalty_points
                    FROM customers
                    WHERE shop_id = ?
                      AND (LOWER(name) LIKE ? OR phone LIKE ? OR REPLACE(REPLACE(phone, '+', ''), ' ', '') LIKE ?)
                    ORDER BY name ASC
                    LIMIT 20
                """, (shop_id, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
            else:
                customers = conn.execute("""
                    SELECT id, name, phone, loyalty_points
                    FROM customers
                    WHERE shop_id = ?
                    ORDER BY name ASC
                    LIMIT 50
                """, (shop_id,)).fetchall()
            conn.close()
            return self.send_json({"customers": [dict(c) for c in customers]})

        # 8f. API: Trigger Miss-You Reminders
        elif path == "/api/reminders/miss-you":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            result = check_and_send_miss_you_reminders(shop_id)
            return self.send_json(result)

        # 8g. API: Trigger Points Reminders
        elif path == "/api/reminders/points":
            shop_id = query.get("shop_id", [None])[0]
            if user.get("role") == "shop_owner":
                shop_id = str(user["shop_id"])
            elif not shop_id:
                return self.send_json({"error": "shop_id required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            result = check_and_send_points_reminders(shop_id)
            return self.send_json(result)

        # 8h. API: Chatbot Interactive Flows (Visual Builder)
        elif path == "/api/chatbot-flows":
            shop_id = query.get("shop_id", [None])[0]
            if not shop_id and user and user.get("shop_id"):
                shop_id = user["shop_id"]
            if not shop_id:
                shop_id = 1
            conn = get_connection()
            flows = conn.execute("""
                SELECT id, shop_id, name, trigger_keyword, flow_data_json, is_active, updated_at
                FROM chatbot_flows
                WHERE shop_id = ?
                ORDER BY id ASC
            """, (shop_id,)).fetchall()
            conn.close()
            result = []
            for f in flows:
                f_dict = dict(f)
                try:
                    f_dict["flow_data"] = json.loads(f_dict["flow_data_json"])
                except Exception:
                    f_dict["flow_data"] = {}
                result.append(f_dict)
            return self.send_json({"success": True, "flows": result})

        elif path.startswith("/api/chatbot-flows/") and len(path.split("/")) == 4:
            flow_id = path.split("/")[3]
            conn = get_connection()
            f = conn.execute("SELECT * FROM chatbot_flows WHERE id = ?", (flow_id,)).fetchone()
            conn.close()
            if not f:
                return self.send_json({"error": "Flow not found"}, 404)
            f_dict = dict(f)
            try:
                f_dict["flow_data"] = json.loads(f_dict["flow_data_json"])
            except Exception:
                f_dict["flow_data"] = {}
            return self.send_json({"success": True, "flow": f_dict})

        # 9. Sample CSV download
        elif path == "/samples/customers_sample.csv":
            sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples", "customers_sample.csv")
            if os.path.exists(sample_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", "attachment; filename=customers_sample.csv")
                self.end_headers()
                with open(sample_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        # Serve Static Frontend Files & Landing Page
        clean_path = path.lstrip("/")
        if not clean_path or clean_path in ("home", "landing"):
            clean_path = "landing.html"
        elif clean_path in ("book-demo", "demo", "book_demo", "book-a-demo"):
            clean_path = "book-demo.html"
        elif clean_path in ("login", "auth", "signin"):
            clean_path = "login.html"
        elif clean_path in ("dashboard", "app", "crm", "index", "index.html"):
            # Strict protection: Only authenticated users (Admin or Shop Owner) can access the dashboard!
            if not user:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            clean_path = "index.html"

        # Check workspace root first, then static directory as fallback
        file_path = os.path.join(ROOT_DIR, clean_path)
        if not (os.path.exists(file_path) and os.path.isfile(file_path)):
            file_path = os.path.join(STATIC_DIR, clean_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            content_type = "application/octet-stream"
            if file_path.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif file_path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif file_path.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            elif file_path.endswith(".json"):
                content_type = "application/json"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif file_path.endswith(".svg"):
                content_type = "image/svg+xml"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.path.getsize(file_path)))
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return
        else:
            # Fallback to index.html for SPA routing (Requires Login)
            if not user:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(os.path.getsize(index_path)))
                self.end_headers()
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        self.send_error(404, "File not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = self.get_current_user()

        # Google Calendar Config & Disconnect
        if path == "/api/google/save-credentials":
            data = self.parse_json_body()
            client_id = data.get("client_id", "").strip()
            client_secret = data.get("client_secret", "").strip()
            if not client_id or not client_secret:
                return self.send_json({"error": "Google Client ID and Secret are required."}, 400)
            google_calendar.save_google_credentials(client_id, client_secret)
            return self.send_json({"success": True, "message": "Google credentials saved successfully."})

        elif path == "/api/google/disconnect":
            conn = get_connection()
            conn.execute("DELETE FROM google_calendar_tokens")
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "message": "Google Calendar disconnected."})

        # Public: Book a Demo request from landing page & /book-demo
        if path == "/api/demo-request":
            data = self.parse_json_body()
            name = (data.get("name") or "").strip()
            phone = (data.get("phone") or "").strip()
            email_addr = (data.get("email") or "").strip()
            shop = (data.get("shop") or "").strip()
            city = (data.get("city") or "").strip()
            biz_type = (data.get("biz_type") or "").strip()
            customers = (data.get("customers") or "").strip()
            goal = (data.get("goal") or "").strip()
            appt_date = (data.get("appointment_date") or "").strip()
            appt_time = (data.get("appointment_time") or "").strip()

            # Email, name, and phone are strictly required to properly confirm the appointment
            if not name or not phone or not email_addr or "@" not in email_addr:
                return self.send_json({"error": "Name, WhatsApp number, and a valid email address are required to book a demo."}, 400)

            # Prevent double-booking: check if slot is already reserved
            if appt_date and appt_time:
                check_conn = get_connection()
                existing = check_conn.execute("""
                    SELECT id FROM demo_requests
                    WHERE appointment_date = ? AND appointment_time = ?
                """, (appt_date, appt_time)).fetchone()
                check_conn.close()
                if existing:
                    return self.send_json({
                        "error": f"The slot on {appt_date} at {appt_time} is already booked. Please choose another time slot."
                    }, 409)

            if appt_date and appt_time and not goal:
                goal = f"Scheduled Demo: {appt_date} at {appt_time}"

            meet_link = ""
            # Google Calendar API: Automatically creates event with Google Meet link & emails invitations
            if appt_date and appt_time:
                try:
                    meet_res = google_calendar.create_meet_event(name, email_addr, phone, shop, appt_date, appt_time)
                    if meet_res.get("success"):
                        meet_link = meet_res.get("meet_link", "")
                except Exception as g_err:
                    print(f"ℹ️ Google Calendar event notice: {g_err}")

            cal_add_link = google_calendar.generate_calendar_template_link(name, email_addr, shop, appt_date, appt_time)

            conn = get_connection()
            try:
                conn.execute("""
                    INSERT INTO demo_requests (name, phone, email, shop_name, city, biz_type, customers, goal, appointment_date, appointment_time, meet_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, phone, email_addr, shop, city, biz_type, customers, goal, appt_date, appt_time, meet_link))
                conn.commit()
                print(f"📅 Demo request successfully saved for {name} ({email_addr}, {phone}) - {appt_date} {appt_time}")
            except Exception as e:
                print(f"Error saving demo request: {e}")
            finally:
                conn.close()

            # Send fallback email notification if SMTP is configured
            send_demo_notification_email(name, phone, shop, city, biz_type, customers, goal,
                                         appt_date=appt_date, appt_time=appt_time, email_addr=email_addr)

            return self.send_json({
                "success": True,
                "message": "Demo booked successfully! A confirmation has been registered for your slot.",
                "meet_link": meet_link,
                "calendar_add_url": cal_add_link,
                "booking": {
                    "name": name,
                    "email": email_addr,
                    "appointment_date": appt_date,
                    "appointment_time": appt_time,
                    "meet_link": meet_link
                }
            })

        # 0. API: User Login
        elif path == "/api/auth/login":
            data = self.parse_json_body()
            username = data.get("username", "").strip()
            password = data.get("password", "").strip()
            if not username or not password:
                return self.send_json({"error": "Username and password required"}, 400)

            auth_user = auth.authenticate_user(username, password)
            if not auth_user:
                return self.send_json({"error": "Invalid username or password"}, 401)
            if isinstance(auth_user, dict) and "error" in auth_user:
                return self.send_json({"error": auth_user["error"]}, 403)

            token, expires_at = auth.create_session(auth_user)
            res_body = json.dumps({
                "success": True,
                "token": token,
                "user": auth_user,
                "expires_at": expires_at
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_body)))
            self.send_header("Set-Cookie", f"session_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={7*86400}")
            self.end_headers()
            self.wfile.write(res_body)
            return

        # 0b. API: User Logout
        elif path == "/api/auth/logout":
            token = None
            auth_header = self.headers.get("Authorization")
            if auth_header:
                token = auth_header.strip()
            if not token:
                cookie_header = self.headers.get("Cookie", "")
                for part in cookie_header.split(";"):
                    part = part.strip()
                    if part.startswith("session_token="):
                        token = part.split("session_token=")[1].strip()
                        break
            if token:
                auth.delete_session(token)

            res_body = json.dumps({"success": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_body)))
            self.send_header("Set-Cookie", "session_token=; Path=/; HttpOnly; Max-Age=0")
            self.end_headers()
            self.wfile.write(res_body)
            return

        # Strict authentication check for all data, billing, and WhatsApp messaging APIs
        if path.startswith("/api/") and path not in ("/api/webhooks/customer", "/api/webhooks/whatsapp"):
            if not user:
                return self.send_json({"error": "Authentication required. Please log in to perform this action."}, 401)

        # 0c. API: Admin Create Shop Owner Account
        if path == "/api/admin/users":
            if not user or user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)

            data = self.parse_json_body()
            username = data.get("username", "").strip()
            email = data.get("email", "").strip()
            password = data.get("password", "").strip()
            shop_id = data.get("shop_id")
            full_name = data.get("full_name", "").strip()
            phone = data.get("phone", "").strip()

            if not username or not email or not password or not shop_id or not full_name:
                return self.send_json({"error": "username, email, password, shop_id, and full_name are required"}, 400)

            res = auth.create_shop_owner_user(username, email, password, int(shop_id), full_name, phone)
            if not res.get("success"):
                return self.send_json(res, 400)
            return self.send_json(res, 201)

        # 1. API: Create Shop (New Tenant) — Admin Only
        elif path == "/api/shops":
            if user and user.get("role") != "admin":
                return self.send_json({"error": "Only Platform Admins can register new shops"}, 403)

            data = self.parse_json_body()
            name = data.get("name", "").strip()
            if not name:
                return self.send_json({"error": "Shop name is required"}, 400)

            slug = data.get("slug") or name.lower().replace(" ", "-").replace("&", "and")
            sub_plan = data.get("subscription_plan") or "Standard Annual"
            sub_start = data.get("subscription_start") or datetime.now().strftime("%Y-%m-%d")
            sub_end = data.get("subscription_end") or (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
            status = "ACTIVE"
            if sub_end < datetime.now().strftime("%Y-%m-%d"):
                status = "SUSPENDED"

            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT INTO shops (
                    name, slug, tagline, phone, email, address, city,
                    sender_display_name, points_per_100_spent, point_redeem_value_inr,
                    birthday_discount_percent, birthday_offer_validity_days,
                    subscription_plan, subscription_start, subscription_end, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, slug, data.get("tagline", ""), data.get("phone", ""),
                    data.get("email", ""), data.get("address", ""), data.get("city", ""),
                    data.get("sender_display_name") or name,
                    float(data.get("points_per_100_spent", 5.0)),
                    float(data.get("point_redeem_value_inr", 1.0)),
                    int(data.get("birthday_discount_percent", 15)),
                    int(data.get("birthday_offer_validity_days", 7)),
                    sub_plan, sub_start, sub_end, status
                ))
                conn.commit()
                new_id = cursor.lastrowid
                conn.close()
                return self.send_json({"success": True, "shop_id": new_id}, 201)
            except Exception as e:
                conn.close()
                return self.send_json({"error": f"Failed to create shop: {str(e)}"}, 400)

        # 1b. API: Update Store Subscription — Admin Only
        elif path == "/api/admin/shops/subscription":
            if user and user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            data = self.parse_json_body()
            shop_id = data.get("shop_id")
            if not shop_id:
                return self.send_json({"error": "shop_id is required"}, 400)

            conn = get_connection()
            shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
            if not shop:
                conn.close()
                return self.send_json({"error": "Shop not found"}, 404)

            plan = data.get("subscription_plan") or shop["subscription_plan"] or "Standard Annual"
            start_date = data.get("subscription_start") or shop["subscription_start"] or "2026-01-01"
            end_date = data.get("subscription_end") or shop["subscription_end"] or "2026-12-31"
            status = data.get("status")

            today_str = datetime.now().strftime("%Y-%m-%d")
            if end_date < today_str:
                status = "SUSPENDED"
            elif not status:
                status = "ACTIVE"

            conn.execute("""
                UPDATE shops
                SET subscription_plan = ?, subscription_start = ?, subscription_end = ?, status = ?
                WHERE id = ?
            """, (plan, start_date, end_date, status, shop_id))

            # Automatically sync user accounts for this store
            conn.execute("UPDATE users SET status = ? WHERE shop_id = ?", (status, shop_id))
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "status": status, "subscription_end": end_date})

        # 2. API: Create Customer
        elif path == "/api/customers":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot add customers to another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            name = data.get("name", "").strip()
            phone = data.get("phone", "").strip()

            if not shop_id or not name or not phone:
                return self.send_json({"error": "shop_id, name, and phone are required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            tags = data.get("tags", ["Regular"])
            tags_json = json.dumps(tags) if isinstance(tags, list) else json.dumps([str(tags)])

            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT INTO customers (
                    shop_id, name, phone, date_of_birth, anniversary_date,
                    gender, category_preference, loyalty_points, notes, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shop_id, name, phone, data.get("date_of_birth", ""),
                    data.get("anniversary_date", ""), data.get("gender", "Female"),
                    data.get("category_preference", "Silk Sarees"),
                    int(data.get("loyalty_points", 0)),
                    data.get("notes", ""), tags_json
                ))
                conn.commit()
                cust_id = cursor.lastrowid

                # Optional: Send Instant WhatsApp Welcome Message
                if data.get("send_welcome_whatsapp", True):
                    shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
                    shop_name = shop["sender_display_name"] or shop["name"]
                    welcome_msg = (
                        f"Namaste *{name}*! 🙏✨\n\n"
                        f"Welcome to the *{shop_name}* family!\n"
                        f"We are delighted to have you with us. As a privileged customer, "
                        f"you will receive special festive offers, new silk collection updates, "
                        f"and rewards on your purchases.\n\n"
                        f"🎁 *Your Starting Loyalty Balance:* {int(data.get('loyalty_points', 0))} Points\n\n"
                        f"📍 Visit our showroom: {shop['address'] or shop['city']}\n"
                        f"Have a wonderful day!"
                    )
                    send_whatsapp_message(
                        shop_id=shop_id,
                        customer_id=cust_id,
                        recipient_phone=phone,
                        message_text=welcome_msg,
                        message_type="WELCOME",
                        customer_name=name
                    )

                conn.close()
                return self.send_json({"success": True, "customer_id": cust_id}, 201)
            except Exception as e:
                conn.close()
                return self.send_json({"error": f"Failed to save customer: {str(e)}"}, 400)

        # 3. API: Bulk Import Customers CSV
        elif path == "/api/customers/import-csv":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot import customers into another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            csv_content = data.get("csv_content", "").strip()

            if not shop_id or not csv_content:
                return self.send_json({"error": "shop_id and csv_content required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            cursor = conn.cursor()
            imported_count = 0
            errors = []

            reader = csv.DictReader(io.StringIO(csv_content))
            for i, row in enumerate(reader):
                name = row.get("name", "").strip()
                phone = row.get("phone", "").strip()
                if not name or not phone:
                    continue

                dob = row.get("date_of_birth", "").strip()
                anniversary = row.get("anniversary_date", "").strip()
                gender = row.get("gender", "Female").strip()
                pref = row.get("category_preference", "Silk Sarees").strip()
                points = int(row.get("loyalty_points", 0) or 0)
                notes = row.get("notes", "").strip()
                tags_raw = row.get("tags", "Regular").split(",")
                tags_clean = [t.strip() for t in tags_raw if t.strip()]

                try:
                    cursor.execute("""
                    INSERT INTO customers (
                        shop_id, name, phone, date_of_birth, anniversary_date,
                        gender, category_preference, loyalty_points, notes, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(shop_id, phone) DO UPDATE SET
                        name = excluded.name,
                        date_of_birth = COALESCE(excluded.date_of_birth, customers.date_of_birth),
                        anniversary_date = COALESCE(excluded.anniversary_date, customers.anniversary_date),
                        category_preference = excluded.category_preference,
                        notes = excluded.notes
                    """, (
                        shop_id, name, phone, dob, anniversary,
                        gender, pref, points, notes, json.dumps(tags_clean)
                    ))
                    imported_count += 1
                except Exception as ex:
                    errors.append(f"Row {i+1} ({name}): {str(ex)}")

            conn.commit()
            conn.close()
            return self.send_json({"success": True, "imported_count": imported_count, "errors": errors})

        # 4. API: Record Purchase & Issue Loyalty Points
        elif path == "/api/billing/purchase":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot record purchases for another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            customer_id = data.get("customer_id")
            bill_amount = float(data.get("bill_amount", 0.0))
            discount_amount = float(data.get("discount_amount", 0.0))
            points_to_redeem = int(data.get("points_to_redeem", 0))
            items_summary = data.get("items_summary", "Textile & Garment Purchase")

            if not shop_id or not customer_id or bill_amount <= 0:
                return self.send_json({"error": "Valid shop_id, customer_id and bill_amount required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            cursor = conn.cursor()

            shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
            cust = conn.execute("SELECT * FROM customers WHERE id = ? AND shop_id = ?", (customer_id, shop_id)).fetchone()

            if not shop or not cust:
                conn.close()
                return self.send_json({"error": "Shop or Customer not found"}, 404)

            # Calculate points discount if redeemed
            redeem_val_per_pt = shop["point_redeem_value_inr"] or 1.0
            redeemed_discount = points_to_redeem * redeem_val_per_pt

            net_amount = max(0.0, bill_amount - discount_amount - redeemed_discount)

            # Calculate points earned (e.g. 5 points per 100 spent)
            pts_per_100 = shop["points_per_100_spent"] or 5.0
            points_earned = int((net_amount / 100.0) * pts_per_100)

            # Update customer balance
            current_points = cust["loyalty_points"]
            new_points_balance = max(0, current_points - points_to_redeem + points_earned)
            new_total_spent = (cust["total_spent"] or 0.0) + net_amount
            new_visits = (cust["total_visits"] or 0) + 1
            now_str = datetime.now().strftime("%Y-%m-%d")

            invoice_no = data.get("invoice_no") or f"INV-{datetime.now().strftime('%y%m%d')}-{cursor.execute('SELECT COUNT(*)+1 FROM purchases').fetchone()[0]:03d}"

            # Insert purchase
            cursor.execute("""
            INSERT INTO purchases (
                shop_id, customer_id, invoice_no, bill_amount, discount_amount,
                net_amount, points_earned, points_redeemed, items_summary, whatsapp_notified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                shop_id, customer_id, invoice_no, bill_amount,
                discount_amount + redeemed_discount, net_amount,
                points_earned, points_to_redeem, items_summary
            ))

            # Update customer record
            cursor.execute("""
            UPDATE customers SET
                loyalty_points = ?,
                total_spent = ?,
                total_visits = ?,
                last_visit_date = ?
            WHERE id = ?
            """, (new_points_balance, new_total_spent, new_visits, now_str, customer_id))

            conn.commit()

            # Automatic WhatsApp Digital Receipt & Points Update
            shop_name = shop["sender_display_name"] or shop["name"]
            receipt_msg = (
                f"Namaste *{cust['name']}*! 🛍️✨\n\n"
                f"Thank you for shopping at *{shop_name}*!\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🧾 *DIGITAL RECEIPT*\n"
                f"📌 *Invoice:* {invoice_no}\n"
                f"👗 *Items:* {items_summary}\n"
                f"💵 *Net Paid:* ₹{net_amount:,.2f}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"⭐ *Points Earned Today:* +{points_earned} pts\n"
            )
            if points_to_redeem > 0:
                receipt_msg += f"🎟️ *Points Redeemed:* -{points_to_redeem} pts (-₹{redeemed_discount})\n"

            receipt_msg += (
                f"🎁 *Total Loyalty Points Balance:* *{new_points_balance} Points*\n"
                f"💡 (1 Point = ₹{int(redeem_val_per_pt)} instant discount on next purchase)\n\n"
                f"We look forward to welcoming you again!\n"
                f"📍 *{shop_name}*"
            )

            receipt_buttons = [
                {"id": "btn_check_points", "title": "Check Balance"},
                {"id": "btn_view_offers", "title": "View Offers"},
                {"id": "btn_contact_store", "title": "Talk to Staff"}
            ]

            send_res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=customer_id,
                recipient_phone=cust["phone"],
                message_text=receipt_msg,
                message_type="POINTS_RECEIPT",
                customer_name=cust["name"],
                buttons=receipt_buttons,
                direction="OUTBOUND"
            )

            conn.close()
            return self.send_json({
                "success": True,
                "invoice_no": invoice_no,
                "net_amount": net_amount,
                "points_earned": points_earned,
                "new_points_balance": new_points_balance,
                "whatsapp_status": send_res.get("status")
            })

        # 5. API: Trigger Birthday Wishes Dispatch (Manual or Cron)
        elif path == "/api/birthdays/send":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot send birthday wishes for another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            result = check_and_send_birthday_wishes(shop_id)
            return self.send_json({"success": True, "result": result})

        # 6. API: Broadcast Campaign (Festival Offers / New Collections)
        elif path == "/api/campaigns/broadcast":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot broadcast campaigns for another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            title = data.get("title", "").strip()
            campaign_type = data.get("type", "FESTIVAL_OFFER")
            festival_name = data.get("festival_name", "")
            message_body = data.get("message_body", "").strip()
            media_url = data.get("media_url", "").strip()
            target_filter = data.get("target_filter", "ALL")
            gender_filter = data.get("gender_filter", "ALL")
            age_filter = data.get("age_filter", "ALL")
            points_filter = data.get("points_filter", "ALL")

            if not shop_id or not title or not message_body:
                return self.send_json({"error": "shop_id, title, and message_body required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            conn = get_connection()
            shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
            if not shop:
                conn.close()
                return self.send_json({"error": "Shop not found"}, 404)

            shop_name = shop["sender_display_name"] or shop["name"]

            # Build query combining target audience tags, gender, loyalty points, and age
            sql = "SELECT * FROM customers WHERE shop_id = ?"
            params = [shop_id]

            # 1. Gender filter
            if gender_filter in ("Female", "Male"):
                sql += " AND gender = ?"
                params.append(gender_filter)
            elif gender_filter == "Other":
                sql += " AND (gender = 'Other' OR (gender != 'Female' AND gender != 'Male'))"

            # 2. Loyalty points filter
            if points_filter == "ABOVE_0":
                sql += " AND loyalty_points > 0"
            elif points_filter == "ABOVE_50":
                sql += " AND loyalty_points >= 50"
            elif points_filter == "ABOVE_100":
                sql += " AND loyalty_points >= 100"
            elif points_filter == "ABOVE_500":
                sql += " AND loyalty_points >= 500"
            elif points_filter == "ZERO":
                sql += " AND (loyalty_points = 0 OR loyalty_points IS NULL)"

            # 3. Target audience tags (VIP, First Time Buyer, Regular, Frequent Buyer, Wedding)
            if target_filter == "VIP":
                sql += " AND (tags LIKE '%VIP%' OR tags LIKE '%vip%')"
            elif target_filter in ("FIRST_TIME", "FIRST_TIME_BUYER"):
                sql += " AND (tags LIKE '%First Time%' OR tags LIKE '%first time%' OR total_visits <= 1)"
            elif target_filter == "REGULAR":
                sql += " AND (tags LIKE '%Regular%' OR tags LIKE '%regular%')"
            elif target_filter in ("FREQUENT", "FREQUENT_BUYER"):
                sql += " AND (tags LIKE '%Frequent%' OR tags LIKE '%frequent%')"
            elif target_filter in ("WEDDING", "WEDDING_SHOPPER"):
                sql += " AND (tags LIKE '%Wedding%' OR tags LIKE '%wedding%' OR tags LIKE '%Bridal%' OR tags LIKE '%bridal%')"

            candidates = conn.execute(sql, params).fetchall()

            # 4. Age filter (<5, 5-18, 18-30, 30-50, 50+)
            recipients = []
            now = datetime.now()
            for cust in candidates:
                dob = cust["date_of_birth"]
                age = None
                if dob and len(str(dob).strip()) >= 4:
                    try:
                        parts = str(dob).strip().split("-")
                        y = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 else 1
                        d = int(parts[2]) if len(parts) > 2 else 1
                        age = now.year - y - ((now.month, now.day) < (m, d))
                    except Exception:
                        pass

                if age_filter == "UNDER_5":
                    if age is not None and age < 5:
                        recipients.append(cust)
                elif age_filter == "5_TO_18":
                    if age is not None and 5 <= age <= 18:
                        recipients.append(cust)
                elif age_filter == "18_TO_30":
                    if age is not None and 18 <= age <= 30:
                        recipients.append(cust)
                elif age_filter == "30_TO_50":
                    if age is not None and 30 <= age <= 50:
                        recipients.append(cust)
                elif age_filter == "50_PLUS":
                    if age is not None and age >= 50:
                        recipients.append(cust)
                else: # ALL
                    recipients.append(cust)

            total_recipients = len(recipients)
            sent_count = 0

            # Create readable summary of applied filters for campaign history
            tag_names = {
                "VIP": "VIP", "FIRST_TIME": "First Time Buyer",
                "REGULAR": "Regular", "FREQUENT": "Frequent Buyer",
                "WEDDING": "Wedding"
            }
            age_names = {
                "UNDER_5": "<5 yrs", "5_TO_18": "5-18 yrs",
                "18_TO_30": "18-30 yrs", "30_TO_50": "30-50 yrs",
                "50_PLUS": "50+ yrs"
            }
            pts_names = {
                "ABOVE_0": ">0 pts", "ABOVE_50": "50+ pts",
                "ABOVE_100": "100+ pts", "ABOVE_500": "500+ pts",
                "ZERO": "0 pts"
            }
            filter_parts = []
            filter_parts.append(tag_names.get(target_filter, "All Audiences" if target_filter == "ALL" else target_filter))
            if gender_filter != "ALL":
                filter_parts.append(gender_filter)
            if age_filter != "ALL":
                filter_parts.append(age_names.get(age_filter, age_filter))
            if points_filter != "ALL":
                filter_parts.append(pts_names.get(points_filter, points_filter))

            target_filter_summary = " · ".join(filter_parts)

            # Record campaign
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO campaigns (
                shop_id, title, type, festival_name, message_body, media_url,
                target_filter, status, total_recipients, sent_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SENDING', ?, 0)
            """, (
                shop_id, title, campaign_type, festival_name, message_body,
                media_url or None, target_filter_summary, total_recipients
            ))
            campaign_id = cursor.lastrowid
            conn.commit()

            # Dispatch messages
            for cust in recipients:
                rendered_msg = render_template(message_body, {
                    "customer_name": cust["name"],
                    "shop_name": shop_name,
                    "points": cust["loyalty_points"],
                    "city": shop["city"] or "our showroom"
                })

                send_whatsapp_message(
                    shop_id=shop_id,
                    customer_id=cust["id"],
                    recipient_phone=cust["phone"],
                    message_text=rendered_msg,
                    message_type=campaign_type,
                    media_url=media_url if media_url else None,
                    customer_name=cust["name"]
                )
                sent_count += 1

            # Update campaign status
            cursor.execute("""
            UPDATE campaigns SET
                status = 'SENT',
                sent_count = ?
            WHERE id = ?
            """, (sent_count, campaign_id))
            conn.commit()
            conn.close()

            return self.send_json({
                "success": True,
                "campaign_id": campaign_id,
                "total_recipients": total_recipients,
                "sent_count": sent_count
            })

        # 7. API: Direct Ad-Hoc Message
        elif path == "/api/whatsapp/send-direct":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access: You cannot send messages for another showroom."}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            recipient_phone = data.get("recipient_phone")
            message_text = data.get("message_text")
            customer_name = data.get("customer_name", "Customer")
            media_url = data.get("media_url")
            buttons = data.get("buttons")

            if not shop_id or not recipient_phone or not message_text:
                return self.send_json({"error": "shop_id, recipient_phone, and message_text required"}, 400)
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=data.get("customer_id"),
                recipient_phone=recipient_phone,
                message_text=message_text,
                message_type="DIRECT",
                media_url=media_url,
                customer_name=customer_name,
                template_name=data.get("template_name"),
                template_params=data.get("template_params"),
                template_lang=data.get("template_lang", "en_US"),
                buttons=buttons
            )
            return self.send_json(res)

        # 7b. API: Two-Way Conversation Send (Manual Typing or Interactive Quick Reply Buttons)
        elif path == "/api/conversations/send":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            recipient_phone = data.get("recipient_phone")
            message_text = data.get("message_text", "").strip()
            buttons = data.get("buttons")
            media_url = data.get("media_url")
            customer_name = data.get("customer_name") or "Customer"
            customer_id = data.get("customer_id")

            if not shop_id or not recipient_phone or not message_text:
                return self.send_json({"error": "shop_id, recipient_phone, and message_text required"}, 400)

            res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=customer_id,
                recipient_phone=recipient_phone,
                message_text=message_text,
                message_type="CHAT",
                media_url=media_url,
                customer_name=customer_name,
                buttons=buttons,
                direction="OUTBOUND"
            )

            # Unhide conversation if it was hidden, since shop owner messaged customer
            try:
                conn = get_connection()
                phone_clean = recipient_phone.replace("+", "").replace(" ", "").replace("-", "")
                phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean
                conn.execute("DELETE FROM hidden_conversations WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)", (shop_id, recipient_phone, f"%{phone_ten}"))
                conn.commit()
                conn.close()
            except Exception:
                pass

            return self.send_json(res)

        # 7b-2. API: Hide/Remove Customer from Conversation List
        elif path in ("/api/conversations/hide", "/api/conversations/remove"):
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            phone = (data.get("phone") or "").strip()

            if not shop_id or not phone:
                return self.send_json({"error": "shop_id and phone required"}, 400)

            phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
            phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

            conn = get_connection()
            # Mark incoming messages as read so it doesn't immediately resurrect from unread count
            conn.execute("""
                UPDATE whatsapp_logs 
                SET is_read = 1 
                WHERE shop_id = ? AND (recipient_phone = ? OR recipient_phone LIKE ?) AND is_read = 0
            """, (shop_id, phone, f"%{phone_ten}"))

            # Remove any older/inconsistent format entries for this customer
            conn.execute("""
                DELETE FROM hidden_conversations 
                WHERE shop_id = ? AND (
                    phone = ? 
                    OR phone = ? 
                    OR (LENGTH(phone) >= 10 AND SUBSTR(phone, -10) = ?)
                    OR (LENGTH(?) >= 10 AND phone LIKE '%' || ?)
                )
            """, (shop_id, phone, phone_ten, phone_ten, phone, phone_ten))

            # Insert clean entries for both the exact phone and 10-digit normalized phone
            conn.execute("""
                INSERT INTO hidden_conversations (shop_id, phone, hidden_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (shop_id, phone))
            if phone_ten != phone:
                conn.execute("""
                    INSERT INTO hidden_conversations (shop_id, phone, hidden_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (shop_id, phone_ten))
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "message": "Conversation removed from list", "phone": phone})

        # 7b-3. API: Unhide/Restore Customer to Conversation List
        elif path in ("/api/conversations/unhide", "/api/conversations/restore"):
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            phone = (data.get("phone") or "").strip()

            if not shop_id or not phone:
                return self.send_json({"error": "shop_id and phone required"}, 400)

            phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
            phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

            conn = get_connection()
            conn.execute("""
                DELETE FROM hidden_conversations
                WHERE shop_id = ? AND (phone = ? OR phone LIKE ? OR phone LIKE ?)
            """, (shop_id, phone, f"%{phone_ten}", f"%{phone_clean}%"))
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "message": "Conversation restored to list", "phone": phone})

        # 7c. API: Simulate Inbound Customer Reply or Interactive Button Click
        elif path == "/api/conversations/simulate-inbound":
            data = self.parse_json_body()
            req_shop_id = data.get("shop_id")
            if req_shop_id and not self.check_shop_access(user, req_shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            shop_id = user["shop_id"] if (user and user.get("role") == "shop_owner") else req_shop_id
            recipient_phone = data.get("recipient_phone")
            customer_name = data.get("customer_name") or "Customer"
            text = data.get("message_text", "").strip()
            button_id = data.get("selected_button_id", "")
            button_title = data.get("selected_button_title", "")

            if button_title:
                text = f"🔘 Selected: {button_title}"
            elif not text:
                text = "[Customer message]"

            if not shop_id or not recipient_phone or not text:
                return self.send_json({"error": "shop_id, recipient_phone, and message_text/button required"}, 400)

            conn = get_connection()
            phone_clean = recipient_phone.replace("+", "").replace(" ", "").replace("-", "")
            phone_ten = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

            # Customer sent a message: unhide so it appears in the conversation list with notification
            try:
                conn.execute("""
                    DELETE FROM hidden_conversations 
                    WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)
                """, (shop_id, recipient_phone, f"%{phone_ten}"))
            except Exception:
                pass

            cust = conn.execute("""
                SELECT id, name, loyalty_points FROM customers 
                WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)
            """, (shop_id, recipient_phone, f"%{phone_ten}")).fetchone()
            cid = cust["id"] if cust else data.get("customer_id")
            if cust and (not customer_name or customer_name == "Customer"):
                customer_name = cust["name"]

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO whatsapp_logs (
                    shop_id, customer_id, recipient_phone, recipient_name,
                    message_type, sender_name, message_text,
                    status, direction, selected_button_id, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                shop_id, cid, recipient_phone, customer_name,
                "INBOUND", customer_name, text,
                "DELIVERED", "INBOUND", button_id or button_title
            ))
            conn.commit()
            inbound_id = cursor.lastrowid
            conn.close()

            # Automated Smart Bot Response for interactive button clicks or keyword triggers
            auto_reply = None
            if button_title or button_id:
                auto_reply = resolve_custom_auto_reply(shop_id, cid, recipient_phone, button_id, button_title)
                if auto_reply:
                    send_whatsapp_message(
                        shop_id=shop_id,
                        customer_id=cid,
                        recipient_phone=recipient_phone,
                        message_text=auto_reply,
                        message_type="AUTO_REPLY",
                        customer_name=customer_name,
                        direction="OUTBOUND"
                    )
            elif text:
                matched_flow = match_flow_by_trigger_keyword(shop_id, text)
                if matched_flow:
                    conn = get_connection()
                    shop_row = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
                    conn.close()
                    s_name = (shop_row["sender_display_name"] or shop_row["name"]) if shop_row else "EasyToReach"
                    c_points = cust["loyalty_points"] if cust else 0
                    flow_msg = matched_flow["message"].replace("{name}", customer_name).replace("{points}", str(c_points)).replace("{shop}", s_name)
                    send_whatsapp_message(
                        shop_id=shop_id,
                        customer_id=cid,
                        recipient_phone=recipient_phone,
                        message_text=flow_msg,
                        message_type="INTERACTIVE_FLOW",
                        customer_name=customer_name,
                        buttons=matched_flow["buttons"],
                        direction="OUTBOUND"
                    )
                    auto_reply = flow_msg

            return self.send_json({"success": True, "inbound_id": inbound_id, "auto_reply": auto_reply})

        # 8. API: Cloud Sheet Auto-Sync (Google Drive / Sheets / Dropbox / Cloud CSV)
        elif path.startswith("/api/shops/") and path.endswith("/sync-cloud"):
            shop_id = path.split("/")[3]
            if user and not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            data = self.parse_json_body()
            url = data.get("sheet_url", "").strip()

            conn = get_connection()
            if not url:
                shop = conn.execute("SELECT cloud_sheet_url FROM shops WHERE id = ?", (shop_id,)).fetchone()
                if shop and shop["cloud_sheet_url"]:
                    url = shop["cloud_sheet_url"].strip()

            if not url:
                conn.close()
                return self.send_json({"error": "Google Sheets or Drive link is required"}, 400)

            # Auto-transform Google Sheets link to CSV export URL
            download_url = url
            if "docs.google.com/spreadsheets" in url:
                import re
                match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
                if match:
                    sheet_id = match.group(1)
                    download_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            elif "drive.google.com/file/d/" in url:
                import re
                match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", url)
                if match:
                    file_id = match.group(1)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

            # Fetch CSV data from cloud
            try:
                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EasyToReach/1.0"}
                )
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    raw_bytes = resp.read()
                    csv_text = raw_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                conn.close()
                return self.send_json({"error": f"Failed to download cloud sheet: {str(e)}"}, 400)

            cursor = conn.cursor()
            imported_count = 0
            errors = []

            reader = csv.DictReader(io.StringIO(csv_text))
            for i, row in enumerate(reader):
                # Flexible column matching
                name = (row.get("name") or row.get("Customer Name") or row.get("Full Name") or row.get("Customer") or "").strip()
                phone = (row.get("phone") or row.get("Phone Number") or row.get("Mobile") or row.get("WhatsApp") or row.get("Phone") or "").strip()
                if not name or not phone:
                    continue

                dob = (row.get("date_of_birth") or row.get("DOB") or row.get("Birthday") or "").strip()
                anniversary = (row.get("anniversary_date") or row.get("Anniversary") or "").strip()
                gender = (row.get("gender") or row.get("Gender") or "Female").strip()
                pref = (row.get("category_preference") or row.get("Preference") or row.get("Category") or "Silk Sarees").strip()
                points_raw = row.get("loyalty_points") or row.get("Points") or 0
                try:
                    points = int(float(points_raw))
                except Exception:
                    points = 0
                notes = (row.get("notes") or row.get("Notes") or row.get("Remarks") or "").strip()
                tags_raw = (row.get("tags") or row.get("Tags") or "Regular").split(",")
                tags_clean = [t.strip() for t in tags_raw if t.strip()]

                try:
                    cursor.execute("""
                    INSERT INTO customers (
                        shop_id, name, phone, date_of_birth, anniversary_date,
                        gender, category_preference, loyalty_points, notes, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(shop_id, phone) DO UPDATE SET
                        name = excluded.name,
                        date_of_birth = COALESCE(excluded.date_of_birth, customers.date_of_birth),
                        anniversary_date = COALESCE(excluded.anniversary_date, customers.anniversary_date),
                        category_preference = excluded.category_preference,
                        notes = excluded.notes
                    """, (
                        shop_id, name, phone, dob, anniversary,
                        gender, pref, points, notes, json.dumps(tags_clean)
                    ))
                    imported_count += 1
                except Exception as ex:
                    errors.append(f"Row {i+1} ({name}): {str(ex)}")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
            UPDATE shops SET
                cloud_sheet_url = ?,
                last_cloud_sync_at = ?
            WHERE id = ?
            """, (url, now_str, shop_id))

            conn.commit()
            conn.close()
            return self.send_json({
                "success": True,
                "imported_count": imported_count,
                "last_cloud_sync_at": now_str,
                "cloud_sheet_url": url,
                "errors": errors
            })

        # 9. API: Cloud Webhook Ingestion (Zapier / Shopify / Make / Google Forms / Cloud POS)
        elif path == "/api/webhooks/customer":
            data = self.parse_json_body()
            shop_id = data.get("shop_id")
            name = (data.get("name") or data.get("customer_name") or "").strip()
            phone = (data.get("phone") or data.get("mobile") or "").strip()

            if not shop_id or not name or not phone:
                return self.send_json({"error": "shop_id, name, and phone required"}, 400)

            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT INTO customers (
                    shop_id, name, phone, date_of_birth, anniversary_date,
                    gender, category_preference, loyalty_points, notes, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(shop_id, phone) DO UPDATE SET
                    name = excluded.name,
                    date_of_birth = COALESCE(excluded.date_of_birth, customers.date_of_birth),
                    category_preference = excluded.category_preference
                """, (
                    shop_id, name, phone, data.get("date_of_birth", ""),
                    data.get("anniversary_date", ""), data.get("gender", "Female"),
                    data.get("category_preference", "Silk Sarees"),
                    int(data.get("loyalty_points", 100)),
                    data.get("notes", "Auto-synced via Cloud Webhook"),
                    json.dumps(data.get("tags", ["Cloud Sync"]))
                ))
                conn.commit()
                cust_id = cursor.lastrowid
                conn.close()
                return self.send_json({"success": True, "customer_id": cust_id}, 201)
            except Exception as e:
                conn.close()
                return self.send_json({"error": str(e)}, 400)

        # 10. API: Inbound WhatsApp Webhook (Meta Cloud API Notifications & Replies)
        elif path == "/api/webhooks/whatsapp":
            data = self.parse_json_body()
            try:
                entries = data.get("entry", [])
                for entry in entries:
                    for change in entry.get("changes", []):
                        val = change.get("value", {})
                        phone_num_id = val.get("metadata", {}).get("phone_number_id")
                        conn = get_connection()
                        shop = conn.execute("SELECT id, name FROM shops WHERE whatsapp_phone_number_id = ?", (phone_num_id,)).fetchone()
                        shop_id = shop["id"] if shop else 1
                        
                        contacts = {c.get("wa_id"): c.get("profile", {}).get("name") for c in val.get("contacts", [])}
                        for msg in val.get("messages", []):
                            from_phone = msg.get("from")
                            cust_name = contacts.get(from_phone, "WhatsApp User")
                            msg_type = msg.get("type")
                            msg_text = ""
                            selected_btn = ""

                            btn_title = ""
                            if msg_type == "text":
                                msg_text = msg.get("text", {}).get("body", "")
                            elif msg_type == "interactive":
                                interactive = msg.get("interactive", {})
                                if interactive.get("type") == "button_reply":
                                    selected_btn = interactive.get("button_reply", {}).get("id", "")
                                    btn_title = interactive.get("button_reply", {}).get("title", "")
                                    msg_text = f"🔘 Selected: {btn_title}"
                                else:
                                    msg_text = "[Interactive Response]"
                            elif msg_type == "image":
                                msg_text = msg.get("image", {}).get("caption") or "[Image Received]"
                            else:
                                msg_text = f"[{msg_type.capitalize()} Message]"

                            cust = conn.execute("SELECT id FROM customers WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)", (shop_id, from_phone, f"%{from_phone[-10:]}%")).fetchone()
                            cid = cust["id"] if cust else None

                            # Unhide conversation if it was hidden, because customer sent an inbound message
                            try:
                                from_ten = from_phone[-10:] if len(from_phone) >= 10 else from_phone
                                conn.execute("DELETE FROM hidden_conversations WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)", (shop_id, from_phone, f"%{from_ten}"))
                            except Exception:
                                pass

                            conn.execute("""
                                INSERT INTO whatsapp_logs (
                                    shop_id, customer_id, recipient_phone, recipient_name,
                                    message_type, sender_name, message_text,
                                    status, direction, selected_button_id, is_read
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                            """, (
                                shop_id, cid, from_phone, cust_name,
                                "INBOUND", cust_name, msg_text,
                                "DELIVERED", "INBOUND", selected_btn
                            ))
                            conn.commit()

                            # Auto reply to real WhatsApp user on button press or keyword trigger
                            if selected_btn or btn_title:
                                auto_reply = resolve_custom_auto_reply(shop_id, cid, from_phone, selected_btn, btn_title)
                                if auto_reply:
                                    send_whatsapp_message(
                                        shop_id=shop_id,
                                        customer_id=cid,
                                        recipient_phone=from_phone,
                                        message_text=auto_reply,
                                        message_type="AUTO_REPLY",
                                        customer_name=cust_name,
                                        direction="OUTBOUND"
                                    )
                            elif msg_text:
                                matched_flow = match_flow_by_trigger_keyword(shop_id, msg_text)
                                if matched_flow:
                                    shop_row = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
                                    s_name = (shop_row["sender_display_name"] or shop_row["name"]) if shop_row else "EasyToReach"
                                    cust_row = conn.execute("SELECT loyalty_points FROM customers WHERE id = ?", (cid,)).fetchone() if cid else None
                                    c_pts = cust_row["loyalty_points"] if cust_row else 0
                                    flow_msg = matched_flow["message"].replace("{name}", cust_name).replace("{points}", str(c_pts)).replace("{shop}", s_name)
                                    send_whatsapp_message(
                                        shop_id=shop_id,
                                        customer_id=cid,
                                        recipient_phone=from_phone,
                                        message_text=flow_msg,
                                        message_type="INTERACTIVE_FLOW",
                                        customer_name=cust_name,
                                        buttons=matched_flow["buttons"],
                                        direction="OUTBOUND"
                                    )
                        conn.close()
            except Exception as e:
                print(f"Error processing inbound WhatsApp webhook: {e}")
            return self.send_json({"status": "received"})

        # 13. API: Save / Create Chatbot Flow (Visual Builder)
        elif path == "/api/chatbot-flows":
            data = self.parse_json_body()
            shop_id = data.get("shop_id") or (user.get("shop_id") if user else None) or 1
            if user and not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)
            name = (data.get("name") or "Custom Interactive Flow").strip()
            trigger_keyword = (data.get("trigger_keyword") or "").strip()
            flow_data = data.get("flow_data") or {}
            flow_id = data.get("id")
            is_active = 1 if data.get("is_active", True) else 0

            flow_data_json = json.dumps(flow_data) if isinstance(flow_data, (dict, list)) else str(flow_data)

            conn = get_connection()
            if flow_id:
                conn.execute("""
                    UPDATE chatbot_flows 
                    SET name = ?, trigger_keyword = ?, flow_data_json = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND (shop_id = ? OR ? = 'admin')
                """, (name, trigger_keyword, flow_data_json, is_active, flow_id, shop_id, user.get("role") if user else "shop_owner"))
                saved_id = flow_id
            else:
                cur = conn.execute("""
                    INSERT INTO chatbot_flows (shop_id, name, trigger_keyword, flow_data_json, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (shop_id, name, trigger_keyword, flow_data_json, is_active))
                saved_id = cur.lastrowid
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "id": saved_id, "message": "Interactive flow saved successfully!"})

        # 14. API: Simulate Chatbot Flow (Real-time WhatsApp Preview)
        elif path == "/api/chatbot-flows/simulate":
            data = self.parse_json_body()
            flow_data = data.get("flow_data") or {}
            action = data.get("action", "start")
            button_id = data.get("button_id", "")
            button_title = data.get("button_title", "")
            current_node_id = data.get("current_node_id", "")

            nodes = {n["id"]: n for n in flow_data.get("nodes", []) if "id" in n}

            if action == "start":
                start_node = None
                for n in flow_data.get("nodes", []):
                    if n.get("type") in ("buttons", "reply_buttons"):
                        start_node = n
                        break
                if not start_node and flow_data.get("nodes"):
                    start_node = flow_data["nodes"][0]

                if start_node:
                    return self.send_json({
                        "success": True,
                        "node_id": start_node["id"],
                        "type": start_node.get("type"),
                        "title": start_node.get("title", ""),
                        "message": start_node.get("message") or start_node.get("title", ""),
                        "buttons": start_node.get("buttons", []),
                        "finished": start_node.get("type") not in ("buttons", "reply_buttons")
                    })
                return self.send_json({"success": True, "message": "No nodes in flow", "buttons": [], "finished": True})

            elif action == "click_button":
                curr_node = nodes.get(current_node_id)
                target_node = None
                if curr_node:
                    for b in curr_node.get("buttons", []):
                        if (b.get("id") and b["id"] == button_id) or (b.get("title") and b["title"].lower() == button_title.lower()):
                            target_id = b.get("target")
                            target_node = nodes.get(target_id)
                            break
                if target_node:
                    return self.send_json({
                        "success": True,
                        "node_id": target_node["id"],
                        "type": target_node.get("type"),
                        "title": target_node.get("title", ""),
                        "message": target_node.get("message") or target_node.get("content", ""),
                        "buttons": target_node.get("buttons", []),
                        "finished": target_node.get("type") not in ("buttons", "reply_buttons")
                    })
                return self.send_json({
                    "success": True,
                    "message": "Thank you! Your response has been recorded.",
                    "buttons": [],
                    "finished": True
                })

        # 15. API: Send Interactive Flow to Real Customers (Single or Broadcast Segment)
        elif path == "/api/chatbot-flows/send":
            data = self.parse_json_body()
            shop_id = data.get("shop_id") or (user.get("shop_id") if user else None) or 1
            if user and not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            flow_id = data.get("flow_id")
            flow_data = data.get("flow_data")
            target_type = data.get("target_type", "single")  # "single" or "segment"
            target_phone = (data.get("phone") or "").strip()
            target_segment = (data.get("segment") or "all").lower()

            conn = get_connection()
            if flow_id and not flow_data:
                f_row = conn.execute("SELECT flow_data_json FROM chatbot_flows WHERE id = ? AND shop_id = ?", (flow_id, shop_id)).fetchone()
                if f_row and f_row["flow_data_json"]:
                    try:
                        flow_data = json.loads(f_row["flow_data_json"])
                    except Exception:
                        flow_data = {}

            if not flow_data or not isinstance(flow_data, dict):
                conn.close()
                return self.send_json({"error": "No valid flow data found to send."}, 400)

            nodes = {n["id"]: n for n in flow_data.get("nodes", []) if "id" in n}
            question_node = None
            for n in flow_data.get("nodes", []):
                if n.get("type") in ("buttons", "reply_buttons"):
                    question_node = n
                    break
            if not question_node and flow_data.get("nodes"):
                question_node = flow_data["nodes"][0]

            if not question_node:
                conn.close()
                return self.send_json({"error": "No interactive question/buttons node found in this flow."}, 400)

            raw_message = (question_node.get("message") or question_node.get("title") or "Hello from our store!").strip()
            raw_buttons = question_node.get("buttons") or []

            # Format buttons for WhatsApp API and attach target node auto-reply
            formatted_buttons = []
            for idx, b in enumerate(raw_buttons[:3]):
                bid = b.get("id") or f"btn_{idx+1}"
                btitle = (b.get("title") or f"Option {idx+1}")[:20]
                target_id = b.get("target")
                target_node = nodes.get(target_id)
                target_msg = ""
                if target_node:
                    target_msg = target_node.get("message") or target_node.get("content") or ""

                formatted_buttons.append({
                    "id": bid,
                    "title": btitle,
                    "target": target_id,
                    "auto_reply": target_msg
                })

            shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
            shop_name = (shop["sender_display_name"] or shop["name"]) if shop else "EasyToReach Store"

            recipients = []
            if target_type == "single":
                if not target_phone:
                    conn.close()
                    return self.send_json({"error": "WhatsApp phone number is required."}, 400)
                clean_phone = target_phone.replace("+", "").replace(" ", "").replace("-", "")
                ten_digits = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
                cust = conn.execute("SELECT * FROM customers WHERE shop_id = ? AND (phone = ? OR phone LIKE ?)", (shop_id, target_phone, f"%{ten_digits}")).fetchone()
                if cust:
                    recipients.append(dict(cust))
                else:
                    recipients.append({
                        "id": None,
                        "name": data.get("customer_name") or "Valued Customer",
                        "phone": target_phone,
                        "loyalty_points": 0
                    })
            else:
                query = "SELECT * FROM customers WHERE shop_id = ? AND phone IS NOT NULL AND phone != ''"
                params = [shop_id]
                if target_segment == "vip":
                    query += " AND (category_preference = 'VIP' OR loyalty_points >= 100)"
                elif target_segment == "regular":
                    query += " AND category_preference = 'Regular'"
                elif target_segment == "inactive":
                    query += " AND last_visit_date < date('now', '-30 days')"
                
                rows = conn.execute(query, tuple(params)).fetchall()
                recipients = [dict(r) for r in rows]

            conn.close()

            if not recipients:
                return self.send_json({"error": "No customers found for the selected target audience."}, 400)

            sent_count = 0
            failed_count = 0
            details = []

            for r in recipients:
                c_name = r.get("name") or "Valued Customer"
                c_phone = r.get("phone")
                c_points = r.get("loyalty_points") or 0
                c_id = r.get("id")

                # Replace placeholders
                personalized_msg = (
                    raw_message
                    .replace("{name}", c_name)
                    .replace("{{customer_name}}", c_name)
                    .replace("{points}", str(c_points))
                    .replace("{{points}}", str(c_points))
                    .replace("{shop}", shop_name)
                    .replace("{{shop_name}}", shop_name)
                )

                cust_buttons = []
                for b in formatted_buttons:
                    b_copy = dict(b)
                    if b_copy.get("auto_reply"):
                        b_copy["auto_reply"] = (
                            b_copy["auto_reply"]
                            .replace("{name}", c_name)
                            .replace("{{customer_name}}", c_name)
                            .replace("{points}", str(c_points))
                            .replace("{{points}}", str(c_points))
                            .replace("{shop}", shop_name)
                            .replace("{{shop_name}}", shop_name)
                        )
                    cust_buttons.append(b_copy)

                res = send_whatsapp_message(
                    shop_id=shop_id,
                    customer_id=c_id,
                    recipient_phone=c_phone,
                    message_text=personalized_msg,
                    message_type="INTERACTIVE_FLOW",
                    customer_name=c_name,
                    buttons=cust_buttons,
                    direction="OUTBOUND"
                )
                if res.get("success"):
                    sent_count += 1
                else:
                    failed_count += 1
                details.append({
                    "phone": c_phone,
                    "name": c_name,
                    "status": res.get("status", "SENT"),
                    "success": res.get("success", False)
                })

            return self.send_json({
                "success": True,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total": len(recipients),
                "message": f"Interactive Flow sent successfully to {sent_count} customer(s)!",
                "details": details[:10]
            })

        self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = self.get_current_user()

        if not user:
            return self.send_json({"error": "Authentication required. Please log in."}, 401)

        # 0. API: Suspend or Activate User (Admin Only)
        if path.startswith("/api/admin/users/") and path.endswith("/status"):
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            parts = path.split("/")
            try:
                target_user_id = int(parts[4])
            except ValueError:
                return self.send_json({"error": "Invalid user ID"}, 400)
            if target_user_id == user.get("id"):
                return self.send_json({"error": "Cannot suspend your own admin account"}, 400)
            data = self.parse_json_body()
            status = data.get("status", "SUSPENDED")
            res = auth.set_user_status(target_user_id, status)
            return self.send_json(res)

        # 1. API: Update Shop Profile & WhatsApp Meta Credentials (Admin & Shop Owner)
        if path.startswith("/api/shops/") and len(path.split("/")) == 4:
            shop_id = path.split("/")[3]
            if not self.check_shop_access(user, shop_id):
                return self.send_json({"error": "Unauthorized shop access"}, 403)

            data = self.parse_json_body()

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE shops SET
                name = COALESCE(?, name),
                tagline = COALESCE(?, tagline),
                phone = COALESCE(?, phone),
                email = COALESCE(?, email),
                address = COALESCE(?, address),
                city = COALESCE(?, city),
                whatsapp_phone_number_id = COALESCE(?, whatsapp_phone_number_id),
                whatsapp_business_id = COALESCE(?, whatsapp_business_id),
                whatsapp_access_token = COALESCE(?, whatsapp_access_token),
                sender_display_name = COALESCE(?, sender_display_name),
                points_per_100_spent = COALESCE(?, points_per_100_spent),
                point_redeem_value_inr = COALESCE(?, point_redeem_value_inr),
                birthday_discount_percent = COALESCE(?, birthday_discount_percent),
                birthday_offer_validity_days = COALESCE(?, birthday_offer_validity_days),
                auto_birthday_wishes_enabled = COALESCE(?, auto_birthday_wishes_enabled),
                cloud_sheet_url = COALESCE(?, cloud_sheet_url),
                custom_auto_replies_json = COALESCE(?, custom_auto_replies_json),
                miss_you_enabled = COALESCE(?, miss_you_enabled),
                miss_you_days = COALESCE(?, miss_you_days),
                miss_you_template = COALESCE(?, miss_you_template),
                points_reminder_enabled = COALESCE(?, points_reminder_enabled),
                points_reminder_days = COALESCE(?, points_reminder_days),
                points_reminder_min_points = COALESCE(?, points_reminder_min_points),
                points_reminder_template = COALESCE(?, points_reminder_template)
            WHERE id = ?
            """, (
                data.get("name"),
                data.get("tagline"),
                data.get("phone"),
                data.get("email"),
                data.get("address"),
                data.get("city"),
                data.get("whatsapp_phone_number_id"),
                data.get("whatsapp_business_id"),
                data.get("whatsapp_access_token"),
                data.get("sender_display_name"),
                data.get("points_per_100_spent"),
                data.get("point_redeem_value_inr"),
                data.get("birthday_discount_percent"),
                data.get("birthday_offer_validity_days"),
                data.get("auto_birthday_wishes_enabled"),
                data.get("cloud_sheet_url"),
                data.get("custom_auto_replies_json"),
                data.get("miss_you_enabled"),
                data.get("miss_you_days"),
                data.get("miss_you_template"),
                data.get("points_reminder_enabled"),
                data.get("points_reminder_days"),
                data.get("points_reminder_min_points"),
                data.get("points_reminder_template"),
                shop_id
            ))
            conn.commit()
            conn.close()
            return self.send_json({"success": True})

        # 2. API: Update Customer
        elif path.startswith("/api/customers/") and len(path.split("/")) == 4:
            cust_id = path.split("/")[3]
            conn = get_connection()
            if user and user.get("role") == "shop_owner":
                cust = conn.execute("SELECT shop_id FROM customers WHERE id = ?", (cust_id,)).fetchone()
                if not cust or not self.check_shop_access(user, cust["shop_id"]):
                    conn.close()
                    return self.send_json({"error": "Unauthorized customer access"}, 403)

            data = self.parse_json_body()

            tags_json = None
            if "tags" in data:
                tags = data["tags"]
                tags_json = json.dumps(tags) if isinstance(tags, list) else json.dumps([str(tags)])

            cursor = conn.cursor()
            cursor.execute("""
            UPDATE customers SET
                name = COALESCE(?, name),
                phone = COALESCE(?, phone),
                date_of_birth = COALESCE(?, date_of_birth),
                anniversary_date = COALESCE(?, anniversary_date),
                gender = COALESCE(?, gender),
                category_preference = COALESCE(?, category_preference),
                loyalty_points = COALESCE(?, loyalty_points),
                notes = COALESCE(?, notes),
                tags = COALESCE(?, tags)
            WHERE id = ?
            """, (
                data.get("name"),
                data.get("phone"),
                data.get("date_of_birth"),
                data.get("anniversary_date"),
                data.get("gender"),
                data.get("category_preference"),
                data.get("loyalty_points"),
                data.get("notes"),
                tags_json,
                cust_id
            ))
            conn.commit()
            conn.close()
            return self.send_json({"success": True})

        # 13. API: Save Chatbot Flow (Visual Builder)
        elif path == "/api/chatbot-flows":
            data = self.parse_json_body()
            shop_id = data.get("shop_id") or (user.get("shop_id") if user else None) or 1
            name = (data.get("name") or "Custom Interactive Flow").strip()
            trigger_keyword = (data.get("trigger_keyword") or "").strip()
            flow_data = data.get("flow_data") or {}
            flow_id = data.get("id")
            is_active = 1 if data.get("is_active", True) else 0

            flow_data_json = json.dumps(flow_data) if isinstance(flow_data, (dict, list)) else str(flow_data)

            conn = get_connection()
            if flow_id:
                conn.execute("""
                    UPDATE chatbot_flows 
                    SET name = ?, trigger_keyword = ?, flow_data_json = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND (shop_id = ? OR ? = 'admin')
                """, (name, trigger_keyword, flow_data_json, is_active, flow_id, shop_id, user.get("role") if user else "shop_owner"))
                saved_id = flow_id
            else:
                cur = conn.execute("""
                    INSERT INTO chatbot_flows (shop_id, name, trigger_keyword, flow_data_json, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (shop_id, name, trigger_keyword, flow_data_json, is_active))
                saved_id = cur.lastrowid
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "id": saved_id, "message": "Interactive flow updated successfully!"})

        self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = self.get_current_user()

        if not user:
            return self.send_json({"error": "Authentication required. Please log in."}, 401)

        # 0. API: Delete User Account (Admin Only)
        if path.startswith("/api/admin/users/") and len(path.split("/")) == 5:
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            try:
                target_user_id = int(path.split("/")[4])
            except ValueError:
                return self.send_json({"error": "Invalid user ID"}, 400)
            if target_user_id == user.get("id"):
                return self.send_json({"error": "Cannot delete your own active admin account"}, 400)
            res = auth.delete_user(target_user_id)
            return self.send_json(res)

        # 0b. API: Delete Shop & Associated Records (Admin Only)
        if path.startswith("/api/shops/") and len(path.split("/")) == 4:
            if user.get("role") != "admin":
                return self.send_json({"error": "Admin access required"}, 403)
            try:
                target_shop_id = int(path.split("/")[3])
            except ValueError:
                return self.send_json({"error": "Invalid shop ID"}, 400)
            conn = get_connection()
            # Clean up all dependent records
            conn.execute("DELETE FROM customers WHERE shop_id = ?", (target_shop_id,))
            conn.execute("DELETE FROM purchases WHERE shop_id = ?", (target_shop_id,))
            conn.execute("DELETE FROM campaigns WHERE shop_id = ?", (target_shop_id,))
            conn.execute("DELETE FROM whatsapp_logs WHERE shop_id = ?", (target_shop_id,))
            conn.execute("DELETE FROM birthday_logs WHERE shop_id = ?", (target_shop_id,))
            # Clean up sessions and users for this shop
            conn.execute("DELETE FROM sessions WHERE shop_id = ?", (target_shop_id,))
            conn.execute("DELETE FROM users WHERE shop_id = ? AND role = 'shop_owner'", (target_shop_id,))
            conn.execute("DELETE FROM shops WHERE id = ?", (target_shop_id,))
            conn.commit()
            conn.close()
            return self.send_json({"success": True})

        if path.startswith("/api/customers/") and len(path.split("/")) == 4:
            cust_id = path.split("/")[3]
            conn = get_connection()
            if user and user.get("role") == "shop_owner":
                cust = conn.execute("SELECT shop_id FROM customers WHERE id = ?", (cust_id,)).fetchone()
                if not cust or not self.check_shop_access(user, cust["shop_id"]):
                    conn.close()
                    return self.send_json({"error": "Unauthorized customer access"}, 403)

            conn.execute("DELETE FROM customers WHERE id = ?", (cust_id,))
            conn.commit()
            conn.close()
            return self.send_json({"success": True})

        # API: Delete Chatbot Flow
        if path.startswith("/api/chatbot-flows/") and len(path.split("/")) == 4:
            flow_id = path.split("/")[3]
            conn = get_connection()
            conn.execute("DELETE FROM chatbot_flows WHERE id = ?", (flow_id,))
            conn.commit()
            conn.close()
            return self.send_json({"success": True, "message": "Flow deleted successfully"})

        self.send_error(404, "Endpoint not found")

def run_server():
    init_db()
    auth.seed_default_users()
    start_background_scheduler()
    server_address = ("0.0.0.0", PORT)
    httpd = ThreadedHTTPServer(server_address, TextileCRMRequestHandler)
    print(f"🚀 Textile WhatsApp CRM & Marketing Server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()

if __name__ == "__main__":
    run_server()

