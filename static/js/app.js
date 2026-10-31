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
          `<div class="p-3 rounded-xl bg-[#1c1714]/80 border border-[rgba(253,140,90,0.15)] flex items-start gap-2.5 text-xs text-[#fdb18f]/85"><span class="w-1.5 h-1.5 rounded-full bg-[#FD8C5A] mt-1.5 shrink-0"></span><span>${item}</span></div>`
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

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initTabs();
  initScrollTop();
  initCountdown();
  initEvents();
  initCabinets();
  initWaitingRoom();
});
