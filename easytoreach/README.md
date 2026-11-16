# EasyToReach - Multi-Tenant WhatsApp CRM & Marketing for Textile Retailers

A full-stack WhatsApp automation and CRM platform tailored specifically for **textile and garment retail stores** (Saree showrooms, Menswear, Bridal collections, Readymades).

---

## 🌟 Key Features

### 1. Multi-Tenant Architecture (Multiple Textile Shops)
* Supports multiple independent textile shops on a single installation.
* Each shop has its own:
  * Customer database, purchase histories, and notes.
  * **Sender Identity**: Messages appear from each shop's unique registered name (e.g. *"Sri Lakshmi Silks"*, *"Royal Menswear"*).
  * Individual **Meta WhatsApp Cloud API** credentials (`Phone Number ID`, `WABA ID`, `Access Token`).
  * Customizable loyalty rules (e.g., 5 points per ₹100 spent) and birthday discount percentages.

### 2. Customer Relationship Management (CRM)
* Stores customer phone numbers, birthdays, wedding anniversaries, gender, shopping preferences (e.g., *Bridal Kanchipuram*, *Soft Silk*, *Raymond Suiting*), notes, and tags (`VIP`, `Bridal`, `Frequent Buyer`).
* **Bulk CSV Import**: Import existing customer contacts with one click using the built-in CSV uploader.
* **Instant Welcome Opt-in**: Automatically dispatches a welcome WhatsApp greeting with initial loyalty points when a customer is added.

### 3. Automated Birthday & Anniversary Offers
* **Automated Daily Scheduler**: Runs every morning to check for customers celebrating birthdays today.
* **Smart Anti-Spam Tracking**: Records sent greetings in `birthday_logs` to ensure customers only receive one birthday offer per calendar year.
* **Personalized Discount Vouchers**: Sends an exclusive discount offer (e.g. 15% OFF) valid for 7 days with store details.

### 4. Festive & New Collections Broadcasts
* Launch marketing campaigns for **Diwali, Pongal, Wedding Season, Eid, Aadi Sale**, or **New Silk Arrivals**.
* Attach lookbook / catalog flyer images directly into the WhatsApp message.
* Dynamic variable replacement: `{{customer_name}}`, `{{shop_name}}`, `{{points}}`, `{{city}}`.
* **Audience Segmentation**: Broadcast to all customers or filter by *VIPs*, *Silk Lovers*, or *High Loyalty Points*.

### 5. Cashier Billing POS & Loyalty Points System
* Store cashier enters the customer's phone number -> system auto-retrieves customer points.
* Calculates points earned on the bill (e.g., 5% cashback in loyalty points).
* Instant points redemption against the invoice.
* **Instant WhatsApp Digital Receipt**: Sends a digital receipt with invoice number, items summary, net paid, points earned today, and total available balance.

### 6. WhatsApp Dispatcher & Live Smartphone Simulator
* Directly integrates with the official **Meta WhatsApp Cloud API**.
* **Zero-Setup Simulation Mode**: If Meta credentials are not entered yet, the system operates in test simulation mode, saving full message logs and rendering real-time message previews in the interactive smartphone mockup.

---

## 🚀 Quick Start

### 1. Run the Platform
```bash
# Start database and web server
./run.sh

# Or directly with Python
python3 app.py
```

### 2. Access the Dashboard
Open your browser and navigate to:
```
http://localhost:5050
```

---

## 📁 Project Structure

```
customer/
├── app.py                      # Multi-threaded HTTP server & REST API
├── database.py                 # SQLite schema, tables & indexes
├── scheduler.py                # Automated birthday & anniversary background scheduler
├── whatsapp.py                 # Meta WhatsApp Cloud API dispatcher & simulator
├── seed_data.py                # Demo textile stores & sample customers
├── test_crm.py                 # Automated unit tests
├── run.sh                      # One-click start script
├── samples/
│   └── customers_sample.csv    # Sample customer CSV format for bulk import
└── static/
    ├── index.html              # Responsive dashboard UI
    ├── css/
    │   └── style.css           # Luxury textile theme & WhatsApp phone mockup
    └── js/
        ├── app.js              # Application controller & view router
        ├── api.js              # API client methods
        └── data.js             # Pre-configured festive & new collection templates
```

---

## 📱 Meta WhatsApp Cloud API Setup (Per Shop)

To deliver messages directly to customers' real WhatsApp accounts:

1. Create a Meta Developer App at [developers.facebook.com](https://developers.facebook.com).
2. Add the **WhatsApp** product.
3. In the EasyToReach Dashboard, navigate to **Shop & API Settings**:
   * **Sender Display Name**: Enter your registered textile showroom name.
   * **Meta Phone Number ID**: Paste your Meta Phone Number ID.
   * **WhatsApp Business Account ID**: Paste your WABA ID.
   * **System User Access Token**: Paste your permanent Meta token.
4. Click **Save Shop Settings**.

