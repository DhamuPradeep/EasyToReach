import time
import threading
from datetime import datetime, timedelta
from database import get_connection
from whatsapp import send_whatsapp_message, render_template

DEFAULT_BIRTHDAY_TEMPLATE = (
    "🎉 Happy Birthday, *{{customer_name}}*! 🎂✨\n\n"
    "Wishing you joy, good health, and prosperity from all of us at *{{shop_name}}*!\n\n"
    "To celebrate your special day, we are pleased to gift you an exclusive *{{discount}}% BIRTHDAY DISCOUNT* on your purchase! 🎁👗\n\n"
    "🛍️ *Valid on all our latest Silk Sarees, Readymades & Designer Collections.*\n"
    "📌 Simply present this message at our store billing counter.\n"
    "⏳ Offer valid for the next {{valid_days}} days.\n\n"
    "📍 Visit {{shop_name}}, {{city}}.\n"
    "Warm wishes,\n"
    "The {{shop_name}} Family"
)

DEFAULT_MISS_YOU_TEMPLATE = (
    "💐 Namaste *{{customer_name}}*!\n\n"
    "We miss you at *{{shop_name}}*! 🛍️\n\n"
    "It's been a while since your last visit and we wanted to check in. "
    "Our latest collection has some beautiful new arrivals we know you'll love!\n\n"
    "✨ Come visit us soon and enjoy a *special welcome-back offer* just for you.\n\n"
    "📍 *{{shop_name}}*, {{city}}\n"
    "We look forward to seeing you again! 🙏"
)

DEFAULT_POINTS_REMINDER_TEMPLATE = (
    "🌟 Namaste *{{customer_name}}*!\n\n"
    "Your loyalty points at *{{shop_name}}* are waiting to be redeemed! 💰\n\n"
    "🏆 *Your Current Balance: {{points}} Points*\n"
    "💵 Worth ₹{{points_value}} instant discount!\n\n"
    "⏰ Don't let your points go unused — redeem them on your next visit!\n"
    "📌 Simply show this message at billing to apply your discount.\n\n"
    "📍 Visit *{{shop_name}}*, {{city}}\n"
    "We value your loyalty! 🙏"
)


def check_and_send_birthday_wishes(specific_shop_id=None):
    """
    Scans for customers whose birthday is today (MM-DD) and dispatches
    personalized WhatsApp birthday greetings with exclusive store offers.
    Ensures zero duplicate messages per calendar year.
    """
    conn = get_connection()
    now = datetime.now()
    current_year = now.year
    today_mm_dd = now.strftime("%m-%d")

    # Fetch active shops with auto-wishes enabled
    if specific_shop_id:
        shops = conn.execute("SELECT * FROM shops WHERE id = ? AND auto_birthday_wishes_enabled = 1", (specific_shop_id,)).fetchall()
    else:
        shops = conn.execute("SELECT * FROM shops WHERE auto_birthday_wishes_enabled = 1").fetchall()

    total_sent = 0
    results = []

    for shop in shops:
        shop_id = shop["id"]
        shop_name = shop["sender_display_name"] or shop["name"]
        discount = shop["birthday_discount_percent"]
        valid_days = shop["birthday_offer_validity_days"]
        city = shop["city"] or "our store"

        # Find customers with birthday today
        # Handles formats: "YYYY-MM-DD" or "MM-DD"
        query = """
        SELECT c.* FROM customers c
        WHERE c.shop_id = ?
        AND (
            substr(c.date_of_birth, -5) = ? OR 
            substr(c.date_of_birth, 6, 5) = ?
        )
        AND c.id NOT IN (
            SELECT customer_id FROM birthday_logs WHERE shop_id = ? AND year = ?
        )
        """
        eligible_customers = conn.execute(query, (shop_id, today_mm_dd, today_mm_dd, shop_id, current_year)).fetchall()

        for cust in eligible_customers:
            cust_name = cust["name"]
            phone = cust["phone"]

            msg = render_template(DEFAULT_BIRTHDAY_TEMPLATE, {
                "customer_name": cust_name,
                "shop_name": shop_name,
                "discount": discount,
                "valid_days": valid_days,
                "city": city
            })

            res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=cust["id"],
                recipient_phone=phone,
                message_text=msg,
                message_type="BIRTHDAY_WISH",
                customer_name=cust_name
            )

            # Record in birthday_logs to prevent duplicate
            try:
                conn.execute(
                    "INSERT INTO birthday_logs (shop_id, customer_id, year) VALUES (?, ?, ?)",
                    (shop_id, cust["id"], current_year)
                )
                conn.commit()
            except Exception:
                pass

            total_sent += 1
            results.append({
                "shop": shop_name,
                "customer": cust_name,
                "phone": phone,
                "status": res.get("status")
            })

    conn.close()
    return {"total_sent": total_sent, "details": results}


def check_and_send_miss_you_reminders(specific_shop_id=None):
    """
    Sends "We Miss You" WhatsApp messages to customers who haven't visited
    in more than shop.miss_you_days days. Sends max once every miss_you_days period.
    """
    conn = get_connection()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if specific_shop_id:
        shops = conn.execute(
            "SELECT * FROM shops WHERE id = ? AND status = 'ACTIVE'", (specific_shop_id,)
        ).fetchall()
    else:
        shops = conn.execute("SELECT * FROM shops WHERE status = 'ACTIVE'").fetchall()

    total_sent = 0
    results = []

    for shop in shops:
        shop_id = shop["id"]
        miss_you_enabled = shop["miss_you_enabled"] if "miss_you_enabled" in shop.keys() else 1
        if not miss_you_enabled:
            continue

        miss_you_days = shop["miss_you_days"] if "miss_you_days" in shop.keys() else 30
        shop_name = shop["sender_display_name"] or shop["name"]
        city = shop["city"] or "our store"

        # Custom template or default
        template = (shop["miss_you_template"] if "miss_you_template" in shop.keys() else "") or DEFAULT_MISS_YOU_TEMPLATE

        # Calculate the cutoff date
        cutoff_date = (now - timedelta(days=int(miss_you_days))).strftime("%Y-%m-%d")

        # Find customers who haven't visited since cutoff_date
        # and haven't received a miss_you reminder in the past miss_you_days days
        customers = conn.execute("""
            SELECT c.* FROM customers c
            WHERE c.shop_id = ?
              AND c.phone IS NOT NULL AND c.phone != ''
              AND (
                  c.last_visit_date IS NULL OR c.last_visit_date < ?
              )
              AND c.id NOT IN (
                  SELECT customer_id FROM reminder_logs
                  WHERE shop_id = ? AND reminder_type = 'MISS_YOU'
                    AND sent_at > datetime('now', ?)
              )
        """, (shop_id, cutoff_date, shop_id, f"-{miss_you_days} days")).fetchall()

        for cust in customers:
            cust_name = cust["name"]
            phone = cust["phone"]
            if not phone:
                continue

            msg = render_template(template, {
                "customer_name": cust_name,
                "shop_name": shop_name,
                "city": city,
                "days": miss_you_days
            })

            res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=cust["id"],
                recipient_phone=phone,
                message_text=msg,
                message_type="MISS_YOU_REMINDER",
                customer_name=cust_name
            )

            # Record log
            try:
                conn.execute(
                    "INSERT INTO reminder_logs (shop_id, customer_id, reminder_type) VALUES (?, ?, 'MISS_YOU')",
                    (shop_id, cust["id"])
                )
                conn.commit()
            except Exception:
                pass

            total_sent += 1
            results.append({
                "shop": shop_name,
                "customer": cust_name,
                "phone": phone,
                "status": res.get("status")
            })

    conn.close()
    return {"total_sent": total_sent, "details": results}


def check_and_send_points_reminders(specific_shop_id=None):
    """
    Sends points redemption reminders to customers who have loyalty points
    but haven't redeemed them within shop.points_reminder_days days.
    """
    conn = get_connection()
    now = datetime.now()

    if specific_shop_id:
        shops = conn.execute(
            "SELECT * FROM shops WHERE id = ? AND status = 'ACTIVE'", (specific_shop_id,)
        ).fetchall()
    else:
        shops = conn.execute("SELECT * FROM shops WHERE status = 'ACTIVE'").fetchall()

    total_sent = 0
    results = []

    for shop in shops:
        shop_id = shop["id"]
        points_reminder_enabled = shop["points_reminder_enabled"] if "points_reminder_enabled" in shop.keys() else 1
        if not points_reminder_enabled:
            continue

        points_reminder_days = shop["points_reminder_days"] if "points_reminder_days" in shop.keys() else 60
        min_points = shop["points_reminder_min_points"] if "points_reminder_min_points" in shop.keys() else 50
        point_redeem_value = shop["point_redeem_value_inr"] or 1.0
        shop_name = shop["sender_display_name"] or shop["name"]
        city = shop["city"] or "our store"

        # Custom template or default
        template = (shop["points_reminder_template"] if "points_reminder_template" in shop.keys() else "") or DEFAULT_POINTS_REMINDER_TEMPLATE

        # Find customers with enough points who haven't been reminded recently
        customers = conn.execute("""
            SELECT c.* FROM customers c
            WHERE c.shop_id = ?
              AND c.phone IS NOT NULL AND c.phone != ''
              AND c.loyalty_points >= ?
              AND c.id NOT IN (
                  SELECT customer_id FROM reminder_logs
                  WHERE shop_id = ? AND reminder_type = 'POINTS_REMINDER'
                    AND sent_at > datetime('now', ?)
              )
        """, (shop_id, int(min_points), shop_id, f"-{points_reminder_days} days")).fetchall()

        for cust in customers:
            cust_name = cust["name"]
            phone = cust["phone"]
            points = cust["loyalty_points"] or 0
            if not phone or points < int(min_points):
                continue

            points_value = int(points * float(point_redeem_value))

            msg = render_template(template, {
                "customer_name": cust_name,
                "shop_name": shop_name,
                "city": city,
                "points": points,
                "points_value": points_value
            })

            res = send_whatsapp_message(
                shop_id=shop_id,
                customer_id=cust["id"],
                recipient_phone=phone,
                message_text=msg,
                message_type="POINTS_REMINDER",
                customer_name=cust_name
            )

            # Record log
            try:
                conn.execute(
                    "INSERT INTO reminder_logs (shop_id, customer_id, reminder_type) VALUES (?, ?, 'POINTS_REMINDER')",
                    (shop_id, cust["id"])
                )
                conn.commit()
            except Exception:
                pass

            total_sent += 1
            results.append({
                "shop": shop_name,
                "customer": cust_name,
                "phone": phone,
                "points": points,
                "status": res.get("status")
            })

    conn.close()
    return {"total_sent": total_sent, "details": results}


def start_background_scheduler():
    """Background daemon thread checking birthdays, miss-you, and points reminders every hour."""
    def run_loop():
        check_interval = 0  # Run immediately on first cycle
        while True:
            try:
                check_and_send_birthday_wishes()
            except Exception as e:
                print(f"[Birthday Scheduler Error]: {e}")
            try:
                check_and_send_miss_you_reminders()
            except Exception as e:
                print(f"[Miss-You Scheduler Error]: {e}")
            try:
                check_and_send_points_reminders()
            except Exception as e:
                print(f"[Points Reminder Scheduler Error]: {e}")
            time.sleep(3600)  # Check every hour

    t = threading.Thread(target=run_loop, daemon=True, name="AutomationCronThread")
    t.start()
    print("Background Birthday Automation Scheduler started.")
