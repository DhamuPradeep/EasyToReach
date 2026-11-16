import unittest
from database import get_connection, init_db
from scheduler import check_and_send_birthday_wishes, check_and_send_miss_you_reminders, check_and_send_points_reminders
from whatsapp import send_whatsapp_message
import auth

class TestTextileCRM(unittest.TestCase):
    def setUp(self):
        init_db()
        auth.seed_default_users()

    def test_shops_exist(self):
        conn = get_connection()
        shops = conn.execute("SELECT * FROM shops").fetchall()
        self.assertGreaterEqual(len(shops), 2)
        conn.close()

    def test_auth_admin_login(self):
        # Admin can authenticate
        admin_user = auth.authenticate_user("admin", "admin123")
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user["role"], "admin")
        self.assertIsNone(admin_user["shop_id"])

        # Create session
        token, exp = auth.create_session(admin_user)
        self.assertTrue(token.startswith("tpx_"))
        
        # Verify user from token
        verified = auth.get_user_from_token(token)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["username"], "admin")
        self.assertEqual(verified["role"], "admin")

        # Invalidate session
        auth.delete_session(token)
        self.assertIsNone(auth.get_user_from_token(token))

    def test_auth_shop_owner_login_and_isolation(self):
        # Shop owner 1 (Lakshmi) can authenticate and is scoped to shop 1
        lakshmi = auth.authenticate_user("lakshmi", "lakshmi123")
        self.assertIsNotNone(lakshmi)
        self.assertEqual(lakshmi["role"], "shop_owner")
        self.assertEqual(lakshmi["shop_id"], 1)

        # Shop owner 2 (Royal) is scoped to shop 2
        royal = auth.authenticate_user("royal", "royal123")
        self.assertIsNotNone(royal)
        self.assertEqual(royal["role"], "shop_owner")
        self.assertEqual(royal["shop_id"], 2)

        # Invalid password fails
        failed = auth.authenticate_user("lakshmi", "wrongpass")
        self.assertIsNone(failed)

    def test_admin_can_provision_shop_owner(self):
        # Provision new shop owner
        import uuid
        uname = f"testowner_{uuid.uuid4().hex[:6]}"
        email = f"{uname}@example.com"
        res = auth.create_shop_owner_user(uname, email, "Pass@1234", 1, "Test Owner", "+91 99999 11111")
        self.assertTrue(res["success"])

        # Authenticate newly created user
        new_user = auth.authenticate_user(uname, "Pass@1234")
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user["role"], "shop_owner")
        self.assertEqual(new_user["shop_id"], 1)

    def test_birthday_automation(self):
        result = check_and_send_birthday_wishes(specific_shop_id=1)
        self.assertIn("total_sent", result)
        print("Birthday test result:", result)

    def test_miss_you_reminders(self):
        result = check_and_send_miss_you_reminders(specific_shop_id=1)
        self.assertIn("total_sent", result)
        self.assertIn("details", result)
        print("Miss-You reminder test result:", result)

    def test_points_reminders(self):
        result = check_and_send_points_reminders(specific_shop_id=1)
        self.assertIn("total_sent", result)
        self.assertIn("details", result)
        print("Points reminder test result:", result)

    def test_whatsapp_logging(self):
        # Shop 2 has no Meta credentials, verifying fallback Simulation Mode
        res = send_whatsapp_message(
            shop_id=2,
            customer_id=1,
            recipient_phone="9840112233",
            message_text="Test WhatsApp Notification",
            message_type="TEST"
        )
        self.assertTrue(res["success"])
        self.assertIn("SIMULATED", res["status"])
        print("WhatsApp dispatch test result:", res)

    def test_hide_and_unhide_conversation(self):
        conn = get_connection()
        test_phone = "919999988888"
        shop_id = 1

        # 1. Insert a log
        conn.execute("""
            INSERT INTO whatsapp_logs (shop_id, recipient_phone, recipient_name, sender_name, message_text, message_type, direction, is_read)
            VALUES (?, ?, 'Test Customer', 'Shop', 'Hello from shop', 'CHAT', 'OUTBOUND', 1)
        """, (shop_id, test_phone))
        conn.commit()

        # 2. Hide conversation
        conn.execute("""
            INSERT INTO hidden_conversations (shop_id, phone) VALUES (?, ?)
            ON CONFLICT(shop_id, phone) DO UPDATE SET hidden_at = CURRENT_TIMESTAMP
        """, (shop_id, test_phone))
        conn.commit()

        # Check it is hidden in query
        rows = conn.execute("""
            SELECT w.recipient_phone
            FROM whatsapp_logs w
            LEFT JOIN hidden_conversations hc ON (hc.shop_id = w.shop_id AND hc.phone = w.recipient_phone)
            WHERE w.shop_id = ? AND w.recipient_phone = ?
              AND (hc.id IS NULL OR w.sent_at > hc.hidden_at OR (w.direction = 'INBOUND' AND w.is_read = 0))
        """, (shop_id, test_phone)).fetchall()
        self.assertEqual(len(rows), 0, "Conversation should be hidden from list")

        # 3. Simulate customer sends an inbound message
        conn.execute("""
            INSERT INTO whatsapp_logs (shop_id, recipient_phone, recipient_name, sender_name, message_text, message_type, direction, is_read)
            VALUES (?, ?, 'Test Customer', 'Test Customer', 'Hi shop, I have a query!', 'INBOUND', 'INBOUND', 0)
        """, (shop_id, test_phone))
        # Unhide on inbound message
        conn.execute("DELETE FROM hidden_conversations WHERE shop_id = ? AND phone = ?", (shop_id, test_phone))
        conn.commit()

        # Check it is visible again and has unread count
        rows = conn.execute("""
            SELECT w.recipient_phone,
                   (SELECT COUNT(*) FROM whatsapp_logs WHERE shop_id = w.shop_id AND recipient_phone = w.recipient_phone AND direction = 'INBOUND' AND is_read = 0) as unread_count
            FROM whatsapp_logs w
            LEFT JOIN hidden_conversations hc ON (hc.shop_id = w.shop_id AND hc.phone = w.recipient_phone)
            WHERE w.shop_id = ? AND w.recipient_phone = ?
              AND (hc.id IS NULL OR w.sent_at > hc.hidden_at OR (w.direction = 'INBOUND' AND w.is_read = 0))
        """, (shop_id, test_phone)).fetchall()
        self.assertGreaterEqual(len(rows), 1, "Conversation should reappear with notification on inbound message")
        self.assertGreaterEqual(rows[0]["unread_count"], 1)

        # Cleanup
        conn.execute("DELETE FROM whatsapp_logs WHERE recipient_phone = ?", (test_phone,))
        conn.execute("DELETE FROM hidden_conversations WHERE phone = ?", (test_phone,))
        conn.commit()
        conn.close()

    def test_chatbot_flow_save_and_interactive_dispatch(self):
        from app import resolve_custom_auto_reply
        import json

        conn = get_connection()
        shop_id = 1
        flow_data = {
            "nodes": [
                {
                    "id": "node_trigger",
                    "type": "trigger",
                    "title": "Trigger",
                    "keyword": "offer, hi"
                },
                {
                    "id": "node_buttons",
                    "type": "buttons",
                    "title": "Buttons",
                    "message": "Namaste {name}! Do you want 20% OFF today?",
                    "buttons": [
                        {"id": "btn_yes", "title": "Yes, Send Code", "target": "node_yes"},
                        {"id": "btn_no", "title": "No, Thanks", "target": "node_no"}
                    ]
                },
                {
                    "id": "node_yes",
                    "type": "text",
                    "title": "Customer Presses YES",
                    "message": "Awesome! Use code SILK20 at billing for flat 20% discount!"
                },
                {
                    "id": "node_no",
                    "type": "text",
                    "title": "Customer Presses NO",
                    "message": "No worries! Have a lovely day."
                }
            ]
        }
        # 1. Test saving flow to DB
        cur = conn.execute("""
            INSERT INTO chatbot_flows (shop_id, name, trigger_keyword, flow_data_json, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (shop_id, "Test Unit Flow", "offer, hi", json.dumps(flow_data), 1))
        flow_id = cur.lastrowid
        conn.commit()
        self.assertIsNotNone(flow_id)

        # 2. Test sending interactive flow message to customer
        test_phone = "919988776655"
        formatted_buttons = [
            {"id": "btn_yes", "title": "Yes, Send Code", "target": "node_yes", "auto_reply": "Awesome! Use code SILK20 at billing for flat 20% discount!"},
            {"id": "btn_no", "title": "No, Thanks", "target": "node_no", "auto_reply": "No worries! Have a lovely day."}
        ]
        res = send_whatsapp_message(
            shop_id=shop_id,
            customer_id=None,
            recipient_phone=test_phone,
            message_text="Namaste Test User! Do you want 20% OFF today?",
            message_type="INTERACTIVE_FLOW",
            customer_name="Test User",
            buttons=formatted_buttons,
            direction="OUTBOUND"
        )
        self.assertTrue(res.get("success"))

        # 3. Test resolve_custom_auto_reply when customer presses "Yes, Send Code"
        auto_reply = resolve_custom_auto_reply(shop_id, None, test_phone, "btn_yes", "Yes, Send Code")
        self.assertIsNotNone(auto_reply)
        self.assertIn("SILK20", auto_reply)

        # 4. Test resolve_custom_auto_reply when customer presses "No, Thanks"
        auto_reply_no = resolve_custom_auto_reply(shop_id, None, test_phone, "btn_no", "No, Thanks")
        self.assertIsNotNone(auto_reply_no)
        self.assertIn("No worries", auto_reply_no)

        # Cleanup
        conn.execute("DELETE FROM chatbot_flows WHERE id = ?", (flow_id,))
        conn.execute("DELETE FROM whatsapp_logs WHERE recipient_phone = ?", (test_phone,))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    unittest.main()

