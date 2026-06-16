(() => {
  const tg = window.Telegram?.WebApp;
  const page = document.body.dataset.page;
  const apiMeta = document.querySelector("meta[name='taza-api-base']");
  const apiBase = (apiMeta?.content || "").replace(/\/$/, "");
  const statusLine = document.getElementById("statusLine");
  const toast = document.getElementById("toast");
  const refreshBtn = document.getElementById("refreshBtn");

  if (!apiBase || apiBase.includes("YOUR-RENDER-APP")) {
    statusLine.textContent = "يرجى ضبط عنوان الـ API في ملف index.html / restaurant.html.";
    return;
  }

  if (!tg || !tg.initDataUnsafe?.user?.id) {
    statusLine.textContent = "افتح هذا التطبيق من داخل تيليغرام.";
    return;
  }

  const userId = tg.initDataUnsafe.user.id;
  const initData = tg.initData || "";
  const authHeaders = initData ? { Authorization: `tma ${initData}` } : {};

  tg.ready();
  tg.expand();

  const theme = () => {
    const scheme = tg.colorScheme || "light";
    document.documentElement.dataset.theme = scheme;
    const params = tg.themeParams || {};
    if (params.bg_color) {
      document.documentElement.style.setProperty("--tg-bg", params.bg_color);
    }
  };

  theme();
  tg.onEvent("themeChanged", theme);

  const showToast = (message, tone = "success") => {
    toast.textContent = message;
    toast.className = `toast ${tone}`;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 2200);
  };

  const apiFetch = async (path, options = {}) => {
    const headers = { ...authHeaders, ...(options.headers || {}) };
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(`${apiBase}${path}`, { ...options, headers });
    return response;
  };

  const escapeHtml = (text) =>
    String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");

  const formatMoney = (value) =>
    Number(value || 0).toLocaleString("ar-SY");

  const switchTab = (tab) => {
    document.querySelectorAll(".bottom-nav .nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });
    document.querySelectorAll("main").forEach((view) => {
      view.classList.toggle("hidden", view.id !== `${tab}View`);
    });
  };

  const bindNav = (onSwitch) => {
    document.querySelectorAll(".bottom-nav .nav-item").forEach((btn) => {
      btn.addEventListener("click", () => onSwitch(btn.dataset.tab));
    });
  };

  const loadImage = async (imgEl, fileId) => {
    try {
      const res = await apiFetch(
        `/api/file?user_id=${userId}&file_id=${encodeURIComponent(fileId)}`
      );
      if (!res.ok) {
        throw new Error("image");
      }
      const blob = await res.blob();
      imgEl.src = URL.createObjectURL(blob);
    } catch (err) {
      imgEl.remove();
    }
  };

  const modal = {
    root: document.getElementById("modal"),
    title: document.getElementById("modalTitle"),
    input: document.getElementById("modalInput"),
    cancel: document.getElementById("modalCancel"),
    confirm: document.getElementById("modalConfirm"),
    onConfirm: null,
  };

  const openModal = (title, initialValue, onConfirm) => {
    if (!modal.root) return;
    modal.title.textContent = title;
    modal.input.value = initialValue || "";
    modal.onConfirm = onConfirm;
    modal.root.classList.remove("hidden");
    modal.input.focus();
  };

  const closeModal = () => {
    if (!modal.root) return;
    modal.root.classList.add("hidden");
    modal.onConfirm = null;
  };

  if (modal.cancel) {
    modal.cancel.addEventListener("click", closeModal);
    modal.confirm.addEventListener("click", () => {
      if (modal.onConfirm) {
        modal.onConfirm(modal.input.value);
      }
      closeModal();
    });
  }

  const initCustomer = () => {
    const bagsView = document.getElementById("bagsView");
    const ordersView = document.getElementById("ordersView");
    const filters = document.getElementById("typeFilters");
    let allBags = [];
    let activeType = "all";
    let selectedBagId = null;

    const updateMainButton = () => {
      if (selectedBagId && tg.MainButton) {
        tg.MainButton.setText("تأكيد الحجز");
        tg.MainButton.show();
      } else if (tg.MainButton) {
        tg.MainButton.hide();
      }
    };

    tg.MainButton.onClick(async () => {
      if (selectedBagId) {
        await reserveBag(selectedBagId);
      }
    });
    updateMainButton();

    const renderFilters = (bags) => {
      const types = new Map();
      bags.forEach((bag) => {
        types.set(bag.type, bag.emoji);
      });
      filters.innerHTML = "";

      const allChip = document.createElement("button");
      allChip.className = `chip ${activeType === "all" ? "active" : ""}`;
      allChip.textContent = "الكل";
      allChip.addEventListener("click", () => {
        activeType = "all";
        renderFilters(bags);
        renderBags(bags);
      });
      filters.appendChild(allChip);

      types.forEach((emoji, type) => {
        const chip = document.createElement("button");
        chip.className = `chip ${activeType === type ? "active" : ""}`;
        chip.textContent = `${emoji} ${type}`;
        chip.addEventListener("click", () => {
          activeType = type;
          renderFilters(bags);
          renderBags(bags);
        });
        filters.appendChild(chip);
      });
    };

    const renderBags = (bags) => {
      const view =
        activeType === "all"
          ? bags
          : bags.filter((bag) => bag.type === activeType);
      bagsView.innerHTML = "";

      if (!view.length) {
        bagsView.innerHTML = "<div class='empty'>لا توجد أكياس مطابقة حالياً.</div>";
        return;
      }

      view.forEach((bag, index) => {
        const card = document.createElement("article");
        card.className = "card bag-card";
        card.style.animationDelay = `${index * 0.03}s`;
        card.dataset.bagId = bag.bag_id;

        const image = document.createElement("div");
        image.className = "card-image";
        image.textContent = bag.emoji || "📦";
        if (bag.photo_file_id) {
          const img = document.createElement("img");
          img.alt = bag.restaurant_name;
          image.textContent = "";
          image.appendChild(img);
          loadImage(img, bag.photo_file_id);
        }

        const body = document.createElement("div");
        body.className = "card-body";
        body.innerHTML = `
          <div class="title">${escapeHtml(bag.restaurant_name)} ${bag.emoji}</div>
          <div class="meta">📍 ${escapeHtml(bag.pickup_address || "")}</div>
          <div class="price-row">
            <div class="price-new">${formatMoney(bag.discounted_price)} ل.س</div>
            <div class="price-old">${formatMoney(bag.original_price)} ل.س</div>
          </div>
          <div class="meta">🕒 ${escapeHtml(bag.pickup_start)} - ${escapeHtml(
          bag.pickup_end
        )}</div>
          <div class="meta"><span class="badge">متبقي ${bag.remaining}</span></div>
          <div class="actions">
            <button class="btn primary" data-action="reserve">احجز</button>
          </div>
        `;

        card.appendChild(image);
        card.appendChild(body);

        card.addEventListener("click", (event) => {
          if (event.target.dataset.action === "reserve") {
            return;
          }
          selectedBagId = bag.bag_id;
          updateMainButton();
          tg.HapticFeedback?.selectionChanged();
        });

        const reserveButton = body.querySelector("button[data-action='reserve']");
        reserveButton.addEventListener("click", async () => {
          await reserveBag(bag.bag_id);
        });

        bagsView.appendChild(card);
      });
    };

    const renderOrders = (orders) => {
      ordersView.innerHTML = "";
      if (!orders.length) {
        ordersView.innerHTML = "<div class='empty'>لا توجد طلبات حالياً.</div>";
        return;
      }

      orders.forEach((order, index) => {
        const card = document.createElement("article");
        card.className = "card";
        card.style.animationDelay = `${index * 0.03}s`;
        card.innerHTML = `
          <div class="card-body">
            <div class="title">${escapeHtml(order.order_code)}</div>
            <div class="meta">${order.status_emoji} ${escapeHtml(
          order.status_label
        )}</div>
            <div class="meta">${escapeHtml(order.restaurant_name)}</div>
            <div class="meta">🕒 ${escapeHtml(
          order.pickup_start
        )} - ${escapeHtml(order.pickup_end)}</div>
          </div>
        `;
        ordersView.appendChild(card);
      });
    };

    const loadBags = async () => {
      statusLine.textContent = "جارٍ تحميل الأكياس...";
      const res = await apiFetch(`/api/bags?user_id=${userId}`);
      const data = await res.json();
      if (!data.success) {
        statusLine.textContent = data.message || "تعذر تحميل البيانات.";
        return;
      }

      if (data.needs_area) {
        statusLine.textContent = "حدّد منطقتك من البوت لعرض الأكياس القريبة.";
        bagsView.innerHTML = "<div class='empty'>لا توجد أكياس حتى الآن.</div>";
        return;
      }

      statusLine.textContent = `منطقتك: ${data.area}`;
      allBags = data.bags || [];
      renderFilters(allBags);
      renderBags(allBags);
    };

    const loadOrders = async () => {
      const res = await apiFetch(`/api/orders?user_id=${userId}`);
      const data = await res.json();
      if (!data.success) {
        ordersView.innerHTML = "<div class='empty'>تعذر تحميل الطلبات.</div>";
        return;
      }
      renderOrders(data.orders || []);
    };

    const reserveBag = async (bagId) => {
      const res = await apiFetch("/api/reserve", {
        method: "POST",
        body: JSON.stringify({ user_id: userId, bag_id: bagId }),
      });
      const data = await res.json();
      if (!data.success) {
        tg.HapticFeedback?.notificationOccurred("error");
        tg.showAlert(data.message || "تعذر الحجز.");
        return;
      }

      tg.HapticFeedback?.notificationOccurred("success");
      tg.sendData(
        JSON.stringify({
          action: "reserve",
          order_code: data.order_code,
          bag_id: bagId,
        })
      );
      showToast("تم إرسال التأكيد إلى البوت.", "success");
      selectedBagId = null;
      updateMainButton();
      await loadBags();
      await loadOrders();
    };

    bindNav((tab) => {
      switchTab(tab);
      if (tab === "orders") {
        selectedBagId = null;
        updateMainButton();
        loadOrders();
      }
    });

    refreshBtn.addEventListener("click", async () => {
      await loadBags();
      await loadOrders();
      showToast("تم تحديث البيانات", "success");
    });

    loadBags();
  };

  const initRestaurant = () => {
    const bagsView = document.getElementById("bagsView");
    const ordersView = document.getElementById("ordersView");
    const summaryLine = document.getElementById("summaryLine");

    const renderSummary = (bags, orders) => {
      const total = bags.reduce((sum, bag) => sum + bag.quantity, 0);
      const remaining = bags.reduce((sum, bag) => sum + bag.remaining, 0);
      const sold = Math.max(total - remaining, 0);
      const revenue = orders
        .filter((order) => ["reserved", "picked_up"].includes(order.status))
        .reduce((sum, order) => sum + (order.discounted_price || 0), 0);

      summaryLine.textContent = `الإجمالي: ${total} | المباعة: ${sold} | الإيراد: ${formatMoney(
        revenue
      )} ل.س`;
    };

    const renderBags = (bags) => {
      bagsView.innerHTML = "";
      if (!bags.length) {
        bagsView.innerHTML = "<div class='empty'>لا توجد أكياس اليوم.</div>";
        return;
      }

      bags.forEach((bag, index) => {
        const card = document.createElement("article");
        card.className = "card";
        card.style.animationDelay = `${index * 0.03}s`;
        card.innerHTML = `
          <div class="card-body">
            <div class="title">${bag.emoji} ${escapeHtml(bag.type)}</div>
            <div class="meta">💸 ${formatMoney(bag.discounted_price)} ل.س</div>
            <div class="meta">🕒 ${escapeHtml(bag.pickup_start)} - ${escapeHtml(
          bag.pickup_end
        )}</div>
            <div class="meta"><span class="badge">متبقي ${bag.remaining}</span></div>
            <div class="actions">
              <button class="btn ghost" data-action="edit-qty" data-id="${
                bag.bag_id
              }">تعديل الكمية</button>
              <button class="btn ghost" data-action="edit-price" data-id="${
                bag.bag_id
              }">تعديل السعر</button>
              <button class="btn warn" data-action="deactivate" data-id="${
                bag.bag_id
              }">إيقاف</button>
            </div>
          </div>
        `;
        bagsView.appendChild(card);
      });
    };

    const renderOrders = (orders) => {
      ordersView.innerHTML = "";
      if (!orders.length) {
        ordersView.innerHTML = "<div class='empty'>لا توجد طلبات اليوم.</div>";
        return;
      }

      orders.forEach((order, index) => {
        const card = document.createElement("article");
        card.className = "card";
        card.style.animationDelay = `${index * 0.03}s`;
        card.innerHTML = `
          <div class="card-body">
            <div class="title">${escapeHtml(order.order_code)}</div>
            <div class="meta">${order.status_emoji} ${escapeHtml(
          order.status_label
        )}</div>
            <div class="meta">${escapeHtml(order.customer_name)} • ${escapeHtml(
          order.customer_phone
        )}</div>
            <div class="meta">🕒 ${escapeHtml(
          order.pickup_start
        )} - ${escapeHtml(order.pickup_end)}</div>
            <div class="actions">
              <button class="btn primary" data-action="pickup" data-id="${
                order.order_id
              }">تم الاستلام</button>
              <button class="btn warn" data-action="cancel" data-id="${
                order.order_id
              }">إلغاء</button>
            </div>
          </div>
        `;
        ordersView.appendChild(card);
      });
    };

    const loadData = async () => {
      statusLine.textContent = "جارٍ تحميل لوحة المطعم...";
      const [bagsRes, ordersRes] = await Promise.all([
        apiFetch(`/api/restaurant_bags?user_id=${userId}`),
        apiFetch(`/api/restaurant_orders?user_id=${userId}`),
      ]);

      const bagsData = await bagsRes.json();
      const ordersData = await ordersRes.json();

      if (!bagsData.success || !ordersData.success) {
        statusLine.textContent = "تعذر تحميل البيانات. تأكد من صلاحياتك.";
        return;
      }

      statusLine.textContent = `مرحباً ${bagsData.restaurant.name || ""}`;
      renderBags(bagsData.bags || []);
      renderOrders(ordersData.orders || []);
      renderSummary(bagsData.bags || [], ordersData.orders || []);
    };

    bagsView.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      const bagId = event.target.dataset.id;
      if (!action || !bagId) return;

      if (action === "edit-qty") {
        openModal("أدخل الكمية الجديدة", "", async (value) => {
          await apiFetch("/api/bag/edit", {
            method: "POST",
            body: JSON.stringify({
              user_id: userId,
              bag_id: bagId,
              field: "qty",
              value,
            }),
          });
          await loadData();
        });
      }

      if (action === "edit-price") {
        openModal("أدخل السعر الجديد", "", async (value) => {
          await apiFetch("/api/bag/edit", {
            method: "POST",
            body: JSON.stringify({
              user_id: userId,
              bag_id: bagId,
              field: "price",
              value,
            }),
          });
          await loadData();
        });
      }

      if (action === "deactivate") {
        apiFetch("/api/bag/deactivate", {
          method: "POST",
          body: JSON.stringify({ user_id: userId, bag_id: bagId }),
        }).then(loadData);
      }
    });

    ordersView.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      const orderId = event.target.dataset.id;
      if (!action || !orderId) return;

      if (action === "pickup") {
        apiFetch("/api/order/pickup", {
          method: "POST",
          body: JSON.stringify({ user_id: userId, order_id: orderId }),
        }).then(loadData);
      }

      if (action === "cancel") {
        apiFetch("/api/order/cancel", {
          method: "POST",
          body: JSON.stringify({ user_id: userId, order_id: orderId }),
        }).then(loadData);
      }
    });

    bindNav((tab) => switchTab(tab));
    refreshBtn.addEventListener("click", async () => {
      await loadData();
      showToast("تم تحديث البيانات", "success");
    });

    loadData();
  };

  if (page === "customer") {
    initCustomer();
  }

  if (page === "restaurant") {
    initRestaurant();
  }
})();
