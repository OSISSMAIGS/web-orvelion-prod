const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function initNav() {
  const header = $("#site-header");
  const toggle = $("#nav-toggle");
  const drawer = $("#nav-drawer");
  if (!header) return;

  window.addEventListener("scroll", () => {
    header.classList.toggle("is-scrolled", window.scrollY > 20);
  });

  toggle?.addEventListener("click", () => {
    drawer?.classList.toggle("hidden");
  });

  $$("[data-close-nav]").forEach((el) => {
    el.addEventListener("click", () => drawer?.classList.add("hidden"));
  });
}

function initTabs() {
  $$("[data-tab-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.getAttribute("data-tab-target");
      $$("[data-tab-target]").forEach((b) => b.classList.toggle("is-active", b === btn));
      $$("[data-tab-panel]").forEach((panel) => {
        panel.classList.toggle("hidden", panel.getAttribute("data-tab-panel") !== name);
      });
    });
  });
}

function initScrollTop() {
  $("#scroll-top")?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

function initCountdown() {
  const root = $("#countdown");
  if (!root) return;
  const target = new Date("2026-11-14T08:00:00+07:00").getTime();
  const tick = () => {
    const diff = Math.max(0, target - Date.now());
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    root.querySelector("[data-days]").textContent = String(days);
    root.querySelector("[data-hours]").textContent = String(hours).padStart(2, "0");
    root.querySelector("[data-minutes]").textContent = String(minutes).padStart(2, "0");
    root.querySelector("[data-seconds]").textContent = String(seconds).padStart(2, "0");
  };
  tick();
  setInterval(tick, 1000);
}

function initEvents() {
  const grid = $("#event-grid");
  if (!grid) return;

  const cards = $$("[data-event-card]", grid);
  const empty = $("#event-empty");
  const search = $("#event-search");
  const modal = $("#event-modal");
  const events = JSON.parse($("#events-data").textContent);

  const applyFilter = () => {
    const cat = $("[data-category].is-active")?.getAttribute("data-category") || "Semua";
    const q = (search?.value || "").toLowerCase().trim();
    let shown = 0;
    cards.forEach((card) => {
      const matchCat = cat === "Semua" || card.dataset.category === cat;
      const hay = `${card.dataset.title} ${card.dataset.desc} ${card.dataset.location}`.toLowerCase();
      const matchQ = !q || hay.includes(q);
      const ok = matchCat && matchQ;
      card.classList.toggle("hidden", !ok);
      if (ok) shown += 1;
    });
    empty?.classList.toggle("hidden", shown !== 0);
  };

  $$("[data-category]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("[data-category]").forEach((b) => b.classList.toggle("is-active", b === btn));
      applyFilter();
    });
  });
  search?.addEventListener("input", applyFilter);

  const fillModal = (event) => {
    $("#modal-kicker").textContent = `${event.category} • ${event.status}`;
    $("#modal-title").textContent = event.title;
    $("#modal-date").textContent = event.date;
    $("#modal-time").textContent = event.time;
    $("#modal-location").textContent = event.location;
    $("#modal-desc").textContent = event.description;
    $("#modal-highlight").textContent = event.highlight;
    $("#modal-success").classList.add("hidden");
    $("#modal-actions").classList.remove("hidden");
    modal.classList.remove("hidden");
    modal.dataset.eventId = event.id;
  };

  $$("[data-open-event]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const event = events.find((item) => item.id === btn.getAttribute("data-open-event"));
      if (event) fillModal(event);
    });
  });

  $$("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => modal.classList.add("hidden"));
  });

  $("#modal-register")?.addEventListener("click", () => {
    $("#modal-success").classList.remove("hidden");
    $("#modal-actions").classList.add("hidden");
  });
}

function initCabinets() {
  const spotlight = $("#cabinet-spotlight");
  if (!spotlight) return;
  const cabinets = JSON.parse($("#cabinets-data").textContent);

  const render = (cab) => {
    $("#cab-image").src = `/static/images/${cab.image}`;
    $("#cab-image").alt = cab.name;
    $("#cab-period").textContent = `Emblem Resmi • ${cab.period}`;
    $("#cab-symbol").textContent = cab.symbol;
    $("#cab-name").textContent = cab.name;
    $("#cab-tagline").textContent = cab.tagline;
    $("#cab-philosophy").textContent = cab.philosophy;
    $("#cab-legacy").textContent = cab.keyLegacy;
    const list = $("#cab-achievements");
    list.innerHTML = cab.achievements
      .map(
        (item) =>
          `<div class="relative"><div class="absolute -left-4 top-1.5 w-3 h-3 rounded-full bg-[#FD8C5A] border-2 border-[#161210]"></div><div class="p-3 rounded-xl bg-[#1c1714]/80 border border-[rgba(253,140,90,0.15)] text-xs text-[#fdb18f]/85">${item}</div></div>`
      )
      .join("");
    $$("[data-cabinet]").forEach((btn) => {
      btn.classList.toggle("is-selected", btn.getAttribute("data-cabinet") === cab.id);
    });
  };

  $$("[data-cabinet]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cab = cabinets.find((item) => item.id === btn.getAttribute("data-cabinet"));
      if (cab) render(cab);
    });
  });
}

function initWaitingRoom() {
  const root = $("#waiting-room");
  if (!root) return;
  const returnUrl = root.dataset.returnUrl || "/";
  const countEl = $("#queue-count");
  const bar = $("#queue-bar");
  const countdown = $("#queue-countdown");
  const status = $("#queue-status");
  let left = 3;

  const check = async () => {
    status.textContent = "Memeriksa slot...";
    try {
      const res = await fetch("/api/queue-status", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        countEl.textContent = `${data.activeCount} / ${data.maxAllowed} Slot`;
        bar.style.width = `${Math.min(100, (data.activeCount / data.maxAllowed) * 100)}%`;
        if (data.allowed) {
          window.location.href = returnUrl;
          return;
        }
      }
    } catch (_err) {
      /* keep waiting */
    }
    status.textContent = "Siaga";
  };

  setInterval(() => {
    left -= 1;
    if (left <= 0) {
      left = 3;
      check();
    }
    countdown.textContent = `${left}s`;
  }, 1000);

  $("#try-access")?.addEventListener("click", () => {
    window.location.href = returnUrl;
  });
}

function initNordelia() {
  console.log("initNordelia called");
  console.log("Current URL:", window.location.href);
  console.log("Checking for nordelia-data-cabang element...");

  const cabangDataEl = document.getElementById("nordelia-data-cabang");
  const formatDataEl = document.getElementById("nordelia-data-formats");

  console.log("cabangDataEl:", cabangDataEl);
  console.log("formatDataEl:", formatDataEl);

  if (!cabangDataEl || !formatDataEl) {
    console.log("Nordelia data elements not found - not on Nordelia page");
    return;
  }

  console.log("=== NORDelia PAGE SCRIPT START ===");

  let cabangList, formatList;
  try {
    cabangList = JSON.parse(cabangDataEl.textContent);
    formatList = JSON.parse(formatDataEl.textContent);
  } catch (e) {
    console.error("Gagal parse JSON:", e);
    return;
  }

  console.log("Data loaded:", {
    cabangCount: cabangList.length,
    formatKeys: Object.keys(formatList),
    sampleCabang: cabangList.slice(0, 3),
  });

  const cabangCards = Array.from(document.querySelectorAll("[data-cabang-card]"));
  const emptyNotice = document.getElementById("cabang-empty");
  const searchInput = document.getElementById("cabang-search");
  const currentCategoryName = document.getElementById("current-category-name");

  // Filter logic
  let activeCategory = "semua";
  function applyFilter() {
    const q = (searchInput?.value || "").toLowerCase().trim();
    let visibleCount = 0;

    cabangCards.forEach(function (card) {
      const matchCat = activeCategory === "semua" || card.dataset.category === activeCategory;
      const haystack = (card.dataset.name + " " + card.dataset.pic + " " + card.dataset.tempat + " " + card.dataset.category).toLowerCase();
      const matchQ = !q || haystack.includes(q);
      const isVisible = matchCat && matchQ;

      card.classList.toggle("hidden", !isVisible);
      if (isVisible) visibleCount++;
    });

    if (emptyNotice) {
      emptyNotice.classList.toggle("hidden", visibleCount > 0);
    }
  }

  // Category Buttons click handler
  document.querySelectorAll("[data-category-select]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const catId = btn.getAttribute("data-category-select");
      const hasSub = btn.getAttribute("data-has-sub") === "true";

      if (hasSub) {
        window.location.href = "/nordelia/" + catId;
      } else {
        // Cabang tanpa sub-events (Literasi Numerasi, Science, Bahasa Indonesia, AI) langsung mengarah ke formulir pendaftaran
        openRegisterModal(catId);
      }
    });
  });

  // Filter pills handler
  document.querySelectorAll(".cat-pill").forEach(function (pill) {
    pill.addEventListener("click", function () {
      const cat = pill.getAttribute("data-filter-cat");
      activeCategory = cat;

      document.querySelectorAll(".cat-pill").forEach(function (p) {
        p.className = "cat-pill px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap bg-stone-900/80 text-stone-300 hover:text-white border border-white/10";
      });
      pill.className = "cat-pill is-active px-4 py-2 rounded-xl text-xs font-extrabold whitespace-nowrap bg-gradient-to-r from-[#FFB7C5] to-[#FFE5B4] text-black";

      if (currentCategoryName) {
        currentCategoryName.textContent = cat === "semua" ? "Semua Kategori" : cat.toUpperCase();
      }

      applyFilter();
    });
  });

  searchInput?.addEventListener("input", applyFilter);

  // MODAL REGISTER & DYNAMIC FIELDS
  const modalReg = document.getElementById("modal-register");
  const closeRegBtn = document.getElementById("btn-close-register-modal");
  const formCabangTitle = document.getElementById("form-cabang-title");
  const formBadgeCategory = document.getElementById("form-badge-category");
  const formRuleBox = document.getElementById("form-rule-box");
  const inputCabangId = document.getElementById("input-cabang-id");
  const inputCategoryId = document.getElementById("input-category-id");
  const dynamicFormFields = document.getElementById("dynamic-form-fields");
  const formAlert = document.getElementById("form-alert");
  const regForm = document.getElementById("nordelia-reg-form");

  console.log("Modal elements:", {
    modalReg: !!modalReg,
    closeRegBtn: !!closeRegBtn,
    formCabangTitle: !!formCabangTitle,
    formBadgeCategory: !!formBadgeCategory,
    formRuleBox: !!formRuleBox,
    inputCabangId: !!inputCabangId,
    dynamicFormFields: !!dynamicFormFields,
    formAlert: !!formAlert,
    regForm: !!regForm,
  });

  function openRegisterModal(cabangId) {
    console.log("openRegisterModal dipanggil dengan cabangId:", cabangId);
    let c = cabangList.find(item => item.id === cabangId);
    if (!c) {
      c = cabangList.find(item => 
        (cabangId.includes("ai") && (item.id.includes("ai") || item.name.toLowerCase().includes("artifisial"))) ||
        item.name.toLowerCase().includes(cabangId.toLowerCase())
      );
    }
    console.log("Cabang ditemukan:", c ? c.name : "tidak ditemukan");
    if (!c) {
      console.error("Cabang tidak ditemukan untuk ID:", cabangId);
      return;
    }

    inputCabangId.value = c.id;
    if (inputCategoryId) inputCategoryId.value = c.category || "akademik";
    formCabangTitle.textContent = c.name;
    formBadgeCategory.textContent = (c.category ? c.category.toUpperCase() : "LOMBA") + (c.no ? " • NO. " + c.no : "");
    
    const isOlimp = !!(c.is_olimpiade_or_ai || c.id === "olimpiade-ai" || c.id.includes("olimpiade") || (c.name && c.name.toLowerCase().includes("artifisial")));
    const isLit = !!(c.is_literasi || (c.name && c.name.toLowerCase().startsWith("literasi")) || (c.id && c.id.startsWith("literasi")));
    const regCount = (typeof c.registered_count === "number") ? c.registered_count : 0;
    
    let quotaDisplay = "";
    if (isOlimp) {
      const rem = (typeof c.remaining_quota === "number") ? c.remaining_quota : Math.max(0, 20 - regCount);
      const isFull = rem <= 0 || !!c.is_full;
      quotaDisplay = `<span class="${isFull ? 'text-rose-400' : 'text-amber-300'} font-bold">${isFull ? 'Kuota Penuh (20/20)' : 'Sisa ' + rem + ' dari 20 Kuota'}</span>`;
    } else {
      quotaDisplay = `<span class="text-emerald-400 font-bold">Kuota Terbuka</span>`;
    }

    let minMaxDisplay = "";
    if (isOlimp) {
      minMaxDisplay = `<span class="text-amber-300 font-bold">Min: 5/Kelas • Maks: 20</span>`;
    } else if (isLit) {
      minMaxDisplay = `<span class="text-[#FFE5B4] font-bold">Min: 2/Kelas</span>`;
    }

    formRuleBox.innerHTML = `
      <div class="flex items-center justify-between mb-1">
        <span class="text-stone-400">Lokasi: ${c.tempat || '-'}</span>
        ${minMaxDisplay}
      </div>
      <div class="flex items-center justify-between py-1 my-1 border-t border-b border-white/10 text-[11px]">
        <span class="text-stone-300">Terdaftar: <strong class="text-white">${regCount} Orang</strong></span>
        ${quotaDisplay}
      </div>
      <p class="text-[11px] text-stone-300"><strong class="text-white">Ketentuan:</strong> ${c.note || '-'}</p>
    `;

    // Dynamic field generation based on format_type
    const fmtKey = c.format_type || "olimpiade_akademik";
    const fmt = formatList[fmtKey] || formatList["olimpiade_akademik"];

    let html = "";
    fmt.fields.forEach(field => {
      if (field.type === "textarea") {
        html += `
          <div>
            <label class="block text-xs font-bold text-stone-200 mb-1">${field.label} ${field.required ? '<span class="text-rose-400">*</span>' : ''}</label>
            <textarea name="${field.name}" ${field.required ? 'required' : ''} placeholder="${field.placeholder}" rows="3"
                      class="w-full px-3.5 py-2.5 rounded-xl bg-stone-900 border border-white/20 text-xs text-white placeholder-stone-500 focus:outline-none focus:border-[#FFE5B4]"></textarea>
          </div>
        `;
      } else {
        html += `
          <div>
            <label class="block text-xs font-bold text-stone-200 mb-1">${field.label} ${field.required ? '<span class="text-rose-400">*</span>' : ''}</label>
            <input type="${field.type}" name="${field.name}" ${field.required ? 'required' : ''} placeholder="${field.placeholder}"
                   class="w-full px-3.5 py-2.5 rounded-xl bg-stone-900 border border-white/20 text-xs text-white placeholder-stone-500 focus:outline-none focus:border-[#FFE5B4]" />
          </div>
        `;
      }
    });

    dynamicFormFields.innerHTML = html;
    formAlert.classList.add("hidden");
    modalReg.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    console.log("Modal pendaftaran berhasil dibuka");
  }

  function closeRegisterModal() {
    modalReg.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  const registerButtons = document.querySelectorAll("[data-register-cabang]");
  console.log("Tombol daftar ditemukan:", registerButtons.length);

  if (registerButtons.length === 0) {
    console.warn("Tidak ada tombol daftar yang ditemukan dengan attribute data-register-cabang");
  } else {
    console.log("Detail tombol daftar:", Array.from(registerButtons).map(btn => ({
      cabangId: btn.getAttribute("data-register-cabang"),
      text: btn.textContent.trim(),
    })));
  }

  registerButtons.forEach((btn, index) => {
    console.log(`Event listener dipasang pada tombol ${index + 1} dengan cabangId:`, btn.getAttribute("data-register-cabang"));
    btn.addEventListener("click", (e) => {
      console.log("=== CLICK EVENT TRIGGERED ===");
      e.preventDefault();
      e.stopPropagation();
      const cabangId = btn.getAttribute("data-register-cabang");
      console.log("Tombol daftar diklik untuk cabang:", cabangId);
      console.log("cabangList tersedia:", cabangList ? cabangList.length : "tidak ada");
      openRegisterModal(cabangId);
    });
  });

  closeRegBtn?.addEventListener("click", closeRegisterModal);
  modalReg?.addEventListener("click", (e) => {
    if (e.target === modalReg) closeRegisterModal();
  });

  // Handle Form Submission
  regForm?.addEventListener("submit", async function (e) {
    e.preventDefault();
    const btnSubmit = document.getElementById("btn-submit-registration");
    const originalText = btnSubmit.innerHTML;

    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `
      <svg class="w-4 h-4 animate-spin text-black" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle><path fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
      <span>Memproses Pendaftaran...</span>
    `;

    try {
      const formData = new FormData(regForm);
      const payload = {};
      formData.forEach((val, key) => { payload[key] = val; });

      const res = await fetch("/api/nordelia/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.success) {
        closeRegisterModal();
        regForm.reset();
        if (typeof window.showNordeliaRegisteredPopup === "function") {
          window.showNordeliaRegisteredPopup({
            participantName: data.participant_name || payload.nama_lengkap || payload.nama_tim || payload.nama,
            cabangName: data.cabang_name,
            groupLink: data.group_link,
            groupLabel: data.group_label,
          });
        } else {
          window.location.reload();
        }

      } else {
        formAlert.className = "p-3 rounded-xl mb-4 text-xs font-bold bg-rose-950/80 text-rose-300 border border-rose-500/40";
        formAlert.textContent = data.error || "Gagal memproses pendaftaran. Silakan coba lagi.";
        formAlert.classList.remove("hidden");
      }
    } catch (err) {
      formAlert.className = "p-3 rounded-xl mb-4 text-xs font-bold bg-rose-950/80 text-rose-300 border border-rose-500/40";
      formAlert.textContent = "Terjadi kesalahan jaringan: " + err.message;
      formAlert.classList.remove("hidden");
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = originalText;
    }
  });

  console.log("=== NORDelia PAGE SCRIPT END ===");
}

console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOMContentLoaded fired in app.js");
  initNav();
  initTabs();
  initScrollTop();
  initCountdown();
  initEvents();
  initCabinets();
  initWaitingRoom();
  initNordelia();
});
