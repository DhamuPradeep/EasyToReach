import sqlite3
import os
import json
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textile_crm.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Shops (Tenants)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        tagline TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        whatsapp_phone_number_id TEXT DEFAULT '',
        whatsapp_business_id TEXT DEFAULT '',
        whatsapp_access_token TEXT DEFAULT '',
        sender_display_name TEXT NOT NULL,
        points_per_100_spent REAL DEFAULT 5.0,
        point_redeem_value_inr REAL DEFAULT 1.0,
        birthday_discount_percent INTEGER DEFAULT 15,
        birthday_offer_validity_days INTEGER DEFAULT 7,
        auto_birthday_wishes_enabled INTEGER DEFAULT 1,
        cloud_sheet_url TEXT DEFAULT '',
        last_cloud_sync_at TIMESTAMP,
        subscription_plan TEXT DEFAULT 'Standard Annual',
        subscription_start TEXT DEFAULT '2026-01-01',
        subscription_end TEXT DEFAULT '2026-12-31',
        status TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Safe migrations for existing DB
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN cloud_sheet_url TEXT DEFAULT '';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN last_cloud_sync_at TIMESTAMP;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN subscription_plan TEXT DEFAULT 'Standard Annual';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN subscription_start TEXT DEFAULT '2026-01-01';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN subscription_end TEXT DEFAULT '2026-12-31';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN status TEXT DEFAULT 'ACTIVE';")
    except Exception:
        pass

    # 2. Customers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        date_of_birth TEXT,
        anniversary_date TEXT,
        gender TEXT DEFAULT 'Female',
        category_preference TEXT DEFAULT 'Silk Sarees',
        loyalty_points INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0.0,
        total_visits INTEGER DEFAULT 0,
        last_visit_date TEXT,
        notes TEXT,
        tags TEXT DEFAULT '["Regular"]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
        UNIQUE(shop_id, phone)
    );
    """)

    # 3. Purchases & Loyalty Points Ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        invoice_no TEXT,
        bill_amount REAL NOT NULL,
        discount_amount REAL DEFAULT 0.0,
        net_amount REAL NOT NULL,
        points_earned INTEGER DEFAULT 0,
        points_redeemed INTEGER DEFAULT 0,
        purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        items_summary TEXT,
        whatsapp_notified INTEGER DEFAULT 0,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    """)

    # 4. Campaigns (Broadcasts: Festivals, New Collections)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        festival_name TEXT,
        message_body TEXT NOT NULL,
        media_url TEXT,
        target_filter TEXT DEFAULT 'ALL',
        status TEXT DEFAULT 'DRAFT',
        total_recipients INTEGER DEFAULT 0,
        sent_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
    );
    """)

    # 5. WhatsApp Message Logs (Full audit trail and delivery status)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        customer_id INTEGER,
        recipient_phone TEXT NOT NULL,
        recipient_name TEXT,
        message_type TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        message_text TEXT NOT NULL,
        media_url TEXT,
        status TEXT DEFAULT 'SENT',
        meta_message_id TEXT,
        error_message TEXT,
        direction TEXT DEFAULT 'OUTBOUND',
        buttons_json TEXT DEFAULT '',
        selected_button_id TEXT DEFAULT '',
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
    );
    """)

    # Safe migrations for existing DB
    try:
        cursor.execute("ALTER TABLE whatsapp_logs ADD COLUMN direction TEXT DEFAULT 'OUTBOUND';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE whatsapp_logs ADD COLUMN buttons_json TEXT DEFAULT '';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE whatsapp_logs ADD COLUMN selected_button_id TEXT DEFAULT '';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE whatsapp_logs ADD COLUMN is_read INTEGER DEFAULT 1;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN custom_auto_replies_json TEXT DEFAULT '{}';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN miss_you_enabled INTEGER DEFAULT 1;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN miss_you_days INTEGER DEFAULT 30;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN miss_you_template TEXT DEFAULT '';")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN points_reminder_enabled INTEGER DEFAULT 1;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN points_reminder_days INTEGER DEFAULT 60;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN points_reminder_min_points INTEGER DEFAULT 50;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE shops ADD COLUMN points_reminder_template TEXT DEFAULT '';")
    except Exception:
        pass
    try:
        cursor.execute("""CREATE TABLE IF NOT EXISTS reminder_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );""")
    except Exception:
        pass

    # 6. Birthday Dispatch Tracking (Prevents duplicate sends within the same year)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS birthday_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, customer_id, year),
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    """)

    # 7. Users (Authentication & Multi-Tenant Role Access)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'shop_owner')),
        shop_id INTEGER,
        full_name TEXT NOT NULL,
        phone TEXT,
        status TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE SET NULL
    );
    """)

    # 8. User Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        shop_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 9. Hidden Conversations (allows shop owners to remove conversations from list)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hidden_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        hidden_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shop_id, phone),
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
    );
    """)

    # 10. Demo Requests (Landing page lead captures & appointments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS demo_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        shop_name TEXT,
        city TEXT,
        biz_type TEXT,
        customers TEXT,
        goal TEXT,
        appointment_date TEXT,
        appointment_time TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migration: ensure email, appointment_date, appointment_time exist
    cursor.execute("PRAGMA table_info(demo_requests)")
    cols = [r[1] for r in cursor.fetchall()]
    if "email" not in cols:
        cursor.execute("ALTER TABLE demo_requests ADD COLUMN email TEXT")
    if "appointment_date" not in cols:
        cursor.execute("ALTER TABLE demo_requests ADD COLUMN appointment_date TEXT")
    if "appointment_time" not in cols:
        cursor.execute("ALTER TABLE demo_requests ADD COLUMN appointment_time TEXT")
    if "meet_link" not in cols:
        cursor.execute("ALTER TABLE demo_requests ADD COLUMN meet_link TEXT")

    # 11. Google Calendar OAuth Tokens
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS google_calendar_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        client_id TEXT,
        client_secret TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at REAL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 12. Chatbot Interactive Flows (Visual Graph Builder)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chatbot_flows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        trigger_keyword TEXT DEFAULT '',
        flow_data_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
    );
    """)

    # Seed default interactive flow for shops if none exist
    cursor.execute("SELECT id, name FROM shops")
    shops_list = cursor.fetchall()
    default_flow_json = json.dumps({
        "nodes": [
            {
                "id": "node_trigger",
                "type": "trigger",
                "title": "Inbound Trigger",
                "keyword": "offer, hi, help, start",
                "x": 50,
                "y": 140
            },
            {
                "id": "node_buttons_1",
                "type": "buttons",
                "title": "Interactive Reply Buttons",
                "message": "Namaste {name}! 🛍️ Would you like to view our exclusive Festive Silk Collection with an instant 15% VIP discount?",
                "x": 330,
                "y": 110,
                "buttons": [
                    { "id": "btn_yes", "title": "Yes, View Offer", "target": "node_text_yes" },
                    { "id": "btn_no", "title": "No, Not Now", "target": "node_text_no" },
                    { "id": "btn_agent", "title": "Talk to Stylist", "target": "node_text_agent" }
                ]
            },
            {
                "id": "node_text_yes",
                "type": "text",
                "title": "Customer Presses YES",
                "message": "🎉 Wonderful! Use voucher code *FESTIVE15* at checkout for flat 15% OFF!\n\n👗 Browse online catalog: https://srilakshmisilks.in/catalog\n⏳ Valid for 7 days. Enjoy your shopping!",
                "x": 720,
                "y": 40
            },
            {
                "id": "node_text_no",
                "type": "text",
                "title": "Customer Presses NO",
                "message": "Understood! No worries at all. Feel free to message us anytime if you need assistance. Have a wonderful day! 😊",
                "x": 720,
                "y": 190
            },
            {
                "id": "node_text_agent",
                "type": "text",
                "title": "Showroom Stylist Handoff",
                "message": "Namaste {name}! Our showroom associate has been notified and will reply directly in this chat shortly. 📞",
                "x": 720,
                "y": 330
            }
        ],
        "connections": [
            { "from": "node_trigger", "to": "node_buttons_1", "port": "out" },
            { "from": "node_buttons_1", "to": "node_text_yes", "buttonId": "btn_yes" },
            { "from": "node_buttons_1", "to": "node_text_no", "buttonId": "btn_no" },
            { "from": "node_buttons_1", "to": "node_text_agent", "buttonId": "btn_agent" }
        ]
    })

    for s in shops_list:
        existing = cursor.execute("SELECT id FROM chatbot_flows WHERE shop_id = ?", (s["id"],)).fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO chatbot_flows (shop_id, name, trigger_keyword, flow_data_json, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (s["id"], "Festive Offer Yes/No Flow", "offer, hi, help", default_flow_json))

    conn.commit()
    conn.close()
    print("Database initialized successfully.")
    sync_subscription_statuses()

def sync_subscription_statuses():
    """
    Checks all shops with subscription_end.
    If current date > subscription_end:
      - Automatically marks shop.status = 'SUSPENDED'
      - Automatically marks associated user accounts (shop_id = shop.id) as 'SUSPENDED'
    """
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        expired = conn.execute("""
            SELECT id, name, subscription_end FROM shops
            WHERE subscription_end IS NOT NULL
              AND subscription_end != ''
              AND subscription_end < ?
              AND status != 'SUSPENDED'
        """, (today_str,)).fetchall()

        for s in expired:
            conn.execute("UPDATE shops SET status = 'SUSPENDED' WHERE id = ?", (s["id"],))
            conn.execute("UPDATE users SET status = 'SUSPENDED' WHERE shop_id = ?", (s["id"],))
        
        conn.commit()
    except Exception as e:
        print(f"Error checking subscriptions: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()

