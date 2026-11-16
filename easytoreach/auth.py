import hashlib
import os
import uuid
from datetime import datetime, timedelta
from database import get_connection, sync_subscription_statuses

def hash_password(password, salt=None):
    """Hash password using PBKDF2-HMAC-SHA256 with salt (Standard Library)."""
    if not salt:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()
    return pwd_hash, salt

def verify_password(password, salt, expected_hash):
    """Verify password against stored salt and hash."""
    pwd_hash, _ = hash_password(password, salt)
    return pwd_hash == expected_hash

def init_auth_tables():
    """Create users and sessions tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()

def seed_default_users():
    """Ensure default Admin and Shop Owner accounts exist."""
    init_auth_tables()
    conn = get_connection()
    cursor = conn.cursor()

    default_accounts = [
        # 1. Platform Master Admin (Access to all shops)
        {
            "username": "admin",
            "email": "admin@easytoreach.in",
            "password": "admin123",
            "role": "admin",
            "shop_id": None,
            "full_name": "Platform Administrator",
            "phone": "+91 99000 00000"
        },
        # 2. Shop Owner 1: Sri Lakshmi Silks
        {
            "username": "lakshmi",
            "email": "owner@srilakshmisilks.in",
            "password": "lakshmi123",
            "role": "shop_owner",
            "shop_id": 1,
            "full_name": "Meenakshi Sundaram",
            "phone": "+91 94441 23456"
        },
        # 3. Shop Owner 2: Royal Menswear
        {
            "username": "royal",
            "email": "manager@royalmenswear.com",
            "password": "royal123",
            "role": "shop_owner",
            "shop_id": 2,
            "full_name": "Rajesh Kumar",
            "phone": "+91 98422 67890"
        }
    ]

    for acc in default_accounts:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (acc["username"],)).fetchone()
        if not existing:
            pwd_hash, salt = hash_password(acc["password"])
            cursor.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, shop_id, full_name, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                acc["username"], acc["email"], pwd_hash, salt,
                acc["role"], acc["shop_id"], acc["full_name"], acc["phone"]
            ))

    conn.commit()
    conn.close()

def authenticate_user(username_or_email, password):
    """Authenticate a user by username or email. Returns user dict or None."""
    try:
        sync_subscription_statuses()
    except Exception:
        pass

    conn = get_connection()
    identifier = username_or_email.strip().lower()
    user = conn.execute("""
    SELECT u.*, s.name as shop_name, s.slug as shop_slug, s.city as shop_city,
           s.status as shop_status, s.subscription_end, s.subscription_plan
    FROM users u
    LEFT JOIN shops s ON u.shop_id = s.id
    WHERE LOWER(u.username) = ? OR LOWER(u.email) = ?
    """, (identifier, identifier)).fetchone()
    conn.close()

    if not user:
        return None

    if verify_password(password, user["salt"], user["password_hash"]):
        if user["role"] == "shop_owner" and user["shop_id"]:
            if user["shop_status"] == "SUSPENDED":
                return {"error": f"Store subscription for '{user['shop_name']}' is suspended/expired. Please contact Admin."}
        if user["status"] != "ACTIVE":
            return {"error": "Your account has been suspended by the Platform Administrator."}
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "shop_id": user["shop_id"],
            "shop_name": user["shop_name"] or "All Showrooms (Admin)",
            "shop_slug": user["shop_slug"],
            "shop_city": user["shop_city"],
            "full_name": user["full_name"],
            "phone": user["phone"]
        }
    return None

def create_session(user_dict):
    """Create a new 7-day session token."""
    token = f"tpx_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    expires_at = datetime.now() + timedelta(days=7)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sessions (token, user_id, role, shop_id, expires_at)
    VALUES (?, ?, ?, ?, ?)
    """, (token, user_dict["id"], user_dict["role"], user_dict["shop_id"], expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return token, expires_at.isoformat()

def get_user_from_token(token):
    """Validate token and return user information if valid."""
    if not token:
        return None

    # Strip Bearer prefix if passed
    if token.startswith("Bearer "):
        token = token[7:].strip()

    conn = get_connection()
    row = conn.execute("""
    SELECT s.token, s.expires_at, u.id, u.username, u.email, u.role, u.shop_id, u.full_name, u.phone,
           sh.name as shop_name, sh.slug as shop_slug, sh.city as shop_city,
           sh.status as shop_status, sh.subscription_end
    FROM sessions s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN shops sh ON u.shop_id = sh.id
    WHERE s.token = ? AND u.status = 'ACTIVE'
    """, (token,)).fetchone()
    conn.close()

    if not row:
        return None

    if row["role"] == "shop_owner" and row["shop_id"]:
        if row["shop_status"] == "SUSPENDED":
            return None

    # Check expiration
    try:
        exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > exp:
            return None
    except Exception:
        pass

    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "shop_id": row["shop_id"],
        "shop_name": row["shop_name"] or ("All Showrooms (Admin)" if row["role"] == "admin" else "Store"),
        "shop_slug": row["shop_slug"],
        "shop_city": row["shop_city"],
        "full_name": row["full_name"],
        "phone": row["phone"]
    }

def delete_session(token):
    """Log out / invalidate session."""
    if not token:
        return
    if token.startswith("Bearer "):
        token = token[7:].strip()
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def create_shop_owner_user(username, email, password, shop_id, full_name, phone=None):
    """Create a new shop owner user account (called by Admin)."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check uniqueness
    existing = cursor.execute(
        "SELECT id FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
        (username.strip().lower(), email.strip().lower())
    ).fetchone()
    if existing:
        conn.close()
        return {"success": False, "error": "Username or email already exists"}

    pwd_hash, salt = hash_password(password)
    cursor.execute("""
    INSERT INTO users (username, email, password_hash, salt, role, shop_id, full_name, phone)
    VALUES (?, ?, ?, ?, 'shop_owner', ?, ?, ?)
    """, (
        username.strip().lower(), email.strip().lower(), pwd_hash, salt,
        shop_id, full_name.strip(), phone
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {"success": True, "user_id": new_id}

def list_users():
    """List all users with their associated shop details (Admin view)."""
    conn = get_connection()
    users = conn.execute("""
    SELECT u.id, u.username, u.email, u.role, u.shop_id, u.full_name, u.phone, u.status, u.created_at,
           s.name as shop_name, s.city as shop_city
    FROM users u
    LEFT JOIN shops s ON u.shop_id = s.id
    ORDER BY u.role ASC, u.id ASC
    """).fetchall()
    conn.close()
    return [dict(u) for u in users]

def set_user_status(user_id, status):
    """Suspend or activate a user account."""
    status = status.upper().strip()
    if status not in ("ACTIVE", "SUSPENDED"):
        return {"success": False, "error": "Invalid status. Must be ACTIVE or SUSPENDED."}
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    if status == "SUSPENDED":
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"success": True, "status": status}

def delete_user(user_id):
    """Permanently delete a user account and their active sessions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"success": True}

