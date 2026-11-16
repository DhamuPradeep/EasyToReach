// ============================================================
// EasyToReach — Main Application Controller
// ============================================================
const App = {
  currentUser: null,
  currentShop: null,
  allCustomers: [],
  selectedCustomerForBilling: null,
  currentTheme: 'light',

  initTheme() {
    const savedTheme = localStorage.getItem("textile_theme") || 
      (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    this.applyTheme(savedTheme, false);
  },

  toggleTheme() {
    const nextTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.applyTheme(nextTheme, true);
    this.showToast(`Switched to ${nextTheme === 'dark' ? 'Dark' : 'Light'} Mode`, "info");
  },

  applyTheme(theme, animate = true) {
    this.currentTheme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem("textile_theme", theme);

    const icon = document.getElementById("themeIcon");
    const label = document.getElementById("themeLabel");
    if (icon) {
      if (animate) {
        icon.classList.remove("icon-spin");
        void icon.offsetWidth; // trigger reflow for animation restart
        icon.classList.add("icon-spin");
        setTimeout(() => icon.classList.remove("icon-spin"), 600);
      }
      if (theme === "dark") {
        icon.className = "fa-solid fa-sun";
        if (label) label.textContent = "Light Mode";
      } else {
        icon.className = "fa-solid fa-moon";
        if (label) label.textContent = "Dark Mode";
      }
    }
  },

  async init() {
    try {
      this.initTheme();
      await this.checkAuth();
      await this.loadShops();
      this.populateTemplateOptions();
      if (this.currentUser && this.currentUser.role === "admin") {
        this.switchTab("tab-admin-overview");
        await this.loadAdminOverview();
      } else {
        this.switchTab("tab-dashboard");
        await this.loadDashboardData();
      }
      // Start background polling for conversation updates and unread badges
      this.startConversationPolling();

      // Enter key to send manual chat in conversations
      document.getElementById("chatTextInput")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          App.sendManualChat();
        }
      });
    } catch (err) {
      console.error("Init error:", err);
      this.showToast("Failed to initialize: " + err.message, "danger");
    }
  },

  async checkAuth() {
    let user = null;
    try {
      const res = await API.getCurrentUser();
      if (res && res.authenticated) {
        user = res.user;
        localStorage.setItem("textile_user", JSON.stringify(user));
      } else {
        localStorage.removeItem("textile_token");
        localStorage.removeItem("textile_user");
        window.location.replace("/login");
        return;
      }
    } catch (_) {
      const stored = localStorage.getItem("textile_user");
      if (stored) {
        try { user = JSON.parse(stored); } catch (_) {}
      }
    }

    if (!user) {
      localStorage.removeItem("textile_token");
      localStorage.removeItem("textile_user");
      window.location.replace("/login");
      return;
    }

    this.currentUser = user;
    this.renderUserProfile();
  },

  renderUserProfile() {
    const user = this.currentUser;
    if (!user) return;

    const nameEl = document.getElementById("userDisplayName");
    const roleEl = document.getElementById("userRoleBadge");
    const iconEl = document.getElementById("userAvatarIcon");
    const adminNavBtn = document.getElementById("adminUsersNavBtn");
    const adminTopBtn = document.getElementById("adminStoreAccountsTopBtn");
    const shopSelectContainer = document.getElementById("shopSelectContainer");
    const lockedBox = document.getElementById("lockedShopContainer");
    const lockedNameEl = document.getElementById("lockedShopName");
    const shopAddBtn = document.getElementById("shopAddBtn");
    const settingsNavBtn = document.getElementById("settingsNavBtn");
    const contactAdminBtn = document.getElementById("contactAdminNavBtn");
    const adminOverviewBtn = document.getElementById("adminOverviewNavBtn");

    if (nameEl) nameEl.textContent = user.full_name || user.username;

    if (user.role === "admin") {
      if (roleEl) {
        roleEl.className = "user-role-badge";
        roleEl.innerHTML = `<i class="fa-solid fa-crown" style="color:var(--gold);"></i> Admin`;
      }
      if (iconEl) {
        iconEl.className = "user-avatar-icon";
        iconEl.innerHTML = `<i class="fa-solid fa-crown"></i>`;
      }
      if (adminNavBtn) adminNavBtn.style.display = "flex";
      if (adminTopBtn) adminTopBtn.style.display = "inline-flex";
      if (shopSelectContainer) shopSelectContainer.style.display = "block";
      if (lockedBox) lockedBox.style.display = "none";
      if (shopAddBtn) shopAddBtn.style.display = "flex";
      if (settingsNavBtn) settingsNavBtn.style.display = "flex";
      if (contactAdminBtn) contactAdminBtn.style.display = "none";
      if (adminOverviewBtn) {
        adminOverviewBtn.style.display = "flex";
        adminOverviewBtn.innerHTML = '<i class="fa-solid fa-gauge-high"></i> <span>EasyToReach Dashboard</span>';
      }
      const platformSectionLabel = document.getElementById("platformSectionLabel");
      if (platformSectionLabel) platformSectionLabel.style.display = "block";
    } else {
      // shop_owner
      if (roleEl) {
        roleEl.className = "user-role-badge owner";
        roleEl.innerHTML = `<i class="fa-solid fa-store" style="color:#10b981;"></i> Owner`;
      }
      if (iconEl) {
        iconEl.className = "user-avatar-icon shop-owner";
        iconEl.innerHTML = `<i class="fa-solid fa-store"></i>`;
      }
      if (adminNavBtn) adminNavBtn.style.display = "none";
      if (adminTopBtn) adminTopBtn.style.display = "none";
      if (shopSelectContainer) shopSelectContainer.style.display = "none";
      if (lockedBox) lockedBox.style.display = "block";
      if (lockedNameEl) lockedNameEl.textContent = user.shop_name || "Assigned Store";
      if (shopAddBtn) shopAddBtn.style.display = "none";
      if (settingsNavBtn) settingsNavBtn.style.display = "none";
      if (contactAdminBtn) contactAdminBtn.style.display = "flex";
      if (adminOverviewBtn) {
        adminOverviewBtn.style.display = "none";
      }
      const platformSectionLabel = document.getElementById("platformSectionLabel");
      if (platformSectionLabel) platformSectionLabel.style.display = "none";
      const platformDivider = document.getElementById("platformDivider");
      if (platformDivider) platformDivider.style.display = "none";

      if (user.shop_id) {
        API.setActiveShop(user.shop_id);
      }
    }
  },

  async handleLogout() {
    try {
      await API.logout();
    } catch (_) {}
    localStorage.removeItem("textile_token");
    localStorage.removeItem("textile_user");
    window.location.href = "/login";
  },

  // ======================== TABS ========================
  handleEasyToReachDashboardClick() {
    if (this.currentUser && this.currentUser.role === "shop_owner") {
      this.switchTab("tab-dashboard");
    } else {
      this.switchTab("tab-admin-overview");
    }
  },

  handleEasyReachDashboardClick() {
    this.handleEasyToReachDashboardClick();
  },

  toggleShopMenu(forceState) {
    const group = document.getElementById("shopNavGroup");
    if (!group) return;
    if (forceState !== undefined) {
      if (forceState) {
        group.classList.remove("collapsed");
      } else {
        group.classList.add("collapsed");
      }
    } else {
      group.classList.toggle("collapsed");
      if (!group.classList.contains("collapsed")) {
        const activeTab = document.querySelector(".tab-pane.active");
        if (activeTab && activeTab.id === "tab-admin-overview") {
          this.switchTab("tab-dashboard");
        }
      }
    }
  },

  toggleMobileSidebar() {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (sidebar) sidebar.classList.toggle("open");
    if (backdrop) backdrop.classList.toggle("open");
  },

  closeMobileSidebar() {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("open");
  },

  switchTab(tabId) {
    this.closeMobileSidebar();
    if (this.currentUser && this.currentUser.role === "shop_owner") {
      if (tabId === "tab-settings" || tabId === "tab-admin-overview" || tabId === "tab-accounts") {
        tabId = "tab-dashboard";
      }
    }
    const contentBody = document.querySelector(".content-body");
    if (contentBody) {
      if (tabId === "tab-conversations") {
        contentBody.classList.add("conversations-active");
      } else {
        contentBody.classList.remove("conversations-active");
      }
    }
    document.querySelectorAll(".tab-pane").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    const target = document.getElementById(tabId);
    if (target) target.classList.add("active");
    const navLink = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (navLink) navLink.classList.add("active");

    // Parent Shop highlight and auto-expand
    const shopParent = document.getElementById("shopParentNavBtn");
    const shopTabs = ["tab-dashboard", "tab-customers", "tab-billing", "tab-birthdays", "tab-campaigns", "tab-logs", "tab-conversations", "tab-flow-builder", "tab-settings"];
    if (shopTabs.includes(tabId)) {
      if (shopParent) shopParent.classList.add("parent-active");
      this.toggleShopMenu(true);
    } else {
      if (shopParent) shopParent.classList.remove("parent-active");
    }

    if (tabId === "tab-flow-builder" && window.FlowBuilder) {
      window.FlowBuilder.init();
    }

    const titles = {
      "tab-dashboard": ["Shop Dashboard", "Overview & Key Store Metrics"],
      "tab-customers": ["Customers", "Manage profiles, birthdays & preferences"],
      "tab-billing": ["Billing & Points", "Record sales & dispatch WhatsApp receipts"],
      "tab-birthdays": ["Birthday Offers", "Automated wishes & exclusive discount vouchers"],
      "tab-campaigns": ["Campaigns", "Festival & new collection broadcasts"],
      "tab-logs": ["WhatsApp Logs", "Message audit trail & delivery status"],
      "tab-conversations": ["Conversations", "Two-way WhatsApp customer chat"],
      "tab-flow-builder": ["Bot Flow Builder", "Visually design interactive WhatsApp button responses & automated flows"],
      "tab-settings": ["Shop Settings", "Shop profile & Meta WhatsApp API configuration"],
      "tab-admin-overview": ["EasyToReach Dashboard", "Consolidated metrics across all registered shops"],
      "tab-accounts": ["Store Accounts", "User logins, shop access control & showroom directory"]
    };

    // Update Topbar Store Tag & Title cleanly without overflow
    const storeTag = document.getElementById("topbarStoreTag");
    const storeNameEl = document.getElementById("topbarStoreName");
    if (shopTabs.includes(tabId) && this.currentShop) {
      if (storeTag) storeTag.style.display = "inline-flex";
      if (storeNameEl) storeNameEl.textContent = this.currentShop.name;
    } else {
      if (storeTag) storeTag.style.display = "none";
    }

    if (titles[tabId]) {
      document.getElementById("pageTitle").textContent = titles[tabId][0];
      document.getElementById("pageSubtitle").textContent = titles[tabId][1];
    }

    const loaders = {
      "tab-dashboard": () => this.loadDashboardData(),
      "tab-customers": () => this.loadCustomers(),
      "tab-billing": () => this.loadBillingCustomers(),
      "tab-birthdays": () => this.loadBirthdays(),
      "tab-campaigns": () => { this.loadCampaignsHistory(); this.updateCampaignAudienceEstimate(); },
      "tab-logs": () => this.loadWhatsAppLogs(),
      "tab-conversations": () => { this.loadConversations(); this.startConversationPolling(); },
      "tab-settings": () => this.loadShopSettings(),
      "tab-admin-overview": () => this.loadAdminOverview(),
      "tab-accounts": () => this.loadStoreAccountsPage()
    };
    if (tabId !== "tab-conversations") {
      this.stopConversationPolling();
    }
    if (loaders[tabId]) loaders[tabId]();
  },

  // ======================== SHOPS ========================
  async loadShops() {
    const data = await API.getShops();
    const select = document.getElementById("shopSelect");
    if (select) select.innerHTML = "";

    // If shop owner, strictly use assigned shop
    if (this.currentUser && this.currentUser.role === "shop_owner" && this.currentUser.shop_id) {
      API.setActiveShop(this.currentUser.shop_id);
      if (data.shops && data.shops.length > 0) {
        const lockedNameEl = document.getElementById("lockedShopName");
        if (lockedNameEl) lockedNameEl.textContent = data.shops[0].name;
      }
    } else {
      const activeId = API.getActiveShop();
      let found = false;
      if (data.shops) {
        data.shops.forEach(shop => {
          const opt = document.createElement("option");
          opt.value = shop.id;
          opt.textContent = `${shop.name} — ${shop.city || 'Store'}`;
          if (shop.id === activeId) { opt.selected = true; found = true; }
          if (select) select.appendChild(opt);
        });
      }
      if (!found && data.shops && data.shops.length > 0) {
        API.setActiveShop(data.shops[0].id);
        if (select) select.value = data.shops[0].id;
      }
    }
    await this.fetchActiveShopDetails();
  },

  async handleShopChange(shopId) {
    API.setActiveShop(shopId);
    await this.fetchActiveShopDetails();
    this.showToast(`Switched to: ${this.currentShop.name}`, "info");
    this.switchTab("tab-dashboard");
  },

  async fetchActiveShopDetails() {
    const data = await API.getShop(API.getActiveShop());
    this.currentShop = data.shop;
    document.getElementById("currentShopNameDisplay").textContent = this.currentShop.sender_display_name || this.currentShop.name;
    const pill = document.getElementById("sidebarActiveShopPill");
    if (pill) pill.textContent = this.currentShop.name || "Store";
    const initials = (this.currentShop.name || "TP").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
    ["mockupHeaderAvatar", "campMockupAvatar"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = initials;
    });
    const displayName = this.currentShop.sender_display_name || this.currentShop.name;
    ["mockupHeaderName", "campMockupName"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `${displayName} <i class="fa-solid fa-circle-check" style="color:#25d366; font-size:0.7rem;"></i>`;
    });
  },

  // ======================== DASHBOARD ========================
  animateCounter(el, target, prefix = "", suffix = "") {
    const start = 0;
    const duration = 800;
    const startTime = performance.now();
    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + (target - start) * eased);
      el.textContent = prefix + current.toLocaleString("en-IN") + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  },

  // ======================== ERROR FORMATTER ========================
  formatMetaError(errStr) {
    if (!errStr) return "Failed";
    if (errStr.includes("131030") || errStr.includes("not in allowed list")) {
      return "Meta Test Number: Recipient not in Meta whitelist (Add in Meta Step 1)";
    }
    if (errStr.includes("190") || errStr.includes("Session has expired") || errStr.includes("Error validating access token")) {
      return "Meta Access Token expired (Generate new token in Meta portal)";
    }
    if (errStr.includes("132001") || errStr.includes("template")) {
      return "Template not approved in Meta WhatsApp Manager";
    }
    if (errStr.includes("131026")) {
      return "Message undeliverable (Number not active on WhatsApp)";
    }
    try {
      const match = errStr.match(/HTTP \d+: (\{.*\})/);
      if (match) {
        const parsed = JSON.parse(match[1]);
        if (parsed.error && parsed.error.message) return parsed.error.message;
      }
    } catch (_) {}
    return errStr.substring(0, 80) + (errStr.length > 80 ? '...' : '');
  },

  async loadDashboardData() {
    try {
      const stats = await API.getStats();
      this.animateCounter(document.getElementById("statCustomers"), stats.total_customers);
      this.animateCounter(document.getElementById("statMessages"), stats.messages_dispatched);
      document.getElementById("statBirthdays").textContent = stats.today_birthdays;

      const bdayBadge = document.getElementById("navBirthdayBadge");
      if (stats.today_birthdays > 0) { bdayBadge.textContent = stats.today_birthdays; bdayBadge.style.display = "flex"; }
      else { bdayBadge.style.display = "none"; }

      const logsData = await API.getWhatsAppLogs(5);
      const container = document.getElementById("recentActivityList");
      container.innerHTML = "";
      if (logsData.logs.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="fa-solid fa-inbox"></i><p>No messages sent yet</p></div>';
      } else {
        logsData.logs.forEach(log => {
          const item = document.createElement("div");
          item.className = "activity-item";
          const errorHtml = (log.status === "FAILED" && log.error_message) 
            ? `<div style="font-size:0.72rem; color:var(--danger); margin-top:5px; background:rgba(239, 68, 68, 0.08); padding:4px 8px; border-radius:6px; border:1px solid rgba(239, 68, 68, 0.2);"><i class="fa-solid fa-triangle-exclamation"></i> ${this.formatMetaError(log.error_message)}</div>`
            : "";
          item.innerHTML = `
            <div class="activity-top">
              <span class="activity-name">${log.recipient_name || log.recipient_phone}</span>
              <span class="status-badge status-${log.status.toLowerCase()}">${log.status}</span>
            </div>
            <div class="activity-type">${log.message_type} · ${log.sent_at}</div>
            <div class="activity-preview">${log.message_text.replace(/\n/g, ' ')}</div>
            ${errorHtml}
          `;
          container.appendChild(item);
        });
      }
    } catch (err) { console.error("Dashboard error:", err); }
  },

  // ======================== CUSTOMERS ========================
  async loadCustomers() {
    const search = document.getElementById("custSearchInput").value;
    const tag = document.getElementById("custTagFilter").value;
    const data = await API.getCustomers(search, tag);
    this.allCustomers = data.customers;
    this.updateCampaignAudienceEstimate();
    const tbody = document.getElementById("customersTableBody");
    tbody.innerHTML = "";
    if (data.customers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><i class="fa-solid fa-users"></i><p>No customers found</p></div></td></tr>';
      return;
    }
    data.customers.forEach(c => {
      const tr = document.createElement("tr");
      const tagsHtml = (c.tags || []).map(t => {
        let cls = "tag-regular";
        if (t === "VIP") cls = "tag-vip";
        else if (t.includes("Silk") || t.includes("Bridal")) cls = "tag-silk";
        else if (t.includes("Wedding")) cls = "tag-wedding";
        return `<span class="tag ${cls}">${t}</span>`;
      }).join("");
      tr.innerHTML = `
        <td><strong>${c.name}</strong><br><small style="color:var(--slate-400);">${c.gender || ''}</small></td>
        <td><a href="https://wa.me/${c.phone}" target="_blank" style="color:var(--wa-teal); text-decoration:none; font-weight:600;"><i class="fa-brands fa-whatsapp"></i> +${c.phone}</a></td>
        <td>🎂 ${c.date_of_birth || '-'}${c.anniversary_date ? '<br>💍 ' + c.anniversary_date : ''}</td>
        <td style="font-size:0.84rem;">${c.category_preference || 'Silk Sarees'}</td>
        <td><strong style="color:var(--accent-600);">${c.loyalty_points || 0} pts</strong></td>
        <td>₹${(c.total_spent || 0).toLocaleString()}</td>
        <td>${tagsHtml}</td>
        <td>
          <div style="display:flex; gap:4px;">
            <button class="btn btn-ghost btn-icon" onclick="App.openEditCustomer(${c.id})" title="Edit"><i class="fa-solid fa-pen-to-square"></i></button>
            <button class="btn btn-ghost btn-icon" onclick="App.openDirectWhatsAppTo('${c.phone}', '${c.name}')" title="WhatsApp" style="color:var(--wa-green);"><i class="fa-brands fa-whatsapp"></i></button>
            <button class="btn btn-ghost btn-icon" onclick="App.deleteCustomer(${c.id})" title="Delete" style="color:var(--danger);"><i class="fa-solid fa-trash"></i></button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  },

  openAddCustomerModal() {
    document.getElementById("customerForm").reset();
    document.getElementById("custFormId").value = "";
    document.getElementById("customerModalTitle").innerHTML = '<i class="fa-solid fa-user-plus" style="color:var(--accent-600);"></i> Add Customer';
    document.getElementById("welcomeMsgCheckGroup").style.display = "flex";
    document.getElementById("customerModal").classList.add("open");
  },

  openEditCustomer(id) {
    const c = this.allCustomers.find(x => x.id === id);
    if (!c) return;
    document.getElementById("custFormId").value = c.id;
    document.getElementById("custFormName").value = c.name;
    document.getElementById("custFormPhone").value = c.phone;
    document.getElementById("custFormDob").value = c.date_of_birth || "";
    document.getElementById("custFormAnniv").value = c.anniversary_date || "";
    document.getElementById("custFormGender").value = c.gender || "Female";
    document.getElementById("custFormPref").value = c.category_preference || "Bridal Kanchipuram Sarees";
    document.getElementById("custFormPoints").value = c.loyalty_points || 0;
    document.getElementById("custFormTags").value = (c.tags || []).join(", ");
    document.getElementById("custFormNotes").value = c.notes || "";
    document.getElementById("welcomeMsgCheckGroup").style.display = "none";
    document.getElementById("customerModalTitle").innerHTML = '<i class="fa-solid fa-user-pen" style="color:var(--accent-600);"></i> Edit Customer';
    document.getElementById("customerModal").classList.add("open");
  },

  closeCustomerModal() { document.getElementById("customerModal").classList.remove("open"); },

  async handleCustomerSubmit(e) {
    e.preventDefault();
    const id = document.getElementById("custFormId").value;
    const payload = {
      name: document.getElementById("custFormName").value.trim(),
      phone: document.getElementById("custFormPhone").value.trim(),
      date_of_birth: document.getElementById("custFormDob").value,
      anniversary_date: document.getElementById("custFormAnniv").value,
      gender: document.getElementById("custFormGender").value,
      category_preference: document.getElementById("custFormPref").value,
      loyalty_points: parseInt(document.getElementById("custFormPoints").value) || 0,
      notes: document.getElementById("custFormNotes").value.trim(),
      tags: document.getElementById("custFormTags").value.split(",").map(t => t.trim()).filter(Boolean)
    };
    try {
      if (id) {
        await API.updateCustomer(id, payload);
        this.showToast("Customer updated!", "success");
      } else {
        payload.send_welcome_whatsapp = document.getElementById("custSendWelcome").checked;
        await API.createCustomer(payload);
        this.showToast("Customer added & welcome sent!", "success");
      }
      this.closeCustomerModal();
      this.loadCustomers();
    } catch (err) { this.showToast(err.message, "danger"); }
  },

  async deleteCustomer(id) {
    if (!confirm("Delete this customer?")) return;
    try { await API.deleteCustomer(id); this.showToast("Customer removed", "info"); this.loadCustomers(); }
    catch (err) { this.showToast(err.message, "danger"); }
  },

  // ======================== CSV ========================
  openCsvModal() { document.getElementById("csvFileInput").value = ""; document.getElementById("csvRawText").value = ""; document.getElementById("csvModal").classList.add("open"); },
  closeCsvModal() { document.getElementById("csvModal").classList.remove("open"); },
  handleCsvFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => { document.getElementById("csvRawText").value = ev.target.result; };
    reader.readAsText(file);
  },
  async submitCsvImport() {
    const content = document.getElementById("csvRawText").value.trim();
    if (!content) { this.showToast("Provide CSV content", "warning"); return; }
    try {
      const res = await API.importCSV(content);
      this.showToast(`Imported ${res.imported_count} customers!`, "success");
      this.closeCsvModal(); this.loadCustomers();
    } catch (err) { this.showToast("Import failed: " + err.message, "danger"); }
  },

  exportCustomersCSV() {
    if (!this.allCustomers || this.allCustomers.length === 0) {
      this.showToast("No customer records to export", "warning");
      return;
    }
    const headers = ["Name", "Phone", "Date of Birth", "Anniversary", "Gender", "Category Preference", "Loyalty Points", "Total Spent", "Visits", "Tags", "Notes"];
    const rows = this.allCustomers.map(c => [
      `"${(c.name || '').replace(/"/g, '""')}"`,
      `"${c.phone || ''}"`,
      `"${c.date_of_birth || ''}"`,
      `"${c.anniversary_date || ''}"`,
      `"${c.gender || ''}"`,
      `"${(c.category_preference || '').replace(/"/g, '""')}"`,
      c.loyalty_points || 0,
      c.total_spent || 0,
      c.total_visits || 0,
      `"${((c.tags || []).join(', ')).replace(/"/g, '""')}"`,
      `"${(c.notes || '').replace(/"/g, '""')}"`
    ]);
    const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const shopSlug = (this.currentShop ? this.currentShop.slug : "shop") || "shop";
    link.setAttribute("href", url);
    link.setAttribute("download", `${shopSlug}_customers_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    this.showToast(`Exported ${this.allCustomers.length} customers to CSV!`, "success");
  },

  // ======================== CLOUD / GOOGLE DRIVE SYNC ========================
  openCloudSyncModal() {
    const s = this.currentShop;
    const input = document.getElementById("cloudSyncInputUrl");
    if (input && s && s.cloud_sheet_url) {
      input.value = s.cloud_sheet_url;
    }
    document.getElementById("cloudSyncModal").classList.add("open");
  },

  closeCloudSyncModal() {
    document.getElementById("cloudSyncModal").classList.remove("open");
  },

  async submitCloudSync() {
    const url = document.getElementById("cloudSyncInputUrl").value.trim();
    if (!url) {
      this.showToast("Please paste a Google Sheets or Drive share link", "warning");
      return;
    }
    this.showToast("Connecting to Cloud & fetching customer rows...", "info");
    try {
      const res = await API.syncCloudSheet(url);
      this.showToast(`Cloud Sync successful! Synced ${res.imported_count} customers.`, "success");
      this.closeCloudSyncModal();
      await this.loadCustomers();
      await this.loadDashboardData();
    } catch (err) {
      this.showToast("Cloud sync failed: " + err.message, "danger");
    }
  },

  // ======================== BILLING ========================
  async loadBillingCustomers() {
    const data = await API.getCustomers();
    this.allCustomers = data.customers;
    const select = document.getElementById("billCustomerSelect");
    select.innerHTML = '<option value="">— Choose Customer —</option>';
    data.customers.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.phone}) — ${c.loyalty_points || 0} pts`;
      select.appendChild(opt);
    });
    this.calculateBillSummary();
  },

  handleBillingCustomerChange(custId) {
    if (!custId) { this.selectedCustomerForBilling = null; document.getElementById("selectedCustomerInfo").style.display = "none"; this.calculateBillSummary(); return; }
    const c = this.allCustomers.find(x => x.id == custId);
    this.selectedCustomerForBilling = c;
    if (c) {
      document.getElementById("selectedCustomerInfo").style.display = "flex";
      document.getElementById("billCustNamePhone").textContent = `${c.name} (+${c.phone})`;
      document.getElementById("billCustPointsBadge").textContent = `${c.loyalty_points || 0} Points`;
      document.getElementById("billCustPref").textContent = `${c.category_preference || 'Silk Sarees'} · ${c.total_visits || 0} visits`;
      document.getElementById("billRedeemPoints").max = c.loyalty_points || 0;
    }
    this.calculateBillSummary();
  },

  calculateBillSummary() {
    const gross = parseFloat(document.getElementById("billGrossAmount").value) || 0;
    const discount = parseFloat(document.getElementById("billDiscountAmount").value) || 0;
    let redeemPts = parseInt(document.getElementById("billRedeemPoints").value) || 0;
    const maxPts = this.selectedCustomerForBilling ? (this.selectedCustomerForBilling.loyalty_points || 0) : 0;
    if (redeemPts > maxPts) { redeemPts = maxPts; document.getElementById("billRedeemPoints").value = redeemPts; }
    const redeemVal = redeemPts * (this.currentShop ? (this.currentShop.point_redeem_value_inr || 1) : 1);
    const totalDeductions = discount + redeemVal;
    const net = Math.max(0, gross - totalDeductions);
    const ptsRate = this.currentShop ? (this.currentShop.points_per_100_spent || 5) : 5;
    const pointsEarned = Math.floor((net / 100) * ptsRate);

    document.getElementById("summaryGross").textContent = `₹${gross.toFixed(2)}`;
    document.getElementById("summaryDeductions").textContent = `-₹${totalDeductions.toFixed(2)}`;
    document.getElementById("summaryNet").textContent = `₹${net.toFixed(2)}`;
    document.getElementById("summaryPointsEarned").textContent = `+${pointsEarned} pts`;

    const custName = this.selectedCustomerForBilling ? this.selectedCustomerForBilling.name : "Customer";
    const shopName = this.currentShop ? (this.currentShop.sender_display_name || this.currentShop.name) : "Textile Store";
    const invNo = document.getElementById("billInvoiceNo").value || "INV-AUTO";
    const items = document.getElementById("billItemsSummary").value || "Bridal Silks";
    const totalBal = (this.selectedCustomerForBilling ? this.selectedCustomerForBilling.loyalty_points : 0) - redeemPts + pointsEarned;

    document.getElementById("receiptPreviewBubble").innerHTML = `
Namaste *${custName}*! 🛍️✨

Thank you for shopping at *${shopName}*!

━━━━━━━━━━━━━━━━
🧾 *DIGITAL RECEIPT*
📌 Invoice: ${invNo}
👗 Items: ${items}
💵 Net Paid: ₹${net.toFixed(2)}
━━━━━━━━━━━━━━━━
⭐ Points Earned: +${pointsEarned} pts
${redeemPts > 0 ? `🎟️ Redeemed: -${redeemPts} pts (-₹${redeemVal})\n` : ''}🎁 Balance: *${totalBal} Points*
💡 (1 Point = ₹1 on next visit)

We look forward to seeing you again!
📍 *${shopName}*
      <div class="timestamp">Just now <i class="fa-solid fa-check-double" style="color:#53bdeb;"></i></div>
    `;
  },

  async handleBillingSubmit(e) {
    e.preventDefault();
    const custId = document.getElementById("billCustomerSelect").value;
    const gross = parseFloat(document.getElementById("billGrossAmount").value);
    if (!custId || !gross) { this.showToast("Select customer & enter amount", "warning"); return; }
    try {
      const res = await API.recordPurchase({
        customer_id: custId,
        bill_amount: gross,
        discount_amount: parseFloat(document.getElementById("billDiscountAmount").value) || 0,
        points_to_redeem: parseInt(document.getElementById("billRedeemPoints").value) || 0,
        invoice_no: document.getElementById("billInvoiceNo").value.trim(),
        items_summary: document.getElementById("billItemsSummary").value.trim()
      });
      this.showToast(`Sale recorded! Invoice: ${res.invoice_no}. WhatsApp: ${res.whatsapp_status}`, "success");
      document.getElementById("billingForm").reset();
      this.handleBillingCustomerChange("");
      this.loadBillingCustomers();
    } catch (err) { this.showToast("Billing error: " + err.message, "danger"); }
  },

  openNewPurchaseModal() { this.switchTab("tab-billing"); },

  // ======================== BIRTHDAYS ========================
  async loadBirthdays() {
    const data = await API.getBirthdays();
    const todayTbody = document.getElementById("bdayTodayTableBody");
    const upcomingTbody = document.getElementById("bdayUpcomingTableBody");
    todayTbody.innerHTML = "";
    upcomingTbody.innerHTML = "";
    document.getElementById("bdayTodayCount").textContent = data.today.length;

    if (data.today.length === 0) {
      todayTbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><i class="fa-solid fa-cake-candles"></i><p>No birthdays today (${data.date})</p></div></td></tr>`;
    } else {
      data.today.forEach(c => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${c.name}</strong></td>
          <td><a href="https://wa.me/${c.phone}" target="_blank" style="color:var(--wa-teal);"><i class="fa-brands fa-whatsapp"></i> +${c.phone}</a></td>
          <td>🎂 ${c.date_of_birth}</td>
          <td>${c.category_preference || 'Silk'}</td>
          <td><strong style="color:var(--accent-600);">${c.loyalty_points || 0}</strong></td>
          <td>${c.wish_sent_this_year ? '<span class="status-badge status-sent"><i class="fa-solid fa-check"></i> Sent</span>' : '<span class="status-badge status-simulated">Pending</span>'}</td>
          <td><button class="btn btn-whatsapp btn-xs" onclick="App.triggerBirthdayWishes()"><i class="fa-solid fa-paper-plane"></i> Send</button></td>
        `;
        todayTbody.appendChild(tr);
      });
    }

    if (data.upcoming.length === 0) {
      upcomingTbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-calendar"></i><p>No upcoming birthdays in 7 days</p></div></td></tr>';
    } else {
      data.upcoming.forEach(c => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${c.name}</strong></td>
          <td>+${c.phone}</td>
          <td>🎂 ${c.date_of_birth}</td>
          <td><span class="tag tag-vip">In ${c.days_until} days</span></td>
          <td>${c.category_preference || 'Silk'}</td>
          <td>${c.loyalty_points || 0} pts</td>
        `;
        upcomingTbody.appendChild(tr);
      });
    }
  },

  async triggerBirthdayWishes() {
    try {
      const res = await API.sendBirthdayWishes();
      this.showToast(`Birthday wishes sent: ${res.result.total_sent} messages!`, "success");
      this.loadBirthdays();
    } catch (err) { this.showToast("Failed: " + err.message, "danger"); }
  },

  // ======================== CAMPAIGNS ========================
  populateTemplateOptions() {
    const select = document.getElementById("campTemplateSelect");
    if (!select) return;
    TEXTILE_TEMPLATES.forEach(tpl => {
      const opt = document.createElement("option");
      opt.value = tpl.id;
      opt.textContent = tpl.name;
      select.appendChild(opt);
    });
  },

  handleTemplateSelect(tplId) {
    if (!tplId) return;
    const tpl = TEXTILE_TEMPLATES.find(t => t.id === tplId);
    if (!tpl) return;
    document.getElementById("campTitle").value = tpl.name;
    document.getElementById("campType").value = tpl.type;
    document.getElementById("campMediaUrl").value = tpl.mediaUrl || "";
    document.getElementById("campBody").value = tpl.body;
    this.updateCampaignPreview();
  },

  updateCampaignPreview() {
    const rawBody = document.getElementById("campBody").value;
    const mediaUrl = document.getElementById("campMediaUrl").value.trim();
    const previewImg = document.getElementById("campPreviewImg");
    const previewText = document.getElementById("campPreviewText");
    if (mediaUrl) { previewImg.src = mediaUrl; previewImg.style.display = "block"; }
    else { previewImg.style.display = "none"; }
    const shopName = this.currentShop ? (this.currentShop.sender_display_name || this.currentShop.name) : "EasyToReach";
    const city = this.currentShop ? (this.currentShop.city || "Showroom") : "Showroom";
    previewText.textContent = rawBody.replace(/{{customer_name}}/g, "Meenakshi").replace(/{{shop_name}}/g, shopName).replace(/{{points}}/g, "450").replace(/{{city}}/g, city) || "Type message to preview...";
  },

  async handleCampaignSubmit(e) {
    e.preventDefault();
    try {
      const res = await API.broadcastCampaign({
        title: document.getElementById("campTitle").value.trim(),
        type: document.getElementById("campType").value,
        target_filter: document.getElementById("campAudience") ? document.getElementById("campAudience").value : "ALL",
        gender_filter: document.getElementById("campGender") ? document.getElementById("campGender").value : "ALL",
        age_filter: document.getElementById("campAge") ? document.getElementById("campAge").value : "ALL",
        points_filter: document.getElementById("campPoints") ? document.getElementById("campPoints").value : "ALL",
        media_url: document.getElementById("campMediaUrl").value.trim(),
        message_body: document.getElementById("campBody").value.trim()
      });
      this.showToast(`Broadcast sent to ${res.sent_count} customers!`, "success");
      document.getElementById("campaignForm").reset();
      this.updateCampaignPreview();
      this.updateCampaignAudienceEstimate();
      this.loadCampaignsHistory();
    } catch (err) { this.showToast("Campaign error: " + err.message, "danger"); }
  },

  updateCampaignAudienceEstimate() {
    const audEl = document.getElementById("campAudience");
    const genEl = document.getElementById("campGender");
    const ageEl = document.getElementById("campAge");
    const ptsEl = document.getElementById("campPoints");
    const countEl = document.getElementById("campAudienceCount");
    if (!countEl) return;

    if (!this.allCustomers || this.allCustomers.length === 0) {
      countEl.textContent = "Loading customers...";
      return;
    }

    const target = audEl ? audEl.value : "ALL";
    const gender = genEl ? genEl.value : "ALL";
    const ageGroup = ageEl ? ageEl.value : "ALL";
    const pointsGroup = ptsEl ? ptsEl.value : "ALL";

    const now = new Date();
    const matches = this.allCustomers.filter(c => {
      // 1. Target Audience Tags (VIP, First Time Buyer, Regular, Frequent Buyer, Wedding)
      if (target !== "ALL") {
        const tags = Array.isArray(c.tags) ? c.tags.join(" ").toLowerCase() : (c.tags || "").toString().toLowerCase();
        if (target === "VIP" && !tags.includes("vip")) return false;
        if (target === "FIRST_TIME" && !tags.includes("first time") && (c.total_visits || 0) > 1) return false;
        if (target === "REGULAR" && !tags.includes("regular")) return false;
        if (target === "FREQUENT" && !tags.includes("frequent")) return false;
        if (target === "WEDDING" && !tags.includes("wedding") && !tags.includes("bridal")) return false;
      }

      // 2. Gender Filter
      if (gender !== "ALL") {
        const cGender = (c.gender || "").toLowerCase();
        if (gender === "Female" && cGender !== "female") return false;
        if (gender === "Male" && cGender !== "male") return false;
        if (gender === "Other" && (cGender === "female" || cGender === "male")) return false;
      }

      // 3. Loyalty Points Filter
      const pts = Number(c.loyalty_points || 0);
      if (pointsGroup === "ABOVE_0" && pts <= 0) return false;
      if (pointsGroup === "ABOVE_50" && pts < 50) return false;
      if (pointsGroup === "ABOVE_100" && pts < 100) return false;
      if (pointsGroup === "ABOVE_500" && pts < 500) return false;
      if (pointsGroup === "ZERO" && pts > 0) return false;

      // 4. Age Group Filter (<5, 5-18, 18-30, 30-50, 50+)
      if (ageGroup !== "ALL") {
        const dob = c.date_of_birth;
        if (!dob || dob.length < 4) return false;
        const parts = dob.split("-");
        const bYear = parseInt(parts[0], 10);
        if (isNaN(bYear)) return false;
        const bMonth = parts[1] ? parseInt(parts[1], 10) - 1 : 0;
        const bDay = parts[2] ? parseInt(parts[2], 10) : 1;
        let age = now.getFullYear() - bYear;
        if (now.getMonth() < bMonth || (now.getMonth() === bMonth && now.getDate() < bDay)) {
          age--;
        }

        if (ageGroup === "UNDER_5" && age >= 5) return false;
        if (ageGroup === "5_TO_18" && (age < 5 || age > 18)) return false;
        if (ageGroup === "18_TO_30" && (age < 18 || age > 30)) return false;
        if (ageGroup === "30_TO_50" && (age < 30 || age > 50)) return false;
        if (ageGroup === "50_PLUS" && age < 50) return false;
      }

      return true;
    });

    countEl.textContent = `${matches.length} customer${matches.length === 1 ? '' : 's'}`;
  },

  async loadCampaignsHistory() {
    const data = await API.getCampaigns();
    const tbody = document.getElementById("campaignsHistoryTableBody");
    tbody.innerHTML = "";
    if (data.campaigns.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-bullhorn"></i><p>No campaigns yet</p></div></td></tr>';
      return;
    }
    data.campaigns.forEach(c => {
      const tr = document.createElement("tr");
      const statusCls = c.status === 'SENT' ? 'status-sent' : c.status === 'DRAFT' ? 'status-draft' : 'status-sending';
      tr.innerHTML = `
        <td><strong>${c.title}</strong></td>
        <td><span class="tag tag-silk">${c.type}</span></td>
        <td>${c.target_filter}</td>
        <td><span class="status-badge ${statusCls}">${c.status}</span></td>
        <td><strong>${c.sent_count}</strong> / ${c.total_recipients}</td>
        <td style="font-size:0.8rem; color:var(--slate-500);">${c.created_at}</td>
      `;
      tbody.appendChild(tr);
    });
  },

  // ======================== WHATSAPP LOGS ========================
  async loadWhatsAppLogs() {
    const days = document.getElementById("logsDaysFilter")?.value || 3;
    const data = await API.getWhatsAppLogs(50, days);
    const tbody = document.getElementById("whatsappLogsTableBody");
    tbody.innerHTML = "";
    if (data.logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><i class="fa-brands fa-whatsapp"></i><p>No messages recorded yet</p></div></td></tr>';
      return;
    }
    data.logs.forEach(log => {
      const tr = document.createElement("tr");
      const errorNote = (log.status === "FAILED" && log.error_message) 
        ? `<div style="font-size:0.7rem; color:var(--danger); margin-top:4px;" title="${log.error_message.replace(/"/g, '&quot;')}"><i class="fa-solid fa-triangle-exclamation"></i> ${this.formatMetaError(log.error_message)}</div>`
        : "";
      tr.innerHTML = `
        <td style="font-size:0.78rem; color:var(--slate-400);">${log.sent_at}</td>
        <td><strong>${log.recipient_name || 'Customer'}</strong></td>
        <td>+${log.recipient_phone}</td>
        <td><span class="tag tag-regular">${log.message_type}</span></td>
        <td>
          <span class="status-badge status-${log.status.toLowerCase()}">${log.status}</span>
          ${errorNote}
        </td>
        <td><code style="font-size:0.7rem; color:var(--slate-400);">${log.meta_message_id || '-'}</code></td>
        <td style="max-width:220px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.82rem;" title="${log.message_text}">${log.message_text.replace(/\n/g, ' ')}</td>
      `;
      tbody.appendChild(tr);
    });
  },

  // ======================== DIRECT WHATSAPP ========================
  openDirectWhatsAppModal() { document.getElementById("directWhatsappForm").reset(); document.getElementById("directWhatsappModal").classList.add("open"); },
  openDirectWhatsAppTo(phone, name) { this.openDirectWhatsAppModal(); document.getElementById("directPhone").value = phone; document.getElementById("directName").value = name; },
  closeDirectWhatsAppModal() { document.getElementById("directWhatsappModal").classList.remove("open"); },

  async handleDirectWhatsAppSubmit(e) {
    e.preventDefault();
    try {
      const res = await API.sendDirectWhatsApp(
        document.getElementById("directPhone").value.trim(),
        document.getElementById("directMsg").value.trim(),
        document.getElementById("directName").value.trim(),
        document.getElementById("directMedia").value.trim()
      );
      this.showToast(`WhatsApp sent! Status: ${res.status}`, "success");
      this.closeDirectWhatsAppModal();
      this.loadDashboardData();
    } catch (err) { this.showToast("Failed: " + err.message, "danger"); }
  },

  // ======================== SETTINGS ========================
  async loadShopSettings() {
    await this.fetchActiveShopDetails();
    const s = this.currentShop;
    if (!s) return;
    document.getElementById("setShopName").value = s.name || "";
    document.getElementById("setSenderName").value = s.sender_display_name || s.name || "";
    document.getElementById("setShopPhone").value = s.phone || "";
    document.getElementById("setShopCity").value = s.city || "";
    document.getElementById("setShopAddress").value = s.address || "";
    document.getElementById("setMetaPhoneId").value = s.whatsapp_phone_number_id || "";
    document.getElementById("setMetaWabaId").value = s.whatsapp_business_id || "";
    document.getElementById("setMetaToken").value = s.whatsapp_access_token || "";
    document.getElementById("setPointsRule").value = s.points_per_100_spent || 5;
    document.getElementById("setRedeemVal").value = s.point_redeem_value_inr || 1;
    document.getElementById("setBdayDiscount").value = s.birthday_discount_percent || 15;
    document.getElementById("setBdayDays").value = s.birthday_offer_validity_days || 7;
    document.getElementById("setAutoBdayWishes").checked = s.auto_birthday_wishes_enabled === 1;
    if (document.getElementById("setCloudSheetUrl")) {
      document.getElementById("setCloudSheetUrl").value = s.cloud_sheet_url || "";
    }
    // Load custom interactive auto-replies
    let autoReplies = {};
    if (s.custom_auto_replies_json) {
      try { autoReplies = JSON.parse(s.custom_auto_replies_json); } catch (_) {}
    }
    const plansEl = document.getElementById("setAutoReplyPlans");
    const pointsEl = document.getElementById("setAutoReplyPoints");
    const staffEl = document.getElementById("setAutoReplyStaff");
    const optOutEl = document.getElementById("setAutoReplyOptOut");
    if (plansEl) plansEl.value = autoReplies.plans || "";
    if (pointsEl) pointsEl.value = autoReplies.points || "";
    if (staffEl) staffEl.value = autoReplies.staff || "";
    if (optOutEl) optOutEl.value = autoReplies.opt_out || "";

    // Miss You settings
    const missYouEnabled = document.getElementById("setMissYouEnabled");
    if (missYouEnabled) missYouEnabled.checked = s.miss_you_enabled !== 0;
    const missYouDays = document.getElementById("setMissYouDays");
    if (missYouDays) missYouDays.value = s.miss_you_days || 30;
    const missYouTemplate = document.getElementById("setMissYouTemplate");
    if (missYouTemplate) missYouTemplate.value = s.miss_you_template || "";

    // Points reminder settings
    const ptsReminderEnabled = document.getElementById("setPointsReminderEnabled");
    if (ptsReminderEnabled) ptsReminderEnabled.checked = s.points_reminder_enabled !== 0;
    const ptsReminderDays = document.getElementById("setPointsReminderDays");
    if (ptsReminderDays) ptsReminderDays.value = s.points_reminder_days || 60;
    const ptsReminderMin = document.getElementById("setPointsReminderMinPoints");
    if (ptsReminderMin) ptsReminderMin.value = s.points_reminder_min_points || 50;
    const ptsReminderTemplate = document.getElementById("setPointsReminderTemplate");
    if (ptsReminderTemplate) ptsReminderTemplate.value = s.points_reminder_template || "";
  },

  async handleShopSettingsSubmit(e) {
    e.preventDefault();
    try {
      const autoReplies = {
        plans: document.getElementById("setAutoReplyPlans")?.value.trim() || "",
        points: document.getElementById("setAutoReplyPoints")?.value.trim() || "",
        staff: document.getElementById("setAutoReplyStaff")?.value.trim() || "",
        opt_out: document.getElementById("setAutoReplyOptOut")?.value.trim() || ""
      };

      await API.updateShop(API.getActiveShop(), {
        name: document.getElementById("setShopName").value.trim(),
        sender_display_name: document.getElementById("setSenderName").value.trim(),
        phone: document.getElementById("setShopPhone").value.trim(),
        city: document.getElementById("setShopCity").value.trim(),
        address: document.getElementById("setShopAddress").value.trim(),
        whatsapp_phone_number_id: document.getElementById("setMetaPhoneId").value.trim(),
        whatsapp_business_id: document.getElementById("setMetaWabaId").value.trim(),
        whatsapp_access_token: document.getElementById("setMetaToken").value.trim(),
        points_per_100_spent: parseFloat(document.getElementById("setPointsRule").value),
        point_redeem_value_inr: parseFloat(document.getElementById("setRedeemVal").value),
        birthday_discount_percent: parseInt(document.getElementById("setBdayDiscount").value),
        birthday_offer_validity_days: parseInt(document.getElementById("setBdayDays").value),
        auto_birthday_wishes_enabled: document.getElementById("setAutoBdayWishes").checked ? 1 : 0,
        cloud_sheet_url: document.getElementById("setCloudSheetUrl") ? document.getElementById("setCloudSheetUrl").value.trim() : "",
        custom_auto_replies_json: JSON.stringify(autoReplies),
        miss_you_enabled: document.getElementById("setMissYouEnabled")?.checked ? 1 : 0,
        miss_you_days: parseInt(document.getElementById("setMissYouDays")?.value || "30"),
        miss_you_template: document.getElementById("setMissYouTemplate")?.value.trim() || "",
        points_reminder_enabled: document.getElementById("setPointsReminderEnabled")?.checked ? 1 : 0,
        points_reminder_days: parseInt(document.getElementById("setPointsReminderDays")?.value || "60"),
        points_reminder_min_points: parseInt(document.getElementById("setPointsReminderMinPoints")?.value || "50"),
        points_reminder_template: document.getElementById("setPointsReminderTemplate")?.value.trim() || ""
      });
      this.showToast("Settings saved!", "success");
      await this.loadShops();
    } catch (err) { this.showToast("Save failed: " + err.message, "danger"); }
  },

  // ======================== NEW SHOP ========================
  openNewShopModal() {
    document.getElementById("newShopForm").reset();
    const today = new Date().toISOString().split("T")[0];
    const nextYear = new Date(Date.now() + 365*86400000).toISOString().split("T")[0];
    const startEl = document.getElementById("newShopSubStart");
    const endEl = document.getElementById("newShopSubEnd");
    if (startEl) startEl.value = today;
    if (endEl) endEl.value = nextYear;
    document.getElementById("newShopModal").classList.add("open");
  },
  closeNewShopModal() { document.getElementById("newShopModal").classList.remove("open"); },

  async handleNewShopSubmit(e) {
    e.preventDefault();
    const name = document.getElementById("newShopName").value.trim();
    try {
      const res = await API.createShop({
        name,
        tagline: document.getElementById("newShopTagline").value.trim(),
        city: document.getElementById("newShopCity").value.trim(),
        phone: document.getElementById("newShopPhone").value.trim(),
        address: document.getElementById("newShopAddress").value.trim(),
        sender_display_name: name,
        subscription_plan: document.getElementById("newShopPlan")?.value || "Standard Annual",
        subscription_start: document.getElementById("newShopSubStart")?.value || "",
        subscription_end: document.getElementById("newShopSubEnd")?.value || ""
      });
      this.showToast(`Shop "${name}" created!`, "success");
      this.closeNewShopModal();
      await this.loadShops();
      API.setActiveShop(res.shop_id);
      document.getElementById("shopSelect").value = res.shop_id;
      this.switchTab("tab-admin-overview");
      await this.loadAdminOverview();
    } catch (err) { this.showToast("Failed: " + err.message, "danger"); }
  },

  // ======================== ADMIN OVERVIEW ========================
  async loadAdminOverview() {
    try {
      const data = await API.request("/api/admin/summary");
      if (!data || !data.shops) return;

      // Totals (No total customers / total revenue; replaced with amount to Meta at ₹1/msg)
      const t = data.totals || {};
      const elShops = document.getElementById("aov-shops");
      const elMsgs = document.getElementById("aov-messages");
      const elMeta = document.getElementById("aov-meta-bill");
      const elSubs = document.getElementById("aov-active-subs");

      if (elShops) elShops.textContent = t.total_shops ?? "—";
      if (elMsgs) elMsgs.textContent = (t.total_messages || 0).toLocaleString("en-IN");
      if (elMeta) elMeta.textContent = "₹" + Number(t.total_meta_amount || (t.total_messages || 0)).toLocaleString("en-IN");
      if (elSubs) elSubs.textContent = `${t.active_subscriptions || 0} Active`;

      // Table
      const tbody = document.getElementById("adminOverviewTableBody");
      if (!tbody) return;
      tbody.innerHTML = data.shops.map(s => {
        const isSuspended = s.status === 'SUSPENDED' || s.is_expired;
        const statusBadge = isSuspended
          ? '<span class="badge" style="background:#fee2e2;color:#b91c1c;font-weight:600;"><i class="fa-solid fa-ban"></i> Suspended</span>'
          : '<span class="badge" style="background:#dcfce7;color:#15803d;font-weight:600;"><i class="fa-solid fa-circle-check"></i> Active</span>';
        
        return `
        <tr>
          <td><strong>${s.name}</strong></td>
          <td>${s.city || "—"}</td>
          <td><strong>${s.messages_sent}</strong></td>
          <td><strong style="color:var(--accent-600);">₹${Number(s.meta_amount).toLocaleString("en-IN")}</strong></td>
          <td><span class="badge" style="background:var(--accent-100);color:var(--accent-700);">${s.subscription_plan || "Standard"}</span></td>
          <td><span style="font-size:0.85rem;color:var(--text-muted);">${s.subscription_start || "—"}</span></td>
          <td><span style="font-size:0.85rem;font-weight:600;${isSuspended ? 'color:#b91c1c;' : ''}">${s.subscription_end || "—"}</span></td>
          <td>${statusBadge}</td>
          <td>
            <div style="display:flex;gap:6px;">
              <button class="btn btn-secondary btn-sm" onclick="App.handleShopChange(${s.id})" title="Open this store's individual dashboard"><i class="fa-solid fa-arrow-right-to-bracket"></i> View</button>
              <button class="btn btn-secondary btn-sm" onclick="App.openSubscriptionModal(${s.id}, '${s.name.replace(/'/g, "\\'")}', '${s.subscription_plan || 'Standard Annual'}', '${s.subscription_start || ''}', '${s.subscription_end || ''}', '${s.status || 'ACTIVE'}')" title="Manage Subscription & Expiry"><i class="fa-solid fa-file-pen"></i> Plan</button>
            </div>
          </td>
        </tr>`;
      }).join("");
    } catch (err) {
      this.showToast("Failed to load admin overview: " + err.message, "danger");
    }
  },

  openSubscriptionModal(shopId, name, plan, start, end, status) {
    document.getElementById("subShopId").value = shopId;
    document.getElementById("subShopName").value = name;
    document.getElementById("subPlan").value = plan || "Standard Annual";
    document.getElementById("subStartDate").value = start || "";
    document.getElementById("subEndDate").value = end || "";
    document.getElementById("subStatus").value = status || "ACTIVE";
    document.getElementById("subscriptionModal").classList.add("open");
  },

  closeSubscriptionModal() {
    document.getElementById("subscriptionModal").classList.remove("open");
  },

  async handleSubscriptionSubmit(e) {
    e.preventDefault();
    const shopId = document.getElementById("subShopId").value;
    const plan = document.getElementById("subPlan").value;
    const start = document.getElementById("subStartDate").value;
    const end = document.getElementById("subEndDate").value;
    const status = document.getElementById("subStatus").value;

    try {
      const res = await API.updateShopSubscription({
        shop_id: shopId,
        subscription_plan: plan,
        subscription_start: start,
        subscription_end: end,
        status: status
      });
      if (res.success) {
        this.showToast("Subscription updated successfully!", "success");
        this.closeSubscriptionModal();
        await this.loadAdminOverview();
        if (document.getElementById("tab-accounts")?.classList.contains("active")) {
          await this.loadStoreAccountsPage();
        }
      } else {
        this.showToast(res.error || "Failed to update subscription", "danger");
      }
    } catch (err) {
      this.showToast(err.message, "danger");
    }
  },

  // ======================== CONTACT ADMIN MODAL ========================
  openContactAdminModal() {
    const modal = document.getElementById("contactAdminModal");
    if (modal) modal.classList.add("open");
  },

  closeContactAdminModal() {
    const modal = document.getElementById("contactAdminModal");
    if (modal) modal.classList.remove("open");
  },

  // ======================== STORE ACCOUNTS MANAGEMENT (FULL PAGE) ========================
  storeAccountsData: [],
  storeShopsData: [],

  async loadStoreAccountsPage() {
    try {
      const [usersRes, shopsRes] = await Promise.all([
        API.getAdminUsers(),
        API.getShops()
      ]);

      this.storeAccountsData = usersRes.users || [];
      this.storeShopsData = shopsRes.shops || [];

      // Update counters
      const totalUsers = this.storeAccountsData.length;
      const activeUsers = this.storeAccountsData.filter(u => (u.status || "ACTIVE") === "ACTIVE").length;
      const suspendedUsers = this.storeAccountsData.filter(u => u.status === "SUSPENDED").length;
      const totalShops = this.storeShopsData.length;

      const elTot = document.getElementById("accTotalUsers");
      const elAct = document.getElementById("accActiveUsers");
      const elSus = document.getElementById("accSuspendedUsers");
      const elShp = document.getElementById("accTotalShops");
      if (elTot) elTot.textContent = totalUsers;
      if (elAct) elAct.textContent = activeUsers;
      if (elSus) elSus.textContent = suspendedUsers;
      if (elShp) elShp.textContent = totalShops;

      this.filterStoreAccounts();
      this.renderStoreShopsDirectory(this.storeShopsData);
    } catch (err) {
      this.showToast("Failed to load store accounts: " + err.message, "danger");
    }
  },

  filterStoreAccounts() {
    const q = (document.getElementById("accountSearchInput")?.value || "").toLowerCase().trim();
    const roleFilter = document.getElementById("accountRoleFilter")?.value || "";
    const statusFilter = document.getElementById("accountStatusFilter")?.value || "";

    const filtered = (this.storeAccountsData || []).filter(u => {
      if (roleFilter && u.role !== roleFilter) return false;
      if (statusFilter && (u.status || "ACTIVE") !== statusFilter) return false;
      if (q) {
        const text = `${u.username} ${u.full_name || ""} ${u.email || ""} ${u.phone || ""} ${u.shop_name || ""}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });

    this.renderStoreAccountsTable(filtered);
  },

  renderStoreAccountsTable(users) {
    const tbody = document.getElementById("storeAccountsTableBody");
    if (!tbody) return;

    if (!users || users.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-muted);"><i class="fa-solid fa-users-slash" style="font-size:1.5rem; margin-bottom:8px; display:block;"></i>No accounts match criteria.</td></tr>`;
      return;
    }

    const currentUserId = this.currentUser ? this.currentUser.id : null;

    tbody.innerHTML = users.map(u => {
      const isSelf = currentUserId === u.id;
      const isSuspended = u.status === "SUSPENDED";

      const statusBadge = isSuspended
        ? `<span class="badge" style="background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3); font-weight:700;"><i class="fa-solid fa-circle-pause" style="font-size:0.55rem; vertical-align:middle; margin-right:4px;"></i> Suspended</span>`
        : `<span class="badge" style="background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-weight:700;"><i class="fa-solid fa-circle" style="font-size:0.5rem; vertical-align:middle; margin-right:4px;"></i> Active</span>`;

      const roleBadge = u.role === "admin"
        ? `<span class="user-role-badge" style="font-size:0.75rem; padding:3px 10px;"><i class="fa-solid fa-crown" style="color:var(--gold);"></i> Admin</span>`
        : `<span class="user-role-badge owner" style="font-size:0.75rem; padding:3px 10px;"><i class="fa-solid fa-store" style="color:#10b981;"></i> Shop Owner</span>`;

      const shopDisplay = u.role === "admin"
        ? `<span style="color:var(--text-muted); font-size:0.85rem;"><i class="fa-solid fa-globe"></i> All Shops (Platform)</span>`
        : `<strong>${u.shop_name || ("Shop #" + u.shop_id)}</strong><br><small style="color:var(--text-muted);">${u.shop_city || ""}</small>`;

      let actionButtons = "";
      if (isSelf) {
        actionButtons = `<span style="font-size:0.75rem; color:var(--text-muted); font-weight:600;"><i class="fa-solid fa-user-check"></i> Current User</span>`;
      } else {
        const toggleBtn = isSuspended
          ? `<button class="btn btn-success btn-xs" onclick="App.toggleAccountStatus(${u.id}, 'ACTIVE')" title="Reactivate this user account"><i class="fa-solid fa-play"></i> Activate</button>`
          : `<button class="btn btn-warning btn-xs" onclick="App.toggleAccountStatus(${u.id}, 'SUSPENDED')" title="Temporarily suspend access"><i class="fa-solid fa-pause"></i> Suspend</button>`;

        const deleteBtn = `<button class="btn btn-danger btn-xs" onclick="App.deleteAccount(${u.id}, '${u.username}')" title="Permanently delete account"><i class="fa-solid fa-trash"></i> Delete</button>`;

        actionButtons = `<div style="display:flex; gap:6px;">${toggleBtn} ${deleteBtn}</div>`;
      }

      return `
        <tr>
          <td>
            <div style="display:flex; align-items:center; gap:10px;">
              <div class="user-avatar-icon ${u.role === 'admin' ? '' : 'shop-owner'}" style="width:34px; height:34px; font-size:0.85rem;">
                <i class="fa-solid ${u.role === 'admin' ? 'fa-crown' : 'fa-store'}"></i>
              </div>
              <div>
                <strong>${u.full_name || u.username}</strong>
                <div style="font-size:0.75rem; color:var(--text-muted); font-family:monospace;">@${u.username}</div>
              </div>
            </div>
          </td>
          <td>${roleBadge}</td>
          <td>${shopDisplay}</td>
          <td style="font-size:0.82rem;">
            <div><i class="fa-solid fa-envelope" style="font-size:0.7rem; color:var(--text-muted); width:14px;"></i> ${u.email}</div>
            ${u.phone ? `<div><i class="fa-solid fa-phone" style="font-size:0.7rem; color:var(--text-muted); width:14px;"></i> ${u.phone}</div>` : ""}
          </td>
          <td>${statusBadge}</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${(u.created_at || "").slice(0, 10)}</td>
          <td>${actionButtons}</td>
        </tr>
      `;
    }).join("");
  },

  renderStoreShopsDirectory(shops) {
    const tbody = document.getElementById("storeShopsDirectoryBody");
    if (!tbody) return;

    if (!shops || shops.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--text-muted);">No registered shops found.</td></tr>`;
      return;
    }

    tbody.innerHTML = shops.map(s => {
      const isLive = Boolean(s.whatsapp_phone_number_id && s.whatsapp_access_token);
      return `
        <tr>
          <td>
            <strong>${s.name}</strong>
            <div style="font-size:0.75rem; color:var(--text-muted); font-family:monospace;">slug: ${s.slug}</div>
          </td>
          <td>
            <div>${s.city || "—"}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">${s.address || ""}</div>
          </td>
          <td>${s.phone || "—"}</td>
          <td>
            ${isLive 
              ? '<span class="status-badge status-sent" style="font-size:0.72rem;"><i class="fa-solid fa-circle-check"></i> Live API</span>' 
              : '<span class="status-badge status-simulated" style="font-size:0.72rem;"><i class="fa-solid fa-circle-xmark"></i> Simulated</span>'
            }
          </td>
          <td>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-secondary btn-xs" onclick="App.handleShopChange(${s.id})" title="Switch active shop to this showroom"><i class="fa-solid fa-arrow-right-to-bracket"></i> View</button>
              <button class="btn btn-danger btn-xs" onclick="App.deleteShop(${s.id}, '${s.name}')" title="Permanently delete shop and records"><i class="fa-solid fa-trash"></i> Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  },

  async openCreateAccountModal() {
    const modal = document.getElementById("createAccountModal");
    if (!modal) return;
    modal.classList.add("open");

    const shopSelect = document.getElementById("newOwnerShopId");
    if (shopSelect) {
      shopSelect.innerHTML = "";
      try {
        const data = await API.getShops();
        if (data.shops) {
          data.shops.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = `${s.name} (${s.city || 'Store'})`;
            shopSelect.appendChild(opt);
          });
        }
      } catch (_) {}
    }
  },

  closeCreateAccountModal() {
    const modal = document.getElementById("createAccountModal");
    if (modal) modal.classList.remove("open");
  },

  async handleCreateShopOwner(e) {
    e.preventDefault();
    const shop_id = document.getElementById("newOwnerShopId").value;
    const full_name = document.getElementById("newOwnerFullName").value.trim();
    const username = document.getElementById("newOwnerUsername").value.trim();
    const email = document.getElementById("newOwnerEmail").value.trim();
    const phone = document.getElementById("newOwnerPhone").value.trim();
    const password = document.getElementById("newOwnerPassword").value.trim();

    try {
      const res = await API.createAdminUser({
        shop_id, full_name, username, email, phone, password, role: "shop_owner"
      });
      if (res.success) {
        this.showToast(`Account created for ${full_name}!`, "success");
        document.getElementById("createShopOwnerForm").reset();
        this.closeCreateAccountModal();
        await this.loadStoreAccountsPage();
      } else {
        this.showToast(res.error || "Failed to create account", "danger");
      }
    } catch (err) {
      this.showToast(err.message, "danger");
    }
  },

  async toggleAccountStatus(userId, newStatus) {
    try {
      const res = await API.toggleAdminUserStatus(userId, newStatus);
      if (res.success) {
        this.showToast(`Account has been ${newStatus === 'ACTIVE' ? 'activated' : 'suspended'}!`, "success");
        await this.loadStoreAccountsPage();
      } else {
        this.showToast(res.error || "Failed to update account status", "danger");
      }
    } catch (err) {
      this.showToast(err.message, "danger");
    }
  },

  async deleteAccount(userId, username) {
    if (!confirm(`Are you sure you want to permanently delete the user account "@${username}"?\n\nThis cannot be undone.`)) {
      return;
    }
    try {
      const res = await API.deleteAdminUser(userId);
      if (res.success) {
        this.showToast(`User @${username} deleted successfully`, "success");
        await this.loadStoreAccountsPage();
      } else {
        this.showToast(res.error || "Failed to delete account", "danger");
      }
    } catch (err) {
      this.showToast(err.message, "danger");
    }
  },

  async deleteShop(shopId, shopName) {
    if (!confirm(`WARNING: Are you sure you want to delete "${shopName}"?\n\nThis will permanently delete this showroom and all its customers, bills, campaigns, and WhatsApp logs.`)) {
      return;
    }
    try {
      const res = await API.deleteShop(shopId);
      if (res.success) {
        this.showToast(`Shop "${shopName}" deleted`, "success");
        await this.loadShops();
        await this.loadStoreAccountsPage();
      } else {
        this.showToast(res.error || "Failed to delete shop", "danger");
      }
    } catch (err) {
      this.showToast(err.message, "danger");
    }
  },

  // ======================== TWO-WAY CONVERSATIONS ========================
  conversationsData: [],
  activeConvPhone: null,
  activeConvCustomerName: null,
  activeConvCustomerId: null,
  composerMode: "text",
  conversationPollTimer: null,
  activeThreadMsgCount: 0,
  manualClosed: false,

  startConversationPolling() {
    this.stopConversationPolling();
    this.conversationPollTimer = setInterval(async () => {
      const convTab = document.getElementById("tab-conversations");
      const isConvTabActive = convTab && convTab.classList.contains("active");

      try {
        // Poll conversations list to catch incoming customer messages
        const convData = await API.getConversations();
        const freshList = convData.conversations || [];

        const oldUnread = this.conversationsData.reduce((a, c) => a + (c.unread_count || 0), 0);
        const newUnread = freshList.reduce((a, c) => a + (c.unread_count || 0), 0);

        // Update nav badge across all tabs
        const badge = document.getElementById("navInboxBadge");
        if (badge) {
          badge.textContent = newUnread;
          badge.style.display = newUnread > 0 ? "inline-flex" : "none";
        }

        // Notification when new message arrives
        if (newUnread > oldUnread) {
          const incomingConv = freshList.find(c => (c.unread_count || 0) > 0);
          if (incomingConv) {
            this.showToast(`💬 New message from ${incomingConv.customer_name}: "${incomingConv.last_message || ''}"`, "success");
          }
        }

        // Check if conversation list content changed
        const oldSig = this.conversationsData.map(c => `${c.recipient_phone}:${c.last_time}:${c.unread_count}`).join("|");
        const newSig = freshList.map(c => `${c.recipient_phone}:${c.last_time}:${c.unread_count}`).join("|");

        if (oldSig !== newSig) {
          this.conversationsData = freshList;
          if (isConvTabActive) {
            this.filterConversations();
          }
        }

        // If conversation tab is open and a thread is active, refresh active thread messages
        if (isConvTabActive && this.activeConvPhone) {
          if (freshList.length === 0) {
            this.closeActiveConversation(false);
            return;
          }
          const data = await API.getConversationMessages(this.activeConvPhone);
          const msgs = data.messages || [];
          if (msgs.length !== this.activeThreadMsgCount) {
            this.activeThreadMsgCount = msgs.length;
            this.renderChatBubbles(msgs);
          }
        }
      } catch (_) {}
    }, 3000);
  },

  stopConversationPolling() {
    if (this.conversationPollTimer) {
      clearInterval(this.conversationPollTimer);
      this.conversationPollTimer = null;
    }
  },

  async loadConversations() {
    const listEl = document.getElementById("conversationsList");
    if (listEl) listEl.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:0.85rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading conversations…</div>';

    try {
      const data = await API.getConversations();
      this.conversationsData = data.conversations || [];
      this.renderConversationsList(this.conversationsData);

      // Update nav inbox badge (ONLY unread incoming customer messages)
      const unreadTotal = this.conversationsData.reduce((a, c) => a + (c.unread_count || 0), 0);
      const badge = document.getElementById("navInboxBadge");
      if (badge) {
        badge.textContent = unreadTotal;
        badge.style.display = unreadTotal > 0 ? "inline-flex" : "none";
      }

      // Auto-open first conversation if none selected and it has messages (unless manually closed)
      // Only auto-open on larger screens (>768px) so mobile users see the conversation list first
      const isMobile = window.innerWidth <= 768;
      if (!isMobile && !this.manualClosed && !this.activeConvPhone && this.conversationsData.length > 0) {
        const first = this.conversationsData[0];
        if ((first.total_messages || 0) > 0) {
          this.openConversation(first.recipient_phone, first.customer_name || "Customer", first.customer_id);
        }
      }
    } catch (err) {
      if (listEl) listEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--danger);font-size:0.82rem;"><i class="fa-solid fa-triangle-exclamation"></i> Error loading: ${err.message}</div>`;
      this.showToast("Failed to load conversations: " + err.message, "danger");
    }
  },

  _normPhone(p) {
    if (!p) return "";
    const clean = String(p).replace(/\D/g, "");
    return clean.length >= 10 ? clean.slice(-10) : clean;
  },

  filterConversations() {
    const q = (document.getElementById("convSearchInput")?.value || "").toLowerCase().trim();
    const filtered = q
      ? this.conversationsData.filter(c => ((c.customer_name || "") + " " + (c.recipient_phone || "")).toLowerCase().includes(q))
      : this.conversationsData;
    this.renderConversationsList(filtered);
  },

  renderConversationsList(conversations) {
    const container = document.getElementById("conversationsList");
    if (!container) return;
    if (!conversations || conversations.length === 0) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:0.85rem;"><i class="fa-solid fa-comment-slash" style="font-size:1.8rem;display:block;margin-bottom:8px;opacity:0.4;"></i>No conversations found.<br>Use <strong>New Chat</strong> to start messaging any customer.</div>';
      return;
    }

    const activeNorm = this._normPhone(this.activeConvPhone);
    container.innerHTML = conversations.map(c => {
      const isActive = Boolean(activeNorm && (this._normPhone(c.recipient_phone) === activeNorm || this._normPhone(c.registered_phone) === activeNorm));
      const timeStr = c.last_time ? c.last_time.slice(5, 16) : "";
      const dirIcon = c.last_direction === "INBOUND" ? "← " : (c.last_direction === "OUTBOUND" ? "→ " : "");
      const name = c.customer_name || "Customer";
      const phone = c.recipient_phone || "";
      const unread = c.unread_count || 0;

      return `<div class="conv-item${isActive ? " active" : ""}" onclick="App.openConversation('${phone.replace(/'/g, "\\'")}','${name.replace(/'/g, "\\'")}',${c.customer_id || "null"})">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:4px;">
          <div class="conv-name" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</div>
          <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
            <span class="conv-time">${timeStr}</span>
            <button class="conv-remove-btn" title="Remove customer from conversation window" onclick="event.stopPropagation(); App.removeConversation('${phone.replace(/'/g, "\\'")}', '${name.replace(/'/g, "\\'")}')">
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:3px;">
          <div class="conv-last-msg">${dirIcon}${c.last_message || "No messages yet — click to chat"}</div>
          ${unread > 0 ? `<span class="conv-badge">${unread}</span>` : ""}
        </div>
        <div style="font-size:0.7rem;color:var(--text-muted);margin-top:2px;">${phone} · ${c.total_messages || 0} msg${(c.total_messages || 0) !== 1 ? "s" : ""}</div>
      </div>`;
    }).join("");
  },

  async openConversation(phone, customerName, customerId) {
    this.manualClosed = false;
    this.activeConvPhone = phone;
    this.activeConvCustomerName = customerName;
    this.activeConvCustomerId = customerId;

    // Toggle mobile chat layout if on mobile
    const convLayout = document.getElementById("convLayout") || document.querySelector(".conv-layout");
    if (convLayout) convLayout.classList.add("mobile-chat-open");

    // Show composer
    const composer = document.getElementById("chatComposer");
    if (composer) composer.style.display = "block";

    // Mark as read locally & immediately clear unread badge
    const activeNorm = this._normPhone(phone);
    const conv = this.conversationsData.find(c => this._normPhone(c.recipient_phone) === activeNorm);
    if (conv && conv.unread_count > 0) {
      conv.unread_count = 0;
      const unreadTotal = this.conversationsData.reduce((a, c) => a + (c.unread_count || 0), 0);
      const badge = document.getElementById("navInboxBadge");
      if (badge) {
        badge.textContent = unreadTotal;
        badge.style.display = unreadTotal > 0 ? "inline-flex" : "none";
      }
    }
    // Update API asynchronously
    API.markConversationRead(phone).catch(() => {});

    // Update header
    const nameEl = document.getElementById("chatCustomerName");
    const phoneEl = document.getElementById("chatCustomerPhone");
    const actionsEl = document.getElementById("chatHeaderActions");
    if (nameEl) nameEl.textContent = customerName;
    if (phoneEl) phoneEl.textContent = phone;
    if (actionsEl) actionsEl.style.display = "flex";

    // Highlight active in list
    this.renderConversationsList(this.conversationsData);

    // Load messages
    const chatMessages = document.getElementById("chatMessages");
    if (chatMessages) chatMessages.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px 0;"><i class="fa-solid fa-spinner fa-spin"></i> Loading thread…</div>';
    try {
      const data = await API.getConversationMessages(phone);
      this.activeThreadMsgCount = (data.messages || []).length;
      this.renderChatBubbles(data.messages || []);
    } catch (err) {
      this.showToast("Failed to load messages: " + err.message, "danger");
    }
  },

  async removeConversation(phone, name) {
    if (!phone) return;
    try {
      const targetNorm = this._normPhone(phone);
      const activeNorm = this._normPhone(this.activeConvPhone);

      // If this conversation was currently active, close it immediately
      if (!this.activeConvPhone || activeNorm === targetNorm) {
        this.closeActiveConversation(false);
      }

      await API.hideConversation(phone);

      // Remove from local list comparing normalized 10-digit phone
      this.conversationsData = (this.conversationsData || []).filter(c => {
        return this._normPhone(c.recipient_phone) !== targetNorm;
      });

      // If active conversation is not in conversationsData anymore, close active conversation
      if (this.activeConvPhone && !this.conversationsData.some(c => this._normPhone(c.recipient_phone) === this._normPhone(this.activeConvPhone))) {
        this.closeActiveConversation(false);
      }

      // If no conversations left, ensure chat panel is closed
      if (this.conversationsData.length === 0) {
        this.closeActiveConversation(false);
      }

      this.filterConversations();

      // Update badge
      const unreadTotal = this.conversationsData.reduce((a, c) => a + (c.unread_count || 0), 0);
      const badge = document.getElementById("navInboxBadge");
      if (badge) {
        badge.textContent = unreadTotal;
        badge.style.display = unreadTotal > 0 ? "inline-flex" : "none";
      }

      this.showToast(`Removed ${name || "customer"} from conversation window. You can re-add anytime via "New Chat".`, "info");
    } catch (err) {
      this.showToast("Failed to remove conversation: " + err.message, "danger");
    }
  },

  closeActiveConversation(reRenderList = true) {
    this.manualClosed = true;
    this.activeConvPhone = null;
    this.activeConvCustomerName = null;
    this.activeConvCustomerId = null;
    this.activeThreadMsgCount = 0;

    // Remove mobile open state to show conversations list
    const convLayout = document.getElementById("convLayout") || document.querySelector(".conv-layout");
    if (convLayout) convLayout.classList.remove("mobile-chat-open");

    const nameEl = document.getElementById("chatCustomerName");
    const phoneEl = document.getElementById("chatCustomerPhone");
    const actionsEl = document.getElementById("chatHeaderActions");
    const chatMessages = document.getElementById("chatMessages");
    const composer = document.getElementById("chatComposer");

    if (nameEl) nameEl.textContent = "Select a conversation";
    if (phoneEl) phoneEl.textContent = "";
    if (actionsEl) actionsEl.style.display = "none";
    if (composer) composer.style.display = "block";
    if (chatMessages) {
      chatMessages.innerHTML = `
        <div style="text-align:center;color:var(--text-muted);margin-top:60px;">
          <i class="fa-solid fa-comments" style="font-size:2.5rem;margin-bottom:12px;display:block;opacity:0.4;"></i>
          Select a customer to start chatting
        </div>`;
    }
    if (reRenderList) {
      this.renderConversationsList(this.conversationsData);
    }
  },

  removeActiveConversation() {
    const phone = this.activeConvPhone || document.getElementById("chatCustomerPhone")?.textContent?.trim();
    const name = this.activeConvCustomerName || document.getElementById("chatCustomerName")?.textContent?.trim();
    this.closeActiveConversation(false);
    if (phone) {
      this.removeConversation(phone, name);
    }
  },

  renderChatBubbles(messages) {
    const container = document.getElementById("chatMessages");
    if (!container) return;
    if (!messages || messages.length === 0) {
      container.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:60px;"><i class="fa-solid fa-comment-dots" style="font-size:2rem;margin-bottom:8px;display:block;opacity:0.4;"></i>No messages yet with this customer.<br>Send a manual message or interactive button offer below!</div>';
      return;
    }

    // Identify which buttons were tapped in this thread
    const tappedButtons = new Set();
    messages.forEach(m => {
      if (m.direction === "INBOUND") {
        if (m.selected_button_id) tappedButtons.add(m.selected_button_id);
        if (m.message_text && m.message_text.startsWith("🔘 Selected:")) {
          tappedButtons.add(m.message_text.replace("🔘 Selected:", "").trim().toLowerCase());
        } else if (m.message_text && m.message_text.startsWith("[Tapped:")) {
          tappedButtons.add(m.message_text.replace("[Tapped:", "").replace("]", "").trim().toLowerCase());
        }
      }
    });

    container.innerHTML = messages.map(msg => {
      const isOutbound = (msg.direction || "OUTBOUND") === "OUTBOUND";
      const bubbleClass = isOutbound ? "outbound" : "inbound";
      const statusColor = msg.status === "DELIVERED" ? "#25d366" : msg.status === "FAILED" ? "#ef4444" : "#94a3b8";
      const statusIcon  = msg.status === "DELIVERED" ? "✓✓" : msg.status === "FAILED" ? "✗" : "◌";
      const timeStr = msg.sent_at ? msg.sent_at.slice(11, 16) : "";

      // If INBOUND message is a button click selection, render with clear prominent badge
      const isChoiceClick = !isOutbound && (
        (msg.message_text && (msg.message_text.startsWith("🔘 Selected:") || msg.message_text.startsWith("[Tapped:"))) ||
        msg.selected_button_id
      );

      if (isChoiceClick) {
        let choiceText = msg.message_text || "";
        if (choiceText.startsWith("🔘 Selected:")) {
          choiceText = choiceText.replace("🔘 Selected:", "").trim();
        } else if (choiceText.startsWith("[Tapped:")) {
          choiceText = choiceText.replace("[Tapped:", "").replace("]", "").trim();
        } else if (msg.selected_button_id) {
          choiceText = msg.selected_button_id;
        }

        return `<div style="display:flex;flex-direction:column;align-items:flex-start;">
          <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;padding-left:4px;">${msg.recipient_name || "Customer"}</div>
          <div class="chat-bubble inbound option-selected-bubble">
            <div class="option-selected-tag"><i class="fa-solid fa-circle-check"></i> Option Clicked by Customer:</div>
            <div class="option-selected-title">${choiceText}</div>
            <div class="bubble-time">${timeStr}</div>
          </div>
        </div>`;
      }

      // Parse quick-reply buttons if any on outbound messages
      let buttonsHtml = "";
      if (msg.buttons_json) {
        try {
          const btns = JSON.parse(msg.buttons_json);
          const tappedId = msg.selected_button_id || "";
          if (btns && btns.length > 0) {
            buttonsHtml = `<div class="chat-buttons-row">${btns.map(b => {
              const id    = typeof b === "object" ? b.id    : `btn_${b}`;
              const title = typeof b === "object" ? b.title : String(b);
              const isSelected = tappedId === id || tappedButtons.has(id) || tappedButtons.has(title.toLowerCase());
              if (isSelected) {
                return `<button class="chat-button-pill selected-by-customer" disabled><i class="fa-solid fa-check"></i> ${title} (Selected)</button>`;
              }
              return `<button class="chat-button-pill"
                onclick="App.handleButtonTap('${id.replace(/'/g,"\\'").replace(/"/g,'&quot;')}','${title.replace(/'/g,"\\'").replace(/"/g,'&quot;')}',this)">${title}</button>`;
            }).join("")}</div>`;
          }
        } catch (_) {}
      }

      return `<div style="display:flex;flex-direction:column;align-items:${isOutbound ? "flex-end" : "flex-start"};">
        ${!isOutbound ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;padding-left:4px;">${msg.recipient_name || "Customer"}</div>` : ""}
        <div class="chat-bubble ${bubbleClass}">
          ${(msg.message_text || "").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\n/g,"<br>")}
          ${buttonsHtml}
          <div class="bubble-time">
            ${timeStr}
            ${isOutbound ? `<span style="color:${statusColor};margin-left:4px;" title="${msg.status}">${statusIcon}</span>` : ""}
          </div>
        </div>
      </div>`;
    }).join("");

    container.scrollTop = container.scrollHeight;
  },

  async handleButtonTap(btnId, btnTitle, btnEl) {
    if (!this.activeConvPhone) return;
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.classList.add("selected-by-customer");
      btnEl.innerHTML = `<i class="fa-solid fa-check"></i> ${btnTitle} (Selected)`;
    }
    try {
      await API.simulateInboundReply({
        recipient_phone: this.activeConvPhone,
        customer_name: this.activeConvCustomerName || "Customer",
        customer_id: this.activeConvCustomerId,
        selected_button_id: btnId,
        selected_button_title: btnTitle,
        message_text: `🔘 Selected: ${btnTitle}`
      });
      await this.openConversation(this.activeConvPhone, this.activeConvCustomerName, this.activeConvCustomerId);
      await this.loadConversations();
    } catch (err) {
      this.showToast("Error: " + err.message, "danger");
    }
  },

  setComposerMode(mode) {
    this.composerMode = "text";
    const textMode = document.getElementById("composerTextMode");
    const interactiveMode = document.getElementById("composerInteractiveMode");
    if (textMode) textMode.style.display = "block";
    if (interactiveMode) interactiveMode.style.display = "none";
  },

  loadFlowIntoComposer(flowId) {
    if (!flowId) return;
    try {
      const flows = (typeof FlowBuilder !== "undefined" && FlowBuilder.flowsList) ? FlowBuilder.flowsList : [];
      const flow = flows.find(f => String(f.id) === String(flowId));
      if (!flow || !flow.flow_data) return;
      const nodes = flow.flow_data.nodes || [];
      const qNode = nodes.find(n => n.type === "buttons" || n.type === "reply_buttons") || nodes[0];
      if (!qNode) return;

      const bodyEl = document.getElementById("interactiveBodyText");
      if (bodyEl) bodyEl.value = qNode.message || qNode.title || "";

      const nodesById = {};
      nodes.forEach(n => { if (n.id) nodesById[n.id] = n; });

      const boxes = document.querySelectorAll(".interactive-btn-box");
      const buttons = qNode.buttons || [];
      boxes.forEach((box, i) => {
        const btn = buttons[i];
        const titleEl = box.querySelector(".interactive-btn-title");
        const idEl = box.querySelector(".interactive-btn-id");
        const replyEl = box.querySelector(".interactive-btn-reply");
        if (btn) {
          box.style.display = "block";
          if (titleEl) titleEl.value = btn.title || "";
          if (idEl) idEl.value = btn.id || `btn_${i+1}`;
          const targetNode = nodesById[btn.target];
          if (replyEl) replyEl.value = targetNode ? (targetNode.message || targetNode.content || "") : "";
        } else if (i > 0) {
          box.style.display = "none";
          if (titleEl) titleEl.value = "";
        }
      });
      this.showToast(`Loaded flow template: ${flow.name}`, "info");
    } catch (err) {
      console.error("Error loading flow into composer:", err);
    }
  },

  async sendManualChat() {
    if (!this.activeConvPhone) { this.showToast("Select a customer from the left list first", "warning"); return; }
    const input = document.getElementById("chatTextInput");
    const text  = (input?.value || "").trim();
    if (!text) return;
    const sendBtn = document.querySelector("#composerTextMode .btn-primary");
    if (sendBtn) sendBtn.disabled = true;
    try {
      await API.sendChatMessage({
        recipient_phone: this.activeConvPhone,
        customer_name:   this.activeConvCustomerName || "Customer",
        customer_id:     this.activeConvCustomerId,
        message_text:    text
      });
      if (input) input.value = "";
      await this.openConversation(this.activeConvPhone, this.activeConvCustomerName, this.activeConvCustomerId);
      await this.loadConversations();
    } catch (err) {
      this.showToast("Send failed: " + err.message, "danger");
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  },

  async sendInteractiveMessage() {
    if (!this.activeConvPhone) { this.showToast("Select a customer from the left list first", "warning"); return; }
    const body   = (document.getElementById("interactiveBodyText")?.value || "").trim();
    const imgUrl = (document.getElementById("interactiveImageUrl")?.value  || "").trim();
    if (!body) { this.showToast("Message body is required", "warning"); return; }

    const boxes = document.querySelectorAll(".interactive-btn-box");
    const buttons = [];
    boxes.forEach((box, i) => {
      const title = box.querySelector(".interactive-btn-title")?.value.trim();
      const id = box.querySelector(".interactive-btn-id")?.value.trim() || `btn_${i + 1}`;
      const autoReply = box.querySelector(".interactive-btn-reply")?.value.trim() || "";
      if (title) {
        buttons.push({ id, title, auto_reply: autoReply });
      }
    });
    if (buttons.length === 0) { this.showToast("Add at least one quick-reply button", "warning"); return; }

    try {
      await API.sendChatMessage({
        recipient_phone: this.activeConvPhone,
        customer_name:   this.activeConvCustomerName || "Customer",
        customer_id:     this.activeConvCustomerId,
        message_text:    body,
        media_url:       imgUrl || null,
        buttons:         buttons
      });
      // Clear body
      const bodyEl = document.getElementById("interactiveBodyText");
      const imgEl  = document.getElementById("interactiveImageUrl");
      if (bodyEl) bodyEl.value = "";
      if (imgEl)  imgEl.value  = "";
      await this.openConversation(this.activeConvPhone, this.activeConvCustomerName, this.activeConvCustomerId);
      await this.loadConversations();
      this.showToast("Interactive message with custom auto-replies sent!", "success");
    } catch (err) {
      this.showToast("Send failed: " + err.message, "danger");
    }
  },

  // ======================== NEW CHAT MODAL ========================
  openNewChatModal() {
    const modal = document.getElementById("newChatModal");
    if (modal) modal.classList.add("open");
    const input = document.getElementById("newChatSearchInput");
    if (input) { input.value = ""; setTimeout(() => input.focus(), 50); }
    const results = document.getElementById("newChatSearchResults");
    if (results) results.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:0.85rem;"><i class="fa-solid fa-users" style="font-size:1.5rem;display:block;margin-bottom:8px;opacity:0.4;"></i>Type a name or phone number to search</div>`;
  },
  closeNewChatModal() {
    const modal = document.getElementById("newChatModal");
    if (modal) modal.classList.remove("open");
  },
  async searchCustomersForNewChat() {
    const q = (document.getElementById("newChatSearchInput")?.value || "").trim();
    const resultsEl = document.getElementById("newChatSearchResults");
    if (!resultsEl) return;
    if (!q) {
      resultsEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:0.85rem;">Type a name or phone number to search</div>`;
      return;
    }
    resultsEl.innerHTML = `<div style="padding:16px;text-align:center;color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Searching...</div>`;
    try {
      const data = await API.searchCustomersForChat(q);
      const customers = data.customers || [];
      if (customers.length === 0) {
        resultsEl.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:0.85rem;"><i class="fa-solid fa-user-slash" style="display:block;margin-bottom:8px;opacity:0.4;font-size:1.5rem;"></i>No customers found for "${q}"</div>`;
        return;
      }
      resultsEl.innerHTML = customers.map(c => `
        <div style="padding:12px 16px;border-bottom:1px solid var(--border-color);cursor:pointer;transition:background 0.15s;"
             onmouseover="this.style.background='rgba(0,168,132,0.08)'" onmouseout="this.style.background=''"
             onclick="App.startChatWithCustomer('${(c.phone||'').replace(/'/g,"\\'")}','${(c.name||'').replace(/'/g,"\\'")}',${c.id||'null'})">
          <div style="font-weight:600;font-size:0.88rem;">${c.name}</div>
          <div style="font-size:0.78rem;color:var(--text-muted);">${c.phone} &middot; ${c.loyalty_points||0} pts</div>
        </div>`).join("");
    } catch(err) {
      resultsEl.innerHTML = `<div style="padding:16px;text-align:center;color:var(--danger);font-size:0.82rem;">Error: ${err.message}</div>`;
    }
  },
  async startChatWithCustomer(phone, name, customerId) {
    this.closeNewChatModal();
    this.manualClosed = false;
    try {
      await API.unhideConversation(phone);
    } catch (_) {}
    await this.openConversation(phone, name, customerId);
    await this.loadConversations();
  },

  // ======================== REMINDER TRIGGERS ========================
  async triggerMissYouReminders() {
    this.showToast("Sending 'We Miss You' reminders…", "info");
    try {
      const res = await API.triggerMissYouReminders();
      this.showToast(`✅ Sent ${res.total_sent} "We Miss You" message(s)`, "success");
    } catch(err) { this.showToast("Error: " + err.message, "danger"); }
  },
  async triggerPointsReminders() {
    this.showToast("Sending points reminders…", "info");
    try {
      const res = await API.triggerPointsReminders();
      this.showToast(`✅ Sent ${res.total_sent} points reminder(s)`, "success");
    } catch(err) { this.showToast("Error: " + err.message, "danger"); }
  },

  // ======================== TOASTS ========================
  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icons = { success: "fa-circle-check", danger: "fa-triangle-exclamation", warning: "fa-triangle-exclamation", info: "fa-circle-info" };
    toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; toast.style.transform = "translateX(100%)"; toast.style.transition = "all 0.3s ease"; setTimeout(() => toast.remove(), 300); }, 4000);
  }
};

// ═════════════════════════════════════════════════════════════════
// VISUAL BOT FLOW BUILDER ENGINE
// ═════════════════════════════════════════════════════════════════
const FlowBuilder = {
  currentFlow: null,
  flowsList: [],
  connectingSource: null,
  scale: 1,

  toggleMobilePalette(force) {
    const panel = document.getElementById("flowComponentsPanel");
    const backdrop = document.getElementById("flowPaletteBackdrop");
    if (!panel) return;
    const isOpen = typeof force === "boolean" ? force : !panel.classList.contains("open");
    panel.classList.toggle("open", isOpen);
    if (backdrop) backdrop.classList.toggle("open", isOpen);
  },

  async init() {
    this.toggleMobilePalette(false);
    await this.loadFlows();
  },

  async loadFlows() {
    try {
      const shopId = App.currentShop ? App.currentShop.id : (App.currentUser ? App.currentUser.shop_id : 1);
      const token = localStorage.getItem("textile_token");
      const headers = token ? { "Authorization": token } : {};
      const res = await fetch(`/api/chatbot-flows?shop_id=${shopId}`, { headers });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch (e) { data = { success: false }; }
      if (data.success && data.flows && data.flows.length > 0) {
        this.flowsList = data.flows;
        this.populateFlowSelect();
        this.selectFlow(this.flowsList[0].id);
      } else {
        this.currentFlow = this.getDefaultFlow();
        this.renderCanvas();
      }
    } catch (err) {
      console.error("Error loading flows:", err);
      this.currentFlow = this.getDefaultFlow();
      this.renderCanvas();
    }
  },

  getDefaultFlow() {
    return {
      name: "Festive Offer Yes/No Flow",
      trigger_keyword: "offer, hi, help",
      flow_data: {
        nodes: [
          {
            id: "node_trigger",
            type: "trigger",
            title: "Inbound Trigger",
            keyword: "offer, hi, help, start",
            x: 50,
            y: 140
          },
          {
            id: "node_buttons_1",
            type: "buttons",
            title: "Interactive Reply Buttons",
            message: "Namaste {name}! 🛍️ Would you like to view our exclusive Festive Silk Collection with an instant 15% VIP discount?",
            x: 340,
            y: 100,
            buttons: [
              { id: "btn_yes", title: "Yes, View Offer", target: "node_text_yes" },
              { id: "btn_no", title: "No, Not Now", target: "node_text_no" },
              { id: "btn_agent", title: "Talk to Stylist", target: "node_text_agent" }
            ]
          },
          {
            id: "node_text_yes",
            type: "text",
            title: "Customer Presses YES",
            message: "🎉 Wonderful! Use voucher code *FESTIVE15* at checkout for flat 15% OFF!\n\n👗 Browse online catalog: https://srilakshmisilks.in/catalog\n⏳ Valid for 7 days. Enjoy your shopping!",
            x: 740,
            y: 40
          },
          {
            id: "node_text_no",
            type: "text",
            title: "Customer Presses NO",
            message: "Understood! No worries at all. Feel free to message us anytime if you need assistance. Have a wonderful day! 😊",
            x: 740,
            y: 200
          },
          {
            id: "node_text_agent",
            type: "text",
            title: "Showroom Stylist Handoff",
            message: "Namaste {name}! Our showroom associate has been notified and will reply directly in this chat shortly. 📞",
            x: 740,
            y: 340
          }
        ]
      }
    };
  },

  populateFlowSelect() {
    const sel = document.getElementById("flowSelectDropdown");
    if (!sel) return;
    sel.innerHTML = this.flowsList.map(f => `<option value="${f.id}">${f.name}</option>`).join("");
  },

  selectFlow(flowId) {
    const found = this.flowsList.find(f => f.id == flowId);
    if (found) {
      this.currentFlow = JSON.parse(JSON.stringify(found));
      if (!this.currentFlow.flow_data || !this.currentFlow.flow_data.nodes) {
        this.currentFlow.flow_data = this.getDefaultFlow().flow_data;
      }
      const nameInput = document.getElementById("flowNameInput");
      const trigInput = document.getElementById("flowTriggerInput");
      const sel = document.getElementById("flowSelectDropdown");
      if (nameInput) nameInput.value = this.currentFlow.name || "";
      if (trigInput) trigInput.value = this.currentFlow.trigger_keyword || "";
      if (sel) sel.value = found.id;
      this.renderCanvas();
    }
  },

  loadSelectedFlow() {
    const sel = document.getElementById("flowSelectDropdown");
    if (sel && sel.value) {
      this.selectFlow(sel.value);
    }
  },

  createNewFlow() {
    const newId = Date.now();
    this.currentFlow = {
      id: null,
      name: "New Custom Interactive Flow",
      trigger_keyword: "start, menu",
      flow_data: {
        nodes: [
          {
            id: "node_" + newId,
            type: "buttons",
            title: "Interactive Question",
            message: "Namaste {name}! How can we assist you today?",
            x: 100,
            y: 100,
            buttons: [
              { id: "btn_1", title: "Yes", target: "node_yes_" + newId },
              { id: "btn_2", title: "No", target: "node_no_" + newId }
            ]
          },
          {
            id: "node_yes_" + newId,
            type: "text",
            title: "Response for YES",
            message: "Thank you for confirming YES! We are processing your request.",
            x: 480,
            y: 60
          },
          {
            id: "node_no_" + newId,
            type: "text",
            title: "Response for NO",
            message: "No problem! Let us know if you need anything else.",
            x: 480,
            y: 220
          }
        ]
      }
    };
    const nameInput = document.getElementById("flowNameInput");
    const trigInput = document.getElementById("flowTriggerInput");
    if (nameInput) nameInput.value = this.currentFlow.name;
    if (trigInput) trigInput.value = this.currentFlow.trigger_keyword;
    this.renderCanvas();
    App.showToast("Created new interactive flow canvas", "info");
  },

  renderCanvas() {
    const container = document.getElementById("flowNodesContainer");
    const svg = document.getElementById("flowConnectionsSvg");
    if (!container || !svg || !this.currentFlow || !this.currentFlow.flow_data) return;

    container.innerHTML = "";
    const nodes = this.currentFlow.flow_data.nodes || [];

    nodes.forEach(node => {
      const el = document.createElement("div");
      el.className = "flow-node";
      el.id = `flow_node_${node.id}`;
      el.style.left = `${node.x || 60}px`;
      el.style.top = `${node.y || 60}px`;

      let icon = "fa-message";
      let iconBg = "rgba(16, 185, 129, 0.15)";
      let iconColor = "#10b981";
      if (node.type === "trigger") { icon = "fa-bolt"; iconBg = "rgba(234, 88, 12, 0.15)"; iconColor = "#ea580c"; }
      else if (node.type === "buttons") { icon = "fa-list-check"; iconBg = "rgba(0, 168, 132, 0.18)"; iconColor = "#00a884"; }
      else if (node.type === "condition") { icon = "fa-code-branch"; iconBg = "rgba(147, 51, 234, 0.15)"; iconColor = "#9333ea"; }
      else if (node.type === "coupon") { icon = "fa-tag"; iconBg = "rgba(245, 158, 11, 0.15)"; iconColor = "#d97706"; }
      else if (node.type === "agent") { icon = "fa-headset"; iconBg = "rgba(236, 72, 153, 0.15)"; iconColor = "#db2777"; }
      else if (node.type === "list") { icon = "fa-bars-staggered"; iconBg = "rgba(14, 165, 233, 0.15)"; iconColor = "#0ea5e9"; }

      let bodyHtml = "";
      if (node.type === "trigger") {
        bodyHtml = `
          <label style="font-size:0.72rem;font-weight:700;color:var(--text-muted);">Trigger Keywords:</label>
          <input type="text" class="form-control" style="font-size:0.78rem;padding:5px 8px;" value="${node.keyword || ''}" 
            onchange="FlowBuilder.updateNodeField('${node.id}', 'keyword', this.value)" placeholder="e.g. offer, hi, help">
        `;
      } else if (node.type === "buttons") {
        const btnsHtml = (node.buttons || []).map((b, idx) => `
          <div class="flow-button-item">
            <span style="font-size:0.72rem;color:#00a884;font-weight:bold;">#${idx+1}</span>
            <input type="text" class="flow-button-label-input" value="${b.title || ''}" 
              onchange="FlowBuilder.updateButtonTitle('${node.id}', '${b.id}', this.value)" placeholder="Button label (e.g. Yes)">
            <button onclick="FlowBuilder.removeButton('${node.id}', '${b.id}')" style="background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:0.72rem;" title="Remove Button"><i class="fa-solid fa-xmark"></i></button>
            <div class="flow-port-out ${b.target ? 'connected' : ''}" id="port_out_${node.id}_${b.id}" 
              onclick="FlowBuilder.handlePortOutClick('${node.id}', '${b.id}', event)" title="${b.target ? 'Connected to ' + b.target + ' (Click to reconnect)' : 'Click to connect to another node'}"></div>
          </div>
        `).join("");

        bodyHtml = `
          <label style="font-size:0.72rem;font-weight:700;color:var(--text-muted);">Question / Message:</label>
          <textarea class="flow-node-textarea" onchange="FlowBuilder.updateNodeField('${node.id}', 'message', this.value)" placeholder="Type question for customer...">${node.message || ''}</textarea>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
            <label style="font-size:0.72rem;font-weight:700;color:var(--text-muted);margin:0;">Reply Buttons (Branches):</label>
            <button class="flow-add-btn" onclick="FlowBuilder.addButton('${node.id}')" style="padding:2px 6px;font-size:0.7rem;"><i class="fa-solid fa-plus"></i> Add Option</button>
          </div>
          <div class="flow-buttons-list">${btnsHtml}</div>
        `;
      } else {
        bodyHtml = `
          <label style="font-size:0.72rem;font-weight:700;color:var(--text-muted);">Response Message:</label>
          <textarea class="flow-node-textarea" onchange="FlowBuilder.updateNodeField('${node.id}', 'message', this.value)" placeholder="Type response when branch reached...">${node.message || ''}</textarea>
        `;
      }

      el.innerHTML = `
        ${node.type !== 'trigger' ? `<div class="flow-port-in" id="port_in_${node.id}" onclick="FlowBuilder.handlePortInClick('${node.id}', event)" title="Connect input here"></div>` : ''}
        <div class="flow-node-header" onmousedown="FlowBuilder.startDrag('${node.id}', event)">
          <div class="flow-node-title-group">
            <div class="flow-node-icon" style="background:${iconBg};color:${iconColor};"><i class="fa-solid ${icon}"></i></div>
            <input type="text" class="flow-node-title" value="${node.title || ''}" onchange="FlowBuilder.updateNodeField('${node.id}', 'title', this.value)" style="border:none;background:transparent;">
          </div>
          <button class="flow-node-del-btn" onclick="FlowBuilder.deleteNode('${node.id}')" title="Delete Node"><i class="fa-solid fa-trash"></i></button>
        </div>
        <div class="flow-node-body">
          ${bodyHtml}
        </div>
      `;

      container.appendChild(el);
    });

    this.renderWires();
  },

  renderWires() {
    const svg = document.getElementById("flowConnectionsSvg");
    if (!svg || !this.currentFlow || !this.currentFlow.flow_data) return;

    svg.innerHTML = "";
    const container = document.getElementById("flowCanvasContainer");
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    const scrollL = container.scrollLeft;
    const scrollT = container.scrollTop;

    const nodes = this.currentFlow.flow_data.nodes || [];

    nodes.forEach(n => {
      if (n.buttons) {
        n.buttons.forEach(b => {
          if (b.target) {
            const outPort = document.getElementById(`port_out_${n.id}_${b.id}`);
            const inPort = document.getElementById(`port_in_${b.target}`);
            if (outPort && inPort) {
              const r1 = outPort.getBoundingClientRect();
              const r2 = inPort.getBoundingClientRect();

              const x1 = r1.left - cRect.left + scrollL + 7;
              const y1 = r1.top - cRect.top + scrollT + 7;
              const x2 = r2.left - cRect.left + scrollL + 8;
              const y2 = r2.top - cRect.top + scrollT + 8;

              const dx = Math.max(Math.abs(x2 - x1) * 0.55, 50);
              const pathData = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

              const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
              path.setAttribute("d", pathData);
              path.setAttribute("class", "flow-wire");
              path.setAttribute("title", `Connected to ${b.target} (Click to disconnect)`);
              path.onclick = () => {
                if (confirm(`Disconnect "${b.title || 'Button'}" from this response?`)) {
                  b.target = null;
                  FlowBuilder.renderCanvas();
                }
              };

              svg.appendChild(path);
            }
          }
        });
      }
    });
  },

  startDrag(nodeId, e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON" || e.target.tagName === "TEXTAREA") return;
    const node = this.currentFlow.flow_data.nodes.find(n => n.id === nodeId);
    if (!node) return;

    const nodeEl = document.getElementById(`flow_node_${nodeId}`);
    if (nodeEl) nodeEl.classList.add("dragging");

    const startX = e.clientX;
    const startY = e.clientY;
    const initialX = node.x || 0;
    const initialY = node.y || 0;

    const onMove = (moveEvt) => {
      node.x = Math.max(initialX + (moveEvt.clientX - startX), 10);
      node.y = Math.max(initialY + (moveEvt.clientY - startY), 10);
      if (nodeEl) {
        nodeEl.style.left = `${node.x}px`;
        nodeEl.style.top = `${node.y}px`;
      }
      FlowBuilder.renderWires();
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      if (nodeEl) nodeEl.classList.remove("dragging");
      FlowBuilder.renderWires();
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  },

  handlePortOutClick(nodeId, buttonId, e) {
    e.stopPropagation();
    this.connectingSource = { nodeId, buttonId };
    App.showToast(`Selected button. Now click the target node's LEFT circle to connect!`, "info");
  },

  handlePortInClick(targetNodeId, e) {
    e.stopPropagation();
    if (this.connectingSource) {
      const sourceNode = this.currentFlow.flow_data.nodes.find(n => n.id === this.connectingSource.nodeId);
      if (sourceNode && sourceNode.buttons) {
        const btn = sourceNode.buttons.find(b => b.id === this.connectingSource.buttonId);
        if (btn) {
          btn.target = targetNodeId;
          App.showToast(`Connected "${btn.title}" to destination response!`, "success");
          this.connectingSource = null;
          this.renderCanvas();
          return;
        }
      }
      this.connectingSource = null;
    } else {
      App.showToast(`First click a colored circle on a button option, then click here to link them.`, "info");
    }
  },

  addNode(type) {
    if (!this.currentFlow || !this.currentFlow.flow_data) return;
    const newId = "node_" + Date.now();
    const existing = this.currentFlow.flow_data.nodes || [];
    const count = existing.length;

    let newNode = {
      id: newId,
      type: type,
      title: type === 'buttons' ? 'Reply Buttons' : (type === 'text' ? 'Text Message' : type.toUpperCase()),
      x: 100 + (count % 3) * 260,
      y: 80 + Math.floor(count / 3) * 160
    };

    if (type === 'buttons') {
      newNode.message = "Namaste {name}! Please choose an option:";
      newNode.buttons = [
        { id: "btn_yes_" + newId, title: "Yes", target: null },
        { id: "btn_no_" + newId, title: "No", target: null }
      ];
    } else if (type === 'text') {
      newNode.message = "Hello! Here is your custom message from Sri Lakshmi Silks.";
    } else if (type === 'trigger') {
      newNode.keyword = "offer, hi, help";
    } else if (type === 'coupon') {
      newNode.title = "Discount Coupon Code";
      newNode.message = "🎁 Special Offer! Use code FESTIVE15 for flat 15% OFF at billing.";
    } else if (type === 'agent') {
      newNode.title = "Showroom Stylist Alert";
      newNode.message = "A showroom specialist has been notified and will message you shortly here. 📞";
    } else if (type === 'condition') {
      newNode.title = "Audience Filter";
      newNode.message = "Condition: VIP Customer OR Loyalty Points > 500";
    } else if (type === 'list') {
      newNode.title = "Interactive Menu List";
      newNode.message = "Browse Categories: 1. Bridal Sarees  2. Silk Kurtis  3. Menswear";
    }

    existing.push(newNode);
    this.currentFlow.flow_data.nodes = existing;
    this.renderCanvas();
    if (window.innerWidth <= 768) {
      this.toggleMobilePalette(false);
    }
    App.showToast(`Added ${newNode.title} to canvas`, "success");
  },

  deleteNode(nodeId) {
    if (!confirm("Are you sure you want to delete this node?")) return;
    this.currentFlow.flow_data.nodes = this.currentFlow.flow_data.nodes.filter(n => n.id !== nodeId);
    this.currentFlow.flow_data.nodes.forEach(n => {
      if (n.buttons) {
        n.buttons.forEach(b => {
          if (b.target === nodeId) b.target = null;
        });
      }
    });
    this.renderCanvas();
    App.showToast("Node removed", "info");
  },

  addButton(nodeId) {
    const node = this.currentFlow.flow_data.nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (!node.buttons) node.buttons = [];
    if (node.buttons.length >= 3) {
      App.showToast("WhatsApp limits interactive button messages to maximum 3 buttons.", "warning");
      return;
    }
    const btnNum = node.buttons.length + 1;
    node.buttons.push({
      id: "btn_" + Date.now(),
      title: "Option " + btnNum,
      target: null
    });
    this.renderCanvas();
  },

  removeButton(nodeId, buttonId) {
    const node = this.currentFlow.flow_data.nodes.find(n => n.id === nodeId);
    if (!node || !node.buttons) return;
    node.buttons = node.buttons.filter(b => b.id !== buttonId);
    this.renderCanvas();
  },

  updateNodeField(nodeId, field, val) {
    const node = this.currentFlow.flow_data.nodes.find(n => n.id === nodeId);
    if (node) {
      node[field] = val;
      this.renderWires();
    }
  },

  updateButtonTitle(nodeId, buttonId, val) {
    const node = this.currentFlow.flow_data.nodes.find(n => n.id === nodeId);
    if (node && node.buttons) {
      const b = node.buttons.find(btn => btn.id === buttonId);
      if (b) b.title = val;
    }
  },

  autoArrange() {
    if (!this.currentFlow || !this.currentFlow.flow_data) return;
    const nodes = this.currentFlow.flow_data.nodes || [];

    const triggers = nodes.filter(n => n.type === 'trigger');
    const questions = nodes.filter(n => n.type === 'buttons' || n.type === 'list');
    const actions = nodes.filter(n => n.type !== 'trigger' && n.type !== 'buttons' && n.type !== 'list');

    triggers.forEach((n, idx) => {
      n.x = 40;
      n.y = 120 + idx * 160;
    });

    questions.forEach((n, idx) => {
      n.x = 340;
      n.y = 80 + idx * 260;
    });

    actions.forEach((n, idx) => {
      n.x = 720;
      n.y = 40 + idx * 150;
    });

    this.renderCanvas();
    App.showToast("✨ Auto-arranged nodes into neat columns", "success");
  },

  zoomIn() {
    this.scale = Math.min(this.scale + 0.1, 1.5);
    this.applyZoom();
  },
  zoomOut() {
    this.scale = Math.max(this.scale - 0.1, 0.6);
    this.applyZoom();
  },
  zoomReset() {
    this.scale = 1;
    this.applyZoom();
  },
  applyZoom() {
    const container = document.getElementById("flowNodesContainer");
    const svg = document.getElementById("flowConnectionsSvg");
    if (container) {
      container.style.transform = `scale(${this.scale})`;
      container.style.transformOrigin = `0 0`;
    }
    if (svg) {
      svg.style.transform = `scale(${this.scale})`;
      svg.style.transformOrigin = `0 0`;
    }
  },

  async saveCurrentFlow() {
    const name = document.getElementById("flowNameInput").value.trim() || "Interactive Flow";
    const trigger = document.getElementById("flowTriggerInput").value.trim();
    const saveBtn = document.getElementById("flowSaveBtn");

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    }

    try {
      const shopId = App.currentShop ? App.currentShop.id : (App.currentUser ? App.currentUser.shop_id : 1);
      const payload = {
        id: this.currentFlow ? this.currentFlow.id : null,
        shop_id: shopId,
        name: name,
        trigger_keyword: trigger,
        flow_data: this.currentFlow ? this.currentFlow.flow_data : {},
        is_active: 1
      };

      const token = localStorage.getItem("textile_token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = token;

      const res = await fetch("/api/chatbot-flows", {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
      });
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (parseErr) {
        throw new Error(`Server status ${res.status}: ${text.substring(0, 100)}`);
      }

      if (data.success) {
        App.showToast("✅ Interactive Flow saved successfully!", "success");
        await this.loadFlows();
        if (data.id) this.selectFlow(data.id);
      } else {
        App.showToast(data.error || "Failed to save flow", "danger");
      }
    } catch (err) {
      App.showToast("Error saving flow: " + err.message, "danger");
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Flow';
      }
    }
  },

  // ── Send Interactive Flow to Real Customers ──────────────────
  openSendFlowModal() {
    const modal = document.getElementById("flowSendModal");
    if (!modal) return;

    const flowName = (this.currentFlow ? this.currentFlow.name : "") || "Interactive Flow";
    const flowNameEl = document.getElementById("flowSendModalFlowName");
    if (flowNameEl) flowNameEl.textContent = flowName;

    // Find interactive question node in current flow
    const flowData = this.currentFlow ? this.currentFlow.flow_data : null;
    let questionNode = null;
    if (flowData && flowData.nodes) {
      questionNode = flowData.nodes.find(n => n.type === "buttons" || n.type === "reply_buttons") || flowData.nodes[0];
    }

    const previewMsgEl = document.getElementById("flowSendPreviewMessage");
    const previewBtnsEl = document.getElementById("flowSendPreviewButtons");
    if (previewMsgEl) {
      previewMsgEl.textContent = questionNode ? (questionNode.message || questionNode.title || "") : "No message configured in flow";
    }
    if (previewBtnsEl) {
      if (questionNode && questionNode.buttons && questionNode.buttons.length > 0) {
        previewBtnsEl.innerHTML = questionNode.buttons.map(b => 
          `<div class="flow-preview-btn-pill"><i class="fa-solid fa-reply"></i> ${b.title || b.id}</div>`
        ).join("");
      } else {
        previewBtnsEl.innerHTML = `<em style="color:#64748b;font-size:0.75rem;">(No buttons configured on question node)</em>`;
      }
    }

    // Populate customer dropdown from App.allCustomers
    const custSelect = document.getElementById("flowSendCustomerSelect");
    if (custSelect) {
      const customers = App.allCustomers || [];
      if (customers.length > 0) {
        custSelect.innerHTML = `<option value="">-- Choose an existing customer (${customers.length} available) --</option>` +
          customers.map(c => `<option value="${c.phone}" data-name="${c.name || ''}" data-id="${c.id}">${c.name || 'Customer'} (${c.phone}) - ${c.loyalty_points || 0} pts</option>`).join("");
      } else {
        custSelect.innerHTML = `<option value="">No saved customers found. Enter phone below.</option>`;
      }
    }

    // Default to active conversation phone if available
    const phoneInput = document.getElementById("flowSendCustomPhone");
    if (phoneInput) {
      phoneInput.value = App.activeConvPhone || "";
    }

    this.toggleSendTargetUI();
    modal.classList.add("open");
  },

  closeSendFlowModal() {
    const modal = document.getElementById("flowSendModal");
    if (modal) modal.classList.remove("open");
  },

  toggleSendTargetUI() {
    const targetType = document.querySelector('input[name="flowSendTarget"]:checked')?.value || "single";
    const singlePanel = document.getElementById("flowSendSinglePanel");
    const segmentPanel = document.getElementById("flowSendSegmentPanel");
    if (singlePanel) singlePanel.style.display = targetType === "single" ? "block" : "none";
    if (segmentPanel) segmentPanel.style.display = targetType === "segment" ? "block" : "none";
  },

  onSelectCustomerForSend(selectEl) {
    if (!selectEl) return;
    const phone = selectEl.value;
    const phoneInput = document.getElementById("flowSendCustomPhone");
    if (phoneInput && phone) {
      phoneInput.value = phone;
    }
  },

  async submitSendFlow() {
    const targetType = document.querySelector('input[name="flowSendTarget"]:checked')?.value || "single";
    const shopId = App.currentShop ? App.currentShop.id : (App.currentUser ? App.currentUser.shop_id : 1);
    const flowId = this.currentFlow ? this.currentFlow.id : null;
    const sendBtn = document.getElementById("flowSendSubmitBtn");

    let phone = "";
    let customerName = "";
    let segment = "all";

    if (targetType === "single") {
      const selectEl = document.getElementById("flowSendCustomerSelect");
      const phoneInput = document.getElementById("flowSendCustomPhone");
      phone = (phoneInput?.value || "").trim() || (selectEl?.value || "").trim();
      if (selectEl && selectEl.selectedOptions && selectEl.selectedOptions[0]) {
        customerName = selectEl.selectedOptions[0].dataset.name || "";
      }
      if (!phone) {
        App.showToast("Please enter or select a recipient WhatsApp number", "warning");
        return;
      }
    } else {
      segment = document.getElementById("flowSendSegmentSelect")?.value || "all";
    }

    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending WhatsApp Flow...';
    }

    try {
      const token = localStorage.getItem("textile_token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = token;

      const payload = {
        shop_id: shopId,
        flow_id: flowId,
        flow_data: this.currentFlow ? this.currentFlow.flow_data : null,
        target_type: targetType,
        phone: phone,
        customer_name: customerName,
        segment: segment
      };

      const res = await fetch("/api/chatbot-flows/send", {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch (e) { throw new Error(`Server returned: ${text.substring(0, 100)}`); }

      if (data.success) {
        App.showToast(`✅ ${data.message}`, "success");
        this.closeSendFlowModal();
        if (typeof App.loadConversations === "function") {
          await App.loadConversations();
          if (phone && typeof App.openConversation === "function") {
            await App.openConversation(phone, customerName);
          }
        }
      } else {
        App.showToast(data.error || "Failed to dispatch interactive flow", "danger");
      }
    } catch (err) {
      App.showToast("Error sending flow: " + err.message, "danger");
    } finally {
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fa-brands fa-whatsapp"></i> Send WhatsApp Flow Now';
      }
    }
  },

  // ── Real-Time WhatsApp Interactive Simulator ──────────────────
  openSimulatorModal() {
    const modal = document.getElementById("flowSimulatorModal");
    if (modal) modal.classList.add("open");
    this.restartSimulation();
  },

  closeSimulatorModal() {
    const modal = document.getElementById("flowSimulatorModal");
    if (modal) modal.classList.remove("open");
  },

  restartSimulation() {
    const area = document.getElementById("simFlowMessagesArea");
    if (!area || !this.currentFlow || !this.currentFlow.flow_data) return;

    area.innerHTML = "";
    const nodes = this.currentFlow.flow_data.nodes || [];
    let startNode = nodes.find(n => n.type === 'buttons') || nodes[0];

    if (!startNode) {
      area.innerHTML = `<div style="text-align:center;color:#64748b;padding:30px;">No nodes created in this flow yet. Add a Reply Buttons node to test!</div>`;
      return;
    }

    this.simCurrentNodeId = startNode.id;
    this.renderSimNode(startNode);
  },

  renderSimNode(node) {
    const area = document.getElementById("simFlowMessagesArea");
    if (!area) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const custName = App.currentUser ? (App.currentUser.shop_name || "Valued Customer") : "Dhamu";
    const shopName = App.currentShop ? App.currentShop.name : "Sri Lakshmi Silks";

    let msgText = (node.message || node.title || "")
      .replace(/{name}/g, custName)
      .replace(/{shop}/g, shopName)
      .replace(/{points}/g, "1,250");

    let buttonsHtml = "";
    if (node.buttons && node.buttons.length > 0) {
      buttonsHtml = `
        <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px;">
          ${node.buttons.map(b => `
            <button class="chat-button-pill" onclick="FlowBuilder.handleSimButtonClick('${node.id}', '${b.id}', '${b.title.replace(/'/g, "\\'")}')" 
              style="padding:8px 12px;font-size:0.78rem;font-weight:700;border:1px solid #00a884;background:#fff;color:#00a884;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;transition:all 0.15s;">
              <i class="fa-solid fa-reply" style="font-size:0.7rem;"></i> ${b.title || 'Option'}
            </button>
          `).join("")}
        </div>
      `;
    }

    const bubbleEl = document.createElement("div");
    bubbleEl.style.display = "flex";
    bubbleEl.style.flexDirection = "column";
    bubbleEl.style.alignItems = "flex-start";
    bubbleEl.style.maxWidth = "88%";

    bubbleEl.innerHTML = `
      <div class="chat-bubble" style="background:#fff;border-radius:12px;padding:10px 12px;font-size:0.78rem;line-height:1.45;color:#1e293b;box-shadow:0 1px 2px rgba(0,0,0,0.1);">
        ${msgText.replace(/\n/g, "<br>")}
        <div style="font-size:0.62rem;color:#94a3b8;text-align:right;margin-top:4px;">${timeStr}</div>
      </div>
      ${buttonsHtml}
    `;

    area.appendChild(bubbleEl);
    area.scrollTop = area.scrollHeight;
  },

  handleSimButtonClick(fromNodeId, buttonId, buttonTitle) {
    const area = document.getElementById("simFlowMessagesArea");
    if (!area) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userBubble = document.createElement("div");
    userBubble.style.display = "flex";
    userBubble.style.justifyContent = "flex-end";
    userBubble.style.width = "100%";
    userBubble.innerHTML = `
      <div class="chat-bubble outbound" style="background:#d9fdd3;color:#111b21;border-radius:12px;padding:8px 12px;font-size:0.78rem;max-width:80%;box-shadow:0 1px 2px rgba(0,0,0,0.1);">
        <i class="fa-solid fa-check" style="color:#00a884;margin-right:4px;"></i> ${buttonTitle}
        <div style="font-size:0.6rem;color:#64748b;text-align:right;margin-top:2px;">${timeStr} <i class="fa-solid fa-check-double" style="color:#53bdeb;"></i></div>
      </div>
    `;
    area.appendChild(userBubble);
    area.scrollTop = area.scrollHeight;

    area.querySelectorAll(".chat-button-pill").forEach(b => {
      b.disabled = true;
      b.style.opacity = "0.5";
      b.style.cursor = "default";
    });

    const fromNode = this.currentFlow.flow_data.nodes.find(n => n.id === fromNodeId);
    let targetNode = null;
    if (fromNode && fromNode.buttons) {
      const btn = fromNode.buttons.find(b => b.id === buttonId);
      if (btn && btn.target) {
        targetNode = this.currentFlow.flow_data.nodes.find(n => n.id === btn.target);
      }
    }

    setTimeout(() => {
      if (targetNode) {
        FlowBuilder.renderSimNode(targetNode);
      } else {
        const fallback = document.createElement("div");
        fallback.style.display = "flex";
        fallback.style.alignItems = "flex-start";
        fallback.style.maxWidth = "88%";
        fallback.innerHTML = `
          <div class="chat-bubble" style="background:#fff;border-radius:12px;padding:10px 12px;font-size:0.78rem;line-height:1.45;color:#1e293b;box-shadow:0 1px 2px rgba(0,0,0,0.1);">
            Thank you! Your response "<strong>${buttonTitle}</strong>" was received. (Connect this button to a response node in the Flow Builder to customize!)
            <div style="font-size:0.62rem;color:#94a3b8;text-align:right;margin-top:4px;">${timeStr}</div>
          </div>
        `;
        area.appendChild(fallback);
        area.scrollTop = area.scrollHeight;
      }
    }, 450);
  }
};

window.FlowBuilder = FlowBuilder;

document.addEventListener("DOMContentLoaded", () => App.init());
