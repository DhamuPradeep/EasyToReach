// API Client for Textile WhatsApp CRM & Marketing
const API = {
  activeShopId: 1,

  setActiveShop(id) {
    this.activeShopId = parseInt(id);
    localStorage.setItem("textile_active_shop_id", this.activeShopId);
  },

  getActiveShop() {
    const saved = localStorage.getItem("textile_active_shop_id");
    if (saved) this.activeShopId = parseInt(saved);
    return this.activeShopId;
  },

  async request(endpoint, options = {}) {
    const token = localStorage.getItem("textile_token");
    const defaultHeaders = {
      "Content-Type": "application/json"
    };
    if (token) {
      defaultHeaders["Authorization"] = token;
    }
    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      config.body = JSON.stringify(options.body);
    }
    try {
      const response = await fetch(endpoint, config);
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401 && endpoint !== "/api/auth/login" && endpoint !== "/api/auth/me") {
          localStorage.removeItem("textile_token");
          localStorage.removeItem("textile_user");
          window.location.replace("/login");
        }
        throw new Error(data.error || `HTTP error ${response.status}`);
      }
      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  },

  // Authentication & RBAC
  getCurrentUser() {
    return this.request("/api/auth/me");
  },

  login(username, password) {
    return this.request("/api/auth/login", {
      method: "POST",
      body: { username, password }
    });
  },

  logout() {
    return this.request("/api/auth/logout", {
      method: "POST"
    });
  },

  getAdminUsers() {
    return this.request("/api/admin/users");
  },

  createAdminUser(userData) {
    return this.request("/api/admin/users", {
      method: "POST",
      body: userData
    });
  },

  toggleAdminUserStatus(userId, status) {
    return this.request(`/api/admin/users/${userId}/status`, {
      method: "PUT",
      body: { status }
    });
  },

  deleteAdminUser(userId) {
    return this.request(`/api/admin/users/${userId}`, {
      method: "DELETE"
    });
  },

  // Shops
  getShops() {
    return this.request("/api/shops");
  },

  getShop(id) {
    return this.request(`/api/shops/${id}`);
  },

  createShop(shopData) {
    return this.request("/api/shops", { method: "POST", body: shopData });
  },

  deleteShop(id) {
    return this.request(`/api/shops/${id}`, { method: "DELETE" });
  },

  updateShop(id, shopData) {
    return this.request(`/api/shops/${id}`, { method: "PUT", body: shopData });
  },

  updateShopSubscription(data) {
    return this.request("/api/admin/shops/subscription", { method: "POST", body: data });
  },

  // Dashboard Stats
  getStats() {
    return this.request(`/api/dashboard/stats?shop_id=${this.getActiveShop()}`);
  },

  // Customers
  getCustomers(search = "", tag = "") {
    const params = new URLSearchParams({
      shop_id: this.getActiveShop(),
      search: search,
      tag: tag
    });
    return this.request(`/api/customers?${params.toString()}`);
  },

  createCustomer(custData) {
    return this.request("/api/customers", {
      method: "POST",
      body: { ...custData, shop_id: this.getActiveShop() }
    });
  },

  updateCustomer(id, custData) {
    return this.request(`/api/customers/${id}`, { method: "PUT", body: custData });
  },

  deleteCustomer(id) {
    return this.request(`/api/customers/${id}`, { method: "DELETE" });
  },

  importCSV(csvContent) {
    return this.request("/api/customers/import-csv", {
      method: "POST",
      body: { shop_id: this.getActiveShop(), csv_content: csvContent }
    });
  },

  syncCloudSheet(sheetUrl) {
    return this.request(`/api/shops/${this.getActiveShop()}/sync-cloud`, {
      method: "POST",
      body: { sheet_url: sheetUrl }
    });
  },

  getCustomerPurchases(customerId) {
    return this.request(`/api/customers/${customerId}/purchases`);
  },

  // POS / Quick Billing & Points
  recordPurchase(purchaseData) {
    return this.request("/api/billing/purchase", {
      method: "POST",
      body: { ...purchaseData, shop_id: this.getActiveShop() }
    });
  },

  // Birthdays
  getBirthdays() {
    return this.request(`/api/birthdays/today?shop_id=${this.getActiveShop()}`);
  },

  sendBirthdayWishes() {
    return this.request("/api/birthdays/send", {
      method: "POST",
      body: { shop_id: this.getActiveShop() }
    });
  },

  // Marketing Campaigns (Festivals & New Collections)
  getCampaigns() {
    return this.request(`/api/campaigns?shop_id=${this.getActiveShop()}`);
  },

  broadcastCampaign(campaignData) {
    return this.request("/api/campaigns/broadcast", {
      method: "POST",
      body: { ...campaignData, shop_id: this.getActiveShop() }
    });
  },

  // WhatsApp Logs & Simulator
  getWhatsAppLogs(limit = 50, days = 3) {
    return this.request(`/api/whatsapp/logs?shop_id=${this.getActiveShop()}&limit=${limit}&days=${days}`);
  },

  sendDirectWhatsApp(recipientPhone, messageText, customerName = "Customer", mediaUrl = null) {
    return this.request("/api/whatsapp/send-direct", {
      method: "POST",
      body: {
        shop_id: this.getActiveShop(),
        recipient_phone: recipientPhone,
        message_text: messageText,
        customer_name: customerName,
        media_url: mediaUrl
      }
    });
  },

  // ── Two-Way Conversations ──
  getConversations() {
    return this.request(`/api/conversations?shop_id=${this.getActiveShop()}`);
  },
  getConversationMessages(phone) {
    return this.request(`/api/conversations/messages?shop_id=${this.getActiveShop()}&phone=${encodeURIComponent(phone)}`);
  },
  sendChatMessage(data) {
    return this.request("/api/conversations/send", { method: "POST", body: { ...data, shop_id: this.getActiveShop() } });
  },
  simulateInboundReply(data) {
    return this.request("/api/conversations/simulate-inbound", { method: "POST", body: { ...data, shop_id: this.getActiveShop() } });
  },
  markConversationRead(phone) {
    return this.request(`/api/conversations/mark-read?shop_id=${this.getActiveShop()}&phone=${encodeURIComponent(phone)}`, { method: "POST" });
  },
  hideConversation(phone) {
    return this.request("/api/conversations/hide", {
      method: "POST",
      body: { shop_id: this.getActiveShop(), phone }
    });
  },
  unhideConversation(phone) {
    return this.request("/api/conversations/unhide", {
      method: "POST",
      body: { shop_id: this.getActiveShop(), phone }
    });
  },
  searchCustomersForChat(q) {
    return this.request(`/api/conversations/customer-search?shop_id=${this.getActiveShop()}&q=${encodeURIComponent(q || "")}`);
  },
  triggerMissYouReminders() {
    return this.request(`/api/reminders/miss-you?shop_id=${this.getActiveShop()}`);
  },
  triggerPointsReminders() {
    return this.request(`/api/reminders/points?shop_id=${this.getActiveShop()}`);
  }
};

