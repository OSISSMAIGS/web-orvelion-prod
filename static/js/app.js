const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function initNav() {
  const header = $("#site-header");
  const toggle = $("#nav-toggle");
  const drawer = $("#nav-drawer");
  if (!header) return;

  // Listener scroll hanya didaftarkan sekali (aman terhadap re-init oleh PJAX)
  if (!window.__orvNavScrollBound) {
    window.__orvNavScrollBound = true;
    window.addEventListener("scroll", () => {
      const h = $("#site-header");
      if (h) h.classList.toggle("is-scrolled", window.scrollY > 20);
    });
  }

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

let countdownTimer = null;

function initCountdown() {
  const root = $("#countdown");
  if (!root) return;
  const target = new Date("2026-11-14T08:00:00+07:00").getTime();
  const tick = () => {
    if (!root.isConnected) {
      // Halaman sudah diganti (PJAX): hentikan interval lama
      if (countdownTimer) clearInterval(countdownTimer);
      countdownTimer = null;
      return;
    }
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
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(tick, 1000);
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
    const legacyEl = $("#cab-legacy");
    if (legacyEl) legacyEl.textContent = cab.keyLegacy;
    const websiteWrap = $("#cab-website-wrap");
    const websiteLink = $("#cab-website");
    if (websiteWrap && websiteLink) {
      if (cab.website) {
        websiteLink.href = cab.website;
        websiteWrap.classList.remove("hidden");
      } else {
        websiteWrap.classList.add("hidden");
      }
    }
    const list = $("#cab-achievements");
    if (list && cab.achievements) {
      list.innerHTML = cab.achievements
      .map(
        (item) =>
          `<div class="relative"><div class="absolute -left-4 top-1.5 w-3 h-3 rounded-full bg-[#FD8C5A] border-2 border-[#161210]"></div><div class="p-3 rounded-xl bg-[#1c1714]/80 border border-[rgba(253,140,90,0.15)] text-xs text-[#fdb18f]/85">${item}</div></div>`
      )
      .join("");
    }
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
  const cabangDataEl = document.getElementById("nordelia-data-cabang");
  const formatDataEl = document.getElementById("nordelia-data-formats");
  const ketentuanDataEl = document.getElementById("nordelia-data-ketentuan");
  let ketentuanData = {};
  try {
    ketentuanData = JSON.parse(ketentuanDataEl ? ketentuanDataEl.textContent : "{}");
  } catch(e) {
    console.error("Gagal parse ketentuan data:", e);
  }

  if (!cabangDataEl || !formatDataEl) {
    return;
  }

  let cabangList, formatList;
  try {
    cabangList = JSON.parse(cabangDataEl.textContent);
    formatList = JSON.parse(formatDataEl.textContent);
  } catch (e) {
    console.error("Gagal parse JSON:", e);
    return;
  }

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

  // Modal OSN Jurusan Elements & Handler
  const modalOsn = document.getElementById("modal-osn-jurusan");
  const closeOsnBtn = document.getElementById("btn-close-osn-modal");
  const cancelOsnBtn = document.getElementById("btn-cancel-osn-modal");

  function closeOsnModal() {
    modalOsn?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  closeOsnBtn?.addEventListener("click", closeOsnModal);
  cancelOsnBtn?.addEventListener("click", closeOsnModal);
  modalOsn?.addEventListener("click", (e) => {
    if (e.target === modalOsn) closeOsnModal();
  });

  // Category Buttons click handler
  document.querySelectorAll("[data-category-select]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const catId = btn.getAttribute("data-category-select");
      const hasSub = btn.getAttribute("data-has-sub") === "true";

      // Khusus OSN: Arahkan terlebih dahulu ke pemilihan jurusan IPA/IPS
      if (catId === "osn" || catId === "olimpiade-9-cabang") {
        if (modalOsn) {
          modalOsn.classList.remove("hidden");
          document.body.classList.add("overflow-hidden");
          return;
        }
      }

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
      pill.className = "cat-pill is-active px-4 py-2 rounded-xl text-xs font-extrabold whitespace-nowrap bg-gradient-to-r from-[#FDE68A] via-[#F5D061] to-[#E5B869] text-[#0B1120] font-black";

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


  function openRegisterModal(cabangId) {
    let c = cabangList.find(item => item.id === cabangId);
    if (!c) {
      c = cabangList.find(item => 
        ((cabangId === "ai" || cabangId === "olimpiade-ai") && (item.id.includes("ai") || item.name.toLowerCase().includes("artifisial"))) ||
        ((cabangId === "cosplay" || cabangId === "cosplay-jepang") && (item.id.includes("cosplay") || item.name.toLowerCase().includes("cosplay"))) ||
        item.name.toLowerCase().includes(cabangId.toLowerCase())
      );
    }

    if (c && c.is_external_gform && c.gform_url) {
      window.open(c.gform_url, "_blank");
      return;
    }
    if (!c) {
      console.error("Cabang tidak ditemukan untuk ID:", cabangId);
      return;
    }

    inputCabangId.value = c.id;
    if (inputCategoryId) inputCategoryId.value = c.category || "akademik";
    formCabangTitle.textContent = c.name;
    formBadgeCategory.textContent = (c.category ? c.category.toUpperCase() : "LOMBA");
    
    const isOlimp = !c.id.includes("bahasa") && !(c.category && c.category === "bahasa") && !c.id.includes("desain") && !c.id.includes("poster") && !!(c.is_olimpiade_or_ai || c.id === "olimpiade-ai" || (c.id.includes("olimpiade") && !c.id.includes("bahasa")) || (c.name && c.name.toLowerCase().includes("artifisial")));
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
      minMaxDisplay = `<span class="text-amber-300 font-bold">Maks. 20 Peserta</span>`;
    }

    const isTeam = !!(c.is_team || c.isTeam);
    const unitText = isTeam ? "Tim" : "Orang";
    const labelText = isTeam ? "Tim Terdaftar:" : "Terdaftar:";

    formRuleBox.innerHTML = `
      <div class="flex items-center justify-between mb-1">
        <span class="text-stone-400">Lokasi: ${c.tempat || '-'}</span>
        ${minMaxDisplay}
      </div>
      <div class="flex items-center justify-between py-1 my-1 border-t border-b border-white/10 text-[11px]">
        <span class="text-stone-300">${labelText} <strong class="text-white" id="modal-live-reg-count">${regCount} ${unitText}</strong></span>
        <span id="modal-live-quota-wrapper">${quotaDisplay}</span>
      </div>
    `;

    const hasKetentuan = !!(ketentuanData && (ketentuanData[c.id] || (c.id === 'ai' && ketentuanData['olimpiade-ai']) || (c.id.includes('ai') && ketentuanData['olimpiade-ai'])));
    const juknisUrl = c.juknis_url || ((c.id === 'ai' || c.id === 'olimpiade-ai') ? 'https://drive.google.com/drive/folders/1QjuO7vX9MhtvZt92LAbHpCFfwKd3IPGF?usp=drive_link' : '');
    if (juknisUrl) {
      formRuleBox.innerHTML += `
        <div class="mt-2.5 pt-2 border-t border-white/10">
          <a href="${juknisUrl}" target="_blank" rel="noopener noreferrer" class="w-full py-2.5 px-3 rounded-xl text-xs font-bold text-[#FDE68A] bg-white/[0.06] hover:bg-white/[0.12] border border-[#F5D061]/35 hover:border-[#F5D061]/70 transition-all flex items-center justify-center gap-2 shadow-sm hover:scale-[1.01]">
            <svg class="w-4 h-4 text-[#F5D061]"><use href="#i-sparkles"></use></svg>
            <span>Lihat Ketentuan & Juknis Lengkap</span>
          </a>
        </div>
      `;
    } else if (hasKetentuan) {
      formRuleBox.innerHTML += `
        <div class="mt-2.5 pt-2 border-t border-white/10">
          <button type="button" id="btn-open-juknis-from-reg" class="w-full py-2.5 px-3 rounded-xl text-xs font-bold text-[#FDE68A] bg-white/[0.06] hover:bg-white/[0.12] border border-[#F5D061]/35 hover:border-[#F5D061]/70 transition-all flex items-center justify-center gap-2 shadow-sm hover:scale-[1.01]">
            <svg class="w-4 h-4 text-[#F5D061]"><use href="#i-sparkles"></use></svg>
            <span>Lihat Ketentuan & Juknis Lengkap</span>
          </button>
        </div>
      `;
      setTimeout(() => {
        const btnJuknis = document.getElementById("btn-open-juknis-from-reg");
        if (btnJuknis) {
          btnJuknis.onclick = () => {
            closeRegisterModal();
            openKetentuanModal(c.id, c.name);
          };
        }
      }, 10);
    }

    // Ambil live count & kuota langsung dari Google Sheet via API
    fetch(`/api/nordelia/cabang-quota?cabang_id=${encodeURIComponent(c.id)}`)
      .then((res) => res.json())
      .then((live) => {
        if (!live || typeof live.count !== "number") return;
        const regEl = document.getElementById("modal-live-reg-count");
        const liveIsTeam = (typeof live.is_team !== "undefined") ? !!live.is_team : isTeam;
        const liveUnit = liveIsTeam ? "Tim" : "Orang";
        if (regEl) regEl.textContent = `${live.count} ${liveUnit}`;
        const qWrap = document.getElementById("modal-live-quota-wrapper");
        if (qWrap) {
          if (live.is_limited) {
            const isFull = live.is_full;
            const rem = live.remaining_quota != null ? live.remaining_quota : Math.max(0, 20 - live.count);
            qWrap.innerHTML = `<span class="${isFull ? 'text-rose-400' : 'text-[#FF7A00]'} font-bold">${isFull ? 'Kuota Penuh (20/20)' : 'Sisa ' + rem + ' dari 20 Kuota'}</span>`;
          } else {
            qWrap.innerHTML = `<span class="text-white font-bold">Kuota Terbuka</span>`;
          }
        }
        if (live.is_full) {
          const btnSubmit = document.getElementById("btn-submit-registration");
          if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.classList.add("opacity-50", "cursor-not-allowed");
            btnSubmit.innerHTML = `<span><strong>Kuota Penuh (20/20)</strong></span>`;
          }
        }
      })
      .catch((err) => console.warn("Live sheet quota check:", err));

    // Dynamic field generation based on format_type
    const fmtKey = c.format_type || "olimpiade_akademik";
    const fmt = formatList[fmtKey] || formatList["olimpiade_akademik"];

    let html = "";
    fmt.fields.forEach(field => {
      if (field.type === "select") {
        const opts = (field.options || []).map(o => `<option value="${o}" class="bg-stone-900 text-white">${o}</option>`).join("");
        html += `
          <div>
            <label class="block text-xs font-bold text-stone-200 mb-1">${field.label} ${field.required ? '<span class="text-rose-400">*</span>' : ''}</label>
            <select name="${field.name}" ${field.required ? 'required' : ''}
                    class="w-full px-3.5 py-2.5 rounded-xl bg-stone-900 border border-white/20 text-xs text-white focus:outline-none focus:border-[#38BDF8]">
              <option value="" disabled selected class="text-stone-500">${field.placeholder || '-- Pilih --'}</option>
              ${opts}
            </select>
          </div>
        `;
      } else if (field.type === "textarea") {
        html += `
          <div>
            <label class="block text-xs font-bold text-stone-200 mb-1">${field.label} ${field.required ? '<span class="text-rose-400">*</span>' : ''}</label>
            <textarea name="${field.name}" ${field.required ? 'required' : ''} placeholder="${field.placeholder}" rows="3"
                      class="w-full px-3.5 py-2.5 rounded-xl bg-stone-900 border border-white/20 text-xs text-white placeholder-stone-500 focus:outline-none focus:border-[#38BDF8]"></textarea>
          </div>
        `;
      } else {
        html += `
          <div>
            <label class="block text-xs font-bold text-stone-200 mb-1">${field.label} ${field.required ? '<span class="text-rose-400">*</span>' : ''}</label>
            <input type="${field.type}" name="${field.name}" ${field.required ? 'required' : ''} placeholder="${field.placeholder}"
                   class="w-full px-3.5 py-2.5 rounded-xl bg-stone-900 border border-white/20 text-xs text-white placeholder-stone-500 focus:outline-none focus:border-[#38BDF8]" />
          </div>
        `;
      }
    });

    dynamicFormFields.innerHTML = html;
    formAlert.classList.add("hidden");
    modalReg.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
  }

  function closeRegisterModal() {
    modalReg.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  // =========================================================================
  // OSN PEMINATAN JURUSAN LOGIC (IPA vs IPS)
  // =========================================================================
  const OSN_IPA_ONLY_IDS = [
    "olimpiade-fisika",
    "olimpiade-kimia",
    "olimpiade-biologi",
    "olimpiade-astronomi",
    "olimpiade-informatika"
  ];
  const OSN_IPS_ALLOWED_IDS = [
    "olimpiade-matematika",
    "olimpiade-kebumian",
    "olimpiade-geografi",
    "olimpiade-ekonomi"
  ];
  const OSN_ALL_IDS = [...OSN_IPA_ONLY_IDS, ...OSN_IPS_ALLOWED_IDS];

  let currentJurusan = null; // 'ipa', 'ips', or null
  try {
    currentJurusan = sessionStorage.getItem("nordelia_jurusan") || null;
  } catch (e) {}

  const urlParams = new URLSearchParams(window.location.search);
  const paramJurusan = urlParams.get("jurusan");
  if (paramJurusan && (paramJurusan === "ipa" || paramJurusan === "ips")) {
    currentJurusan = paramJurusan;
    try { sessionStorage.setItem("nordelia_jurusan", currentJurusan); } catch (e) {}
  }

  const badgeJurusan = document.getElementById("active-jurusan-badge");
  const jurusanFilterBtns = document.querySelectorAll("[data-jurusan-filter]");

  function updateJurusanUI() {
    if (badgeJurusan) {
      if (currentJurusan === "ipa") {
        badgeJurusan.textContent = "🔬 Kelas IPA";
        badgeJurusan.className = "px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/40";
      } else if (currentJurusan === "ips") {
        badgeJurusan.textContent = "📚 Kelas IPS";
        badgeJurusan.className = "px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-[#FBBF24]/20 text-[#FBBF24] border border-[#FBBF24]/40";
      } else {
        badgeJurusan.textContent = "Semua Kelas";
        badgeJurusan.className = "px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-white/10 text-stone-300";
      }
    }

    jurusanFilterBtns.forEach(btn => {
      const val = btn.getAttribute("data-jurusan-filter");
      if ((val === "all" && !currentJurusan) || val === currentJurusan) {
        btn.className = "px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all bg-white/20 border-white/40 text-white shadow-sm";
      } else {
        btn.className = "px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all bg-black/40 border-white/15 text-stone-300 hover:text-white";
      }
    });

    // Dim IPA-only cards if user selected IPS
    document.querySelectorAll("[data-cabang-card]").forEach(card => {
      const isOsn = card.getAttribute("data-is-osn") === "true";
      const osnType = card.getAttribute("data-osn-type");
      if (currentJurusan === "ips" && isOsn && osnType === "ipa-only") {
        card.classList.add("opacity-60", "border-amber-500/30");
      } else {
        card.classList.remove("opacity-60", "border-amber-500/30");
      }
    });
  }

  updateJurusanUI();

  jurusanFilterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const val = btn.getAttribute("data-jurusan-filter");
      if (val === "all") {
        currentJurusan = null;
        try { sessionStorage.removeItem("nordelia_jurusan"); } catch (e) {}
      } else {
        currentJurusan = val;
        try { sessionStorage.setItem("nordelia_jurusan", val); } catch (e) {}
      }
      updateJurusanUI();
    });
  });

  // Modals elements
  const modalIpsBlocked = document.getElementById("modal-ips-blocked");
  const btnCloseIpsBlocked = document.getElementById("btn-close-ips-blocked");
  const btnCloseIpsModalFooter = document.getElementById("btn-close-ips-modal-footer");
  const btnSwitchToIpa = document.getElementById("btn-switch-to-ipa");
  const btnShowIpsCabang = document.getElementById("btn-show-ips-cabang");
  const ipsBlockedCabangName = document.getElementById("ips-blocked-cabang-name");
  const ipsBlockedMessage = document.getElementById("ips-blocked-message");

  const modalConfirmJurusan = document.getElementById("modal-confirm-jurusan");
  const btnCloseConfirmJurusan = document.getElementById("btn-close-confirm-jurusan");
  const btnCancelConfirmJurusan = document.getElementById("btn-cancel-confirm-jurusan");
  const btnChooseIpa = document.getElementById("btn-choose-ipa");
  const btnChooseIps = document.getElementById("btn-choose-ips");
  const confirmJurusanCabangName = document.getElementById("confirm-jurusan-cabang-name");

  let pendingCabangId = null;
  let blockedCabangId = null;

  function showIpsBlockedPopup(cabangId, cabangName) {
    blockedCabangId = cabangId;
    if (ipsBlockedCabangName) ipsBlockedCabangName.textContent = cabangName || "ini";
    if (ipsBlockedMessage) {
      ipsBlockedMessage.innerHTML = `Maaf, <strong>${cabangName || 'Olimpiade ini'}</strong> tidak tersedia untuk kelas IPS. Siswa kelas IPS hanya diperbolehkan mendaftar cabang Matematika, Kebumian, Geografi, dan Ekonomi.`;
    }
    modalIpsBlocked?.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
  }

  function closeIpsBlockedPopup() {
    modalIpsBlocked?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  btnCloseIpsBlocked?.addEventListener("click", closeIpsBlockedPopup);
  btnCloseIpsModalFooter?.addEventListener("click", closeIpsBlockedPopup);
  modalIpsBlocked?.addEventListener("click", (e) => {
    if (e.target === modalIpsBlocked) closeIpsBlockedPopup();
  });

  btnSwitchToIpa?.addEventListener("click", () => {
    currentJurusan = "ipa";
    try { sessionStorage.setItem("nordelia_jurusan", "ipa"); } catch (e) {}
    updateJurusanUI();
    closeIpsBlockedPopup();
    if (blockedCabangId) {
      openRegisterModal(blockedCabangId);
      blockedCabangId = null;
    }
  });

  btnShowIpsCabang?.addEventListener("click", () => {
    closeIpsBlockedPopup();
    currentJurusan = "ips";
    try { sessionStorage.setItem("nordelia_jurusan", "ips"); } catch (e) {}
    updateJurusanUI();

    const grid = document.getElementById("cabang-grid");
    if (grid) {
      grid.scrollIntoView({ behavior: "smooth", block: "start" });
      OSN_IPS_ALLOWED_IDS.forEach(id => {
        const card = document.querySelector(`[data-cabang-id="${id}"]`);
        if (card) {
          card.classList.add("ring-2", "ring-[#38BDF8]", "scale-[1.02]");
          setTimeout(() => {
            card.classList.remove("ring-2", "ring-[#38BDF8]", "scale-[1.02]");
          }, 2500);
        }
      });
    } else {
      window.location.href = "/nordelia/osn?jurusan=ips";
    }
  });

  function showConfirmJurusanModal(cabangId, cabangName) {
    pendingCabangId = cabangId;
    if (confirmJurusanCabangName) confirmJurusanCabangName.textContent = cabangName || "OSN";
    modalConfirmJurusan?.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
  }

  function closeConfirmJurusanModal() {
    modalConfirmJurusan?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
    pendingCabangId = null;
  }

  btnCloseConfirmJurusan?.addEventListener("click", closeConfirmJurusanModal);
  btnCancelConfirmJurusan?.addEventListener("click", closeConfirmJurusanModal);
  modalConfirmJurusan?.addEventListener("click", (e) => {
    if (e.target === modalConfirmJurusan) closeConfirmJurusanModal();
  });

  btnChooseIpa?.addEventListener("click", () => {
    currentJurusan = "ipa";
    try { sessionStorage.setItem("nordelia_jurusan", "ipa"); } catch (e) {}
    updateJurusanUI();
    const targetId = pendingCabangId;
    closeConfirmJurusanModal();
    if (targetId) {
      openRegisterModal(targetId);
    }
  });

  btnChooseIps?.addEventListener("click", () => {
    currentJurusan = "ips";
    try { sessionStorage.setItem("nordelia_jurusan", "ips"); } catch (e) {}
    updateJurusanUI();
    const targetId = pendingCabangId;
    closeConfirmJurusanModal();

    if (targetId && OSN_IPA_ONLY_IDS.includes(targetId)) {
      const cObj = cabangList.find(x => x.id === targetId);
      showIpsBlockedPopup(targetId, cObj ? cObj.name : "Olimpiade");
    } else if (targetId) {
      openRegisterModal(targetId);
    }
  });

  // Listeners for blocked buttons on subpages (e.g. /nordelia/osn)
  document.querySelectorAll("[data-blocked-jurusan-btn]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const subId = btn.getAttribute("data-blocked-jurusan-btn");
      const subName = btn.getAttribute("data-blocked-sub-name") || "Olimpiade";
      showIpsBlockedPopup(subId, subName);
    });
  });

  const registerButtons = document.querySelectorAll("[data-register-cabang]");

  if (registerButtons.length === 0) {
    console.warn("Tidak ada tombol daftar yang ditemukan dengan attribute data-register-cabang");
  }

  registerButtons.forEach((btn, index) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const cabangId = btn.getAttribute("data-register-cabang");
      
      const cObj = cabangList.find(x => x.id === cabangId) || {};
      const cabangName = cObj.name || "Cabang Lomba";

      // Khusus cabang OSN: Validasi Peminatan IPA/IPS
      const isOsnBranch = OSN_ALL_IDS.includes(cabangId);
      if (isOsnBranch) {
        if (currentJurusan === "ips") {
          if (OSN_IPA_ONLY_IDS.includes(cabangId)) {
            showIpsBlockedPopup(cabangId, cabangName);
            return;
          }
        } else if (!currentJurusan) {
          showConfirmJurusanModal(cabangId, cabangName);
          return;
        }
      }

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

  // =========================================================================
  // MODAL KETENTUAN LOMBA HANDLER
  // =========================================================================
  const modalKetentuan = document.getElementById("modal-ketentuan");
  const closeKetentuanBtn = document.getElementById("btn-close-ketentuan-modal");
  const closeKetentuanFooterBtn = document.getElementById("btn-close-ketentuan-footer");
  const ketentuanTitle = document.getElementById("ketentuan-modal-title");
  const ketentuanCategoryBadge = document.getElementById("ketentuan-category-badge");
  const ketentuanMetaBox = document.getElementById("ketentuan-meta-box");
  const ketentuanSections = document.getElementById("ketentuan-sections-container");
  const ketentuanGformBtn = document.getElementById("ketentuan-modal-gform-btn");

  function openKetentuanModal(cabangId, fallbackName) {
    if (!modalKetentuan) return;
    const k = (ketentuanData && ketentuanData[cabangId]) || (ketentuanData && (cabangId.includes('ai') ? ketentuanData['olimpiade-ai'] : null));
    const cb = (cabangList || []).find(c => c.id === cabangId || (cabangId.includes('ai') && c.id.includes('ai')));
    if (!k) {
      if (cb) {
        if (ketentuanTitle) ketentuanTitle.textContent = "Ketentuan " + (cb.name || fallbackName);
        if (ketentuanCategoryBadge) ketentuanCategoryBadge.textContent = cb.category ? cb.category.toUpperCase() : "LOMBA";
        if (ketentuanMetaBox) {
          ketentuanMetaBox.innerHTML = `
            <div class="text-xs text-stone-300">
              <strong>Lokasi:</strong> ${cb.tempat || '-'}<br>
              <strong>PIC:</strong> ${cb.pic || '-'}
            </div>
          `;
        }
        if (ketentuanSections) {
          ketentuanSections.innerHTML = "";
        }
        const juknisBtn = document.getElementById("ketentuan-modal-juknis-btn");
        if (juknisBtn) {
          if (cb.juknis_url) {
            juknisBtn.href = cb.juknis_url;
            juknisBtn.classList.remove("hidden");
          } else {
            juknisBtn.classList.add("hidden");
          }
        }
        modalKetentuan.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
      }
      return;
    }

    if (ketentuanTitle) ketentuanTitle.textContent = k.title || ("Ketentuan " + (cb ? cb.name : fallbackName));
    if (ketentuanCategoryBadge) ketentuanCategoryBadge.textContent = k.category || "LOMBA";

    let metaHtml = `
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        ${k.tema ? `<div><span class="text-stone-400">Tema:</span> <strong class="text-[#FDE68A]">${k.tema}</strong></div>` : ''}
        ${k.biaya ? `<div><span class="text-stone-400">Biaya:</span> <strong class="text-emerald-400">${k.biaya}</strong></div>` : ''}
        ${k.deadline ? `<div><span class="text-stone-400">Jadwal:</span> <strong class="text-stone-200">${k.deadline}</strong></div>` : ''}
        ${k.durasi ? `<div><span class="text-stone-400">Durasi:</span> <strong class="text-sky-300">${k.durasi}</strong></div>` : ''}
      </div>
      ${k.contact_person ? `
        <div class="mt-3 pt-2 border-t border-white/10 flex items-center justify-between text-xs">
          <span class="text-stone-400">Narahubung: <strong class="text-stone-200">${k.contact_person.name}</strong></span>
          ${k.contact_person.wa_url ? `<a href="${k.contact_person.wa_url}" target="_blank" class="px-2.5 py-1 rounded-lg bg-[#06C755]/20 text-[#06C755] border border-[#06C755]/30 font-bold hover:bg-[#06C755]/30">Chat &rarr;</a>` : ''}
        </div>
      ` : ''}
    `;
    if (ketentuanMetaBox) ketentuanMetaBox.innerHTML = metaHtml;

    let secHtml = "";
    (k.sections || []).forEach(sec => {
      secHtml += `
        <div class="p-4 sm:p-5 rounded-2xl bg-white/[0.03] border border-white/10 space-y-2.5">
          <div class="flex items-center justify-between gap-2">
            <h4 class="text-sm font-bold text-white flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-[#F5D061]"></span>
              ${sec.heading}
            </h4>
            ${sec.badge ? `<span class="text-[10px] px-2.5 py-0.5 rounded-full bg-white/10 text-[#FDE68A] font-semibold border border-white/10">${sec.badge}</span>` : ''}
          </div>
          <ul class="space-y-2 pl-1 text-xs text-stone-300">
            ${sec.items.map(item => `
              <li class="flex items-start gap-2.5">
                <span class="text-[#FDE68A] mt-1 shrink-0">✦</span>
                <span class="leading-relaxed">${item}</span>
              </li>
            `).join('')}
          </ul>
        </div>
      `;
    });
    if (ketentuanSections) ketentuanSections.innerHTML = secHtml;

    const hasGform = !!(k.gform_url || (cb && cb.is_external_gform && cb.gform_url));
    const modalEmailNotice = document.getElementById("ketentuan-modal-email-notice");
    const modalInAppRegBtn = document.getElementById("ketentuan-modal-inapp-reg-btn");

    if (ketentuanGformBtn) {
      if (hasGform) {
        ketentuanGformBtn.href = k.gform_url || (cb && cb.gform_url) || "https://forms.google.com";
        ketentuanGformBtn.classList.remove("hidden");
        if (modalEmailNotice) modalEmailNotice.classList.remove("hidden");
        if (modalInAppRegBtn) modalInAppRegBtn.classList.add("hidden");
      } else {
        ketentuanGformBtn.classList.add("hidden");
        if (modalEmailNotice) modalEmailNotice.classList.add("hidden");
        if (modalInAppRegBtn) {
          modalInAppRegBtn.classList.remove("hidden");
          modalInAppRegBtn.onclick = () => {
            closeKetentuanModal();
            openRegisterModal(cb ? cb.id : cabangId, (cb && cb.name) ? cb.name : fallbackName);
          };
        }
      }
    }

    const juknisBtn = document.getElementById("ketentuan-modal-juknis-btn");
    const juknisUrl = k.juknis_url || (cb && cb.juknis_url) || "";
    if (juknisBtn) {
      if (juknisUrl) {
        juknisBtn.href = juknisUrl;
        juknisBtn.classList.remove("hidden");
      } else {
        juknisBtn.classList.add("hidden");
      }
    }

    modalKetentuan.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
  }

  function closeKetentuanModal() {
    modalKetentuan?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  closeKetentuanBtn?.addEventListener("click", closeKetentuanModal);
  closeKetentuanFooterBtn?.addEventListener("click", closeKetentuanModal);
  modalKetentuan?.addEventListener("click", function(e) {
    if (e.target === modalKetentuan) closeKetentuanModal();
  });


  // Expose to window
  window.openRegisterModal = openRegisterModal;
  window.closeRegisterModal = closeRegisterModal;
  window.openKetentuanModal = openKetentuanModal;
  window.closeKetentuanModal = closeKetentuanModal;
  window.ketentuanData = ketentuanData;
  window.cabangList = cabangList;

}

function initAllPages() {
  initNav();
  initTabs();
  initScrollTop();
  initCountdown();
  initEvents();
  initCabinets();
  initWaitingRoom();
  initNordelia();
}

// Diekspos agar PJAX dapat menjalankan ulang inisialisasi halaman
// dengan urutan eksekusi yang sama seperti muatan halaman normal.
window.OrvelionInit = initAllPages;

document.addEventListener("DOMContentLoaded", initAllPages);
