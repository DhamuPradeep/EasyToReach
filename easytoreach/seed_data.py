import json
from datetime import datetime, timedelta
from database import get_connection, init_db

def seed():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing if any
    cursor.execute("DELETE FROM birthday_logs")
    cursor.execute("DELETE FROM whatsapp_logs")
    cursor.execute("DELETE FROM purchases")
    cursor.execute("DELETE FROM campaigns")
    cursor.execute("DELETE FROM customers")
    cursor.execute("DELETE FROM shops")

    # 1. Insert Textile Shops (Tenants)
    shops_data = [
        (
            1,
            "Sri Lakshmi Silks & Sarees",
            "sri-lakshmi-silks",
            "Authentic Kanchipuram & Bridal Wedding Silks",
            "+91 94441 23456",
            "contact@srilakshmisilks.in",
            "142, Gandhi Road, Near Bus Stand",
            "Kanchipuram, Tamil Nadu",
            "",  # whatsapp_phone_number_id (configured via dashboard)
            "",  # whatsapp_business_id
            "",  # whatsapp_access_token
            "Sri Lakshmi Silks",
            5.0, # 5 points per 100 spent (5%)
            1.0, # 1 pt = 1 INR
            15,  # 15% birthday discount
            7,   # 7 days validity
            1
        ),
        (
            2,
            "Royal Menswear & Suiting",
            "royal-menswear",
            "Finest Raymond Suiting, Dhotis & Wedding Kurtas",
            "+91 98422 67890",
            "care@royalmenswear.com",
            "88, Cross Cut Road, Gandhipuram",
            "Coimbatore, Tamil Nadu",
            "",
            "",
            "",
            "Royal Menswear",
            4.0, # 4 points per 100 spent (4%)
            1.0,
            10,  # 10% birthday discount
            5,
            1
        )
    ]

    cursor.executemany("""
    INSERT INTO shops (
        id, name, slug, tagline, phone, email, address, city,
        whatsapp_phone_number_id, whatsapp_business_id, whatsapp_access_token,
        sender_display_name, points_per_100_spent, point_redeem_value_inr,
        birthday_discount_percent, birthday_offer_validity_days,
        auto_birthday_wishes_enabled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, shops_data)

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    in_3_days_str = (now + timedelta(days=3)).strftime("%Y-%m-%d")

    # 2. Insert Customers for Shop 1 (Sri Lakshmi Silks)
    customers_shop1 = [
        # Birthday TODAY!
        (
            1, "Meenakshi Sundaram", "9840112233", f"1990-{now.strftime('%m-%d')}", "2015-05-18",
            "Female", "Bridal Kanchipuram Sarees", 450, 45000.0, 4, today_str,
            "Prefers traditional contrast borders, maroon and gold zari.",
            json.dumps(["VIP", "Bridal", "Silk Lover"])
        ),
        # Birthday TODAY!
        (
            1, "Radhika Ramanathan", "9884223344", f"1994-{now.strftime('%m-%d')}", "2020-02-14",
            "Female", "Soft Silk Sarees", 220, 22000.0, 3, "2026-10-15",
            "Likes pastel shades and light weight silks.",
            json.dumps(["Frequent Buyer"])
        ),
        # Birthday Tomorrow
        (
            1, "Kavitha Balakrishnan", "9445112299", f"1988-{tomorrow_str[5:]}", "2012-11-20",
            "Female", "Tussar & Banarasi", 150, 15000.0, 2, "2026-09-20",
            "Regular festival buyer.",
            json.dumps(["Regular"])
        ),
        # Other regular customers
        (
            1, "Ananya Narayanan", "9790887766", "1998-12-05", "",
            "Female", "Pattu Pavadai & Kurtis", 600, 60000.0, 6, "2026-10-22",
            "Wedding shopping customer.",
            json.dumps(["VIP", "Wedding Shopper"])
        ),
        (
            1, "Deepa Senthil", "9940123987", "1992-04-18", "2018-09-10",
            "Female", "Handloom Cotton Sarees", 80, 8000.0, 1, "2026-08-11",
            "Enquiring about Aadi discount collections.",
            json.dumps(["Handloom"])
        )
    ]

    cursor.executemany("""
    INSERT INTO customers (
        shop_id, name, phone, date_of_birth, anniversary_date,
        gender, category_preference, loyalty_points, total_spent,
        total_visits, last_visit_date, notes, tags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, customers_shop1)

    # 3. Insert Customers for Shop 2 (Royal Menswear)
    customers_shop2 = [
        (
            2, "Rajesh Kumar", "9842111222", f"1987-{now.strftime('%m-%d')}", "2014-06-25",
            "Male", "Raymond Suiting & Blazers", 350, 35000.0, 3, today_str,
            "Tailored suit fitting on record.",
            json.dumps(["VIP", "Executive"])
        ),
        (
            2, "Saravanan Muthu", "9443222333", f"1993-{in_3_days_str[5:]}", "",
            "Male", "Pure Silk Dhotis & Wedding Kurtas", 180, 18000.0, 2, "2026-10-01",
            "Groom purchase.",
            json.dumps(["Wedding Shopper"])
        ),
        (
            2, "Karthik Vijay", "9952333444", "1996-08-12", "2022-12-10",
            "Male", "Linen Shirts & Trousers", 90, 9000.0, 1, "2026-07-15",
            "Casual weekend wear.",
            json.dumps(["Casual"])
        )
    ]

    cursor.executemany("""
    INSERT INTO customers (
        shop_id, name, phone, date_of_birth, anniversary_date,
        gender, category_preference, loyalty_points, total_spent,
        total_visits, last_visit_date, notes, tags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, customers_shop2)

    # 4. Insert Initial Purchases & Point Logs
    purchases_data = [
        (1, 1, "INV-2026-001", 25000.0, 0.0, 25000.0, 1250, 0, "1 Pure Zari Muhurtham Kanchipuram Silk Saree", 1),
        (1, 2, "INV-2026-002", 12000.0, 500.0, 11500.0, 575, 0, "2 Soft Silk Partywear Sarees", 1),
        (2, 6, "INV-2026-101", 18500.0, 0.0, 18500.0, 740, 0, "1 Raymond Custom 2-Piece Suit, 2 Italian Cotton Shirts", 1)
    ]

    cursor.executemany("""
    INSERT INTO purchases (
        shop_id, customer_id, invoice_no, bill_amount, discount_amount,
        net_amount, points_earned, points_redeemed, items_summary, whatsapp_notified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, purchases_data)

    # 5. Insert Sample Festive & New Collection Campaigns
    campaigns_data = [
        (
            1,
            "Deepavali Grand Silk Launch 2026 🪔",
            "FESTIVAL_OFFER",
            "Diwali",
            "✨ *DEEPAVALI GRAND SILK LAUNCH at Sri Lakshmi Silks!* 🪔✨\n\nDear *{{customer_name}}*,\nCelebrate the festival of lights with our newly unveiled *Kanchipuram Pure Zari & Bridal Silk Collections*!\n\n🎁 *Special Festive Offers:*\n• Flat 20% OFF on all Bridal Silk Sarees\n• Free Silver Coin on purchases above ₹25,000\n• Redeem your *{{points}} Loyalty Points* for instant cash discounts!\n\n📍 Visit Sri Lakshmi Silks, Kanchipuram.\n📞 Helpline: +91 94441 23456",
            "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
            "ALL",
            "SENT",
            5,
            5
        ),
        (
            1,
            "Aadi Wedding Carnival - Up to 30% OFF",
            "NEW_COLLECTION",
            "Wedding Season",
            "👗 *New Arrival Alert: Royal Brocade & Pastel Silks* 👗\n\nHello *{{customer_name}}*,\nOur exclusive autumn bridal line has just arrived from our master weavers!\n\nExplore 150+ hand-picked designs in Pastel Mint, Lavender, and Traditional Vermillion Red.\n\n📍 Visit our showroom or reply *CATALOG* to view via WhatsApp.",
            "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80",
            "SAREES",
            "DRAFT",
            0,
            0
        )
    ]

    cursor.executemany("""
    INSERT INTO campaigns (
        shop_id, title, type, festival_name, message_body, media_url,
        target_filter, status, total_recipients, sent_count
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, campaigns_data)

    conn.commit()
    conn.close()
    print("Sample textile database seeded successfully with 2 shops, customers, purchases, and campaigns!")

if __name__ == "__main__":
    seed()

