/*!
 * Orvelion PJAX — navigasi antarhalaman tanpa reload penuh.
 *
 * Prinsip kerja (progressive enhancement):
 * - Klik tautan internal dihalau, halaman diambil via fetch(), lalu isi <body>
 *   diganti dengan hasil render server yang sama persis (tampilan tidak berubah).
 * - Skrip inline pada konten baru dieksekusi ulang sesuai urutan dokumen,
 *   kemudian event DOMContentLoaded disintesis dan inisialisasi app.js
 *   dipanggil terakhir — meniru urutan eksekusi muatan halaman normal.
 * - Hover/fokus pada tautan memicu prefetch agar klik terasa instan.
 * - Jika apa pun gagal (jaringan, redirect, non-HTML), otomatis fallback ke
 *   navigasi penuh sehingga situs tetap berfungsi 100% tanpa PJAX.
 */
(function () {
  "use strict";

  var FETCH_TIMEOUT_MS = 10000;   // batas waktu fetch sebelum fallback reload
  var PREFETCH_TTL_MS = 15000;    // usia maksimum hasil prefetch (menjaga kesegaran kuota)
  var PREFETCH_MAX = 10;          // jumlah maksimum halaman ter-prefetch
  var HOVER_DELAY_MS = 80;        // jeda hover sebelum prefetch dimulai

  /* Transisi: fade-out → fade-in murni pada <main> saja (~300 ms total).   */
  /* Header tidak ikut memudar; DOM diganti & scroll terjadi saat layar     */
  /* sedang gelap sehingga tidak ada kedipan. Menghormati                   */
  /* prefers-reduced-motion: pergantian menjadi instan.                     */
  var REDUCED_MOTION = !!(window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var PROGRESS_DELAY_MS = 180;    // progress bar hanya muncul bila fetch > 180 ms

  var prefetchStore = new Map();  // url -> { html: string, at: number }
  var scrollMap = new Map();      // url -> posisi scroll vertikal
  var activeController = null;    // AbortController fetch yang sedang berjalan
  var swapCount = 0;
  var currentPagePath = window.location.pathname + window.location.search;

  /* ------------------------------------------------------------------ */
  /* Utilitas                                                            */
  /* ------------------------------------------------------------------ */

  function toURL(str) {
    try {
      return new URL(str, window.location.href);
    } catch (e) {
      return null;
    }
  }

  function sameOrigin(u) {
    return u && u.origin === window.location.origin;
  }

  /* Tautan yang boleh dinavigasi via PJAX */
  function eligibleURL(u) {
    if (!u || !sameOrigin(u)) return false;
    if (u.protocol !== "http:" && u.protocol !== "https:") return false;
    var p = u.pathname;
    if (p.indexOf("/api/") === 0) return false;
    if (p.indexOf("/waiting-room") === 0) return false; // halaman antrean wajib reload penuh
    if (p.indexOf("/static/") === 0) return false;
    var lastSeg = p.substring(p.lastIndexOf("/") + 1);
    if (lastSeg.indexOf(".") !== -1) return false; // file ber-ekstensi (aset/unduhan)
    return true;
  }

  function findAnchor(el) {
    while (el && el !== document.body) {
      if (el instanceof HTMLAnchorElement) return el;
      el = el.parentElement;
    }
    return null;
  }

  function linkAllowed(a, ev) {
    if (ev && ev.defaultPrevented) return false;
    if (ev && ev.button !== 0) return false;
    if (ev && (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey)) return false;
    if (a.hasAttribute("download")) return false;
    var target = a.getAttribute("target");
    if (target && target !== "_self") return false;
    var rel = (a.getAttribute("rel") || "").toLowerCase();
    if (rel.indexOf("external") !== -1) return false;
    var href = a.getAttribute("href");
    if (!href) return false;
    var hrefLow = href.toLowerCase();
    if (href.charAt(0) === "#") return false;
    if (hrefLow.indexOf("javascript:") === 0) return false;
    if (hrefLow.indexOf("mailto:") === 0) return false;
    if (hrefLow.indexOf("tel:") === 0) return false;
    var u = toURL(a.href);
    if (!u || !eligibleURL(u)) return false;
    /* Halaman sama persis (hanya berbeda hash) → biarkan browser scroll */
    if (u.pathname === window.location.pathname && u.search === window.location.search) return false;
    return true;
  }

  /* Daftar skrip eksternal yang sudah termuat (pathname) */
  function loadedScriptPaths() {
    var paths = [];
    var scripts = document.querySelectorAll("script[src]");
    for (var i = 0; i < scripts.length; i++) {
      var u = toURL(scripts[i].getAttribute("src"));
      if (u) paths.push(u.pathname);
    }
    return paths;
  }

  function isJSMime(el) {
    var t = (el.getAttribute("type") || "").toLowerCase();
    return t === "" || t === "text/javascript" || t === "application/javascript" || t === "module";
  }

  /* ------------------------------------------------------------------ */
  /* Fetch                                                               */
  /* ------------------------------------------------------------------ */

  function fetchHTML(url) {
    return new Promise(function (resolve, reject) {
      var ctl = new AbortController();
      activeController = ctl;
      var timer = setTimeout(function () { ctl.abort(); }, FETCH_TIMEOUT_MS);

      fetch(url, {
        headers: { "X-Orvelion-PJAX": "1" },
        credentials: "same-origin",
        cache: "no-store",
        redirect: "follow",
        signal: ctl.signal
      }).then(function (resp) {
        clearTimeout(timer);
        if (ctl.signal.aborted) return reject("aborted");
        activeController = null;
        /* Redirect (mis. kapasitas penuh → waiting-room) : navigasi penuh */
        if (resp.redirected) {
          window.location.href = resp.url;
          return reject("redirected");
        }
        var ct = (resp.headers.get("content-type") || "").toLowerCase();
        if (ct.indexOf("text/html") === -1) {
          window.location.href = url;
          return reject("non-html");
        }
        return resp.text().then(resolve, reject);
      }).catch(function (err) {
        clearTimeout(timer);
        if (ctl.signal.aborted && activeController !== ctl) return reject("aborted");
        activeController = null;
        /* Kegagalan jaringan → fallback reload penuh agar selalu sampai tujuan */
        window.location.href = url;
        reject(err);
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Prefetch saat hover / sentuh                                        */
  /* ------------------------------------------------------------------ */

  function prefetch(urlStr) {
    if (prefetchStore.has(urlStr)) return;
    if (prefetchStore.size >= PREFETCH_MAX) {
      prefetchStore.delete(prefetchStore.keys().next().value);
    }
    var entry = { html: null, at: Date.now() };
    prefetchStore.set(urlStr, entry);

    fetch(urlStr, {
      headers: { "X-Orvelion-PJAX": "1" },
      credentials: "same-origin",
      cache: "no-store"
    }).then(function (r) {
      if (r.redirected) { prefetchStore.delete(urlStr); return null; }
      var ct = (r.headers.get("content-type") || "").toLowerCase();
      if (ct.indexOf("text/html") === -1) { prefetchStore.delete(urlStr); return null; }
      return r.text();
    }).then(function (html) {
      if (html == null) return;
      var e = prefetchStore.get(urlStr);
      if (e) e.html = html;
    }).catch(function () {
      prefetchStore.delete(urlStr);
    });
  }

  function getCachedHTML(urlStr) {
    var e = prefetchStore.get(urlStr);
    if (!e || !e.html) return null;
    if (Date.now() - e.at > PREFETCH_TTL_MS) {
      prefetchStore.delete(urlStr);
      return null;
    }
    return e.html;
  }

  /* ------------------------------------------------------------------ */
  /* Swap dokumen                                                        */
  /* ------------------------------------------------------------------ */

  function instantScrollTo(y) {
    var html = document.documentElement;
    var prev = html.style.scrollBehavior;
    html.style.scrollBehavior = "auto";
    window.scrollTo(0, y);
    html.style.scrollBehavior = prev;
  }

  function executeInlineScripts(scope, loadedPaths) {
    var scripts = scope.querySelectorAll("script");
    for (var i = 0; i < scripts.length; i++) {
      var s = scripts[i];
      if (s.src) {
        var u = toURL(s.getAttribute("src"));
        if (u && loadedPaths.indexOf(u.pathname) !== -1) continue; // sudah termuat
        /* Skrip eksternal baru di dalam konten: muat ulang secara sinkron-berurut */
        var ext = document.createElement("script");
        for (var ai = 0; ai < s.attributes.length; ai++) {
          ext.setAttribute(s.attributes[ai].name, s.attributes[ai].value);
        }
        ext.removeAttribute("async");
        s.parentNode.replaceChild(ext, s);
      } else if (isJSMime(s)) {
        /* Skrip inline: ganti dengan salinan baru agar dieksekusi */
        var ns = document.createElement("script");
        for (var aj = 0; aj < s.attributes.length; aj++) {
          ns.setAttribute(s.attributes[aj].name, s.attributes[aj].value);
        }
        ns.textContent = s.textContent;
        s.parentNode.replaceChild(ns, s);
      }
      /* type="application/json" dan sejenisnya: data, tidak dieksekusi */
    }
  }

  function swapDocument(html, urlStr) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var u = toURL(urlStr);

    /* 1. Judul & meta head */
    if (doc.title) document.title = doc.title;
    ["description", "theme-color"].forEach(function (name) {
      var newMeta = doc.querySelector('meta[name="' + name + '"]');
      var oldMeta = document.querySelector('meta[name="' + name + '"]');
      if (newMeta && oldMeta) oldMeta.setAttribute("content", newMeta.getAttribute("content") || "");
    });

    /* 2. Lepas fokus dari elemen lama sebelum diganti */
    if (document.activeElement && document.activeElement !== document.body) {
      try { document.activeElement.blur(); } catch (e) { /* abaikan */ }
    }

    /* 3. Inisialisasi app.js disingkirkan sementara dari event
          DOMContentLoaded agar urutan eksekusi bisa dikendalikan:
          skrip inline dulu, lalu app.js — sama seperti muatan normal. */
    var appInit = window.OrvelionInit;
    if (typeof appInit === "function") {
      document.removeEventListener("DOMContentLoaded", appInit);
    }

    /* 4. Ganti isi <body> kecuali node persisten:
          - svg ikon (identik di semua halaman, tidak perlu diganti)
          - skrip app.js & pjax.js (sudah termuat, jangan dieksekusi ulang) */
    var loadedPaths = loadedScriptPaths();
    var oldIcons = document.body.querySelector(":scope > svg.hidden");

    /* Kumpulkan node lama yang harus tetap ada */
    Array.prototype.slice.call(document.body.children).forEach(function (child) {
      if (child === oldIcons) return;
      if (child.tagName === "SCRIPT" && child.src) {
        var cu = toURL(child.getAttribute("src"));
        if (cu && loadedPaths.indexOf(cu.pathname) !== -1) return; // pertahankan
      }
      document.body.removeChild(child);
    });

    /* Sisipkan node baru, lewati svg ikon & skrip yang sudah termuat */
    var newIcons = doc.body.querySelector(":scope > svg.hidden");
    Array.prototype.slice.call(doc.body.children).forEach(function (child) {
      if (child === newIcons) return; // pakai svg ikon lama
      if (child.tagName === "SCRIPT" && child.src) {
        var nu = toURL(child.getAttribute("src"));
        if (nu && loadedPaths.indexOf(nu.pathname) !== -1) return; // jangan muat ulang
      }
      document.body.appendChild(document.adoptNode(child));
    });

    /* 5. Eksekusi skrip inline baru sesuai urutan dokumen */
    executeInlineScripts(document.body, loadedPaths);

    /* 6. Sintesis DOMContentLoaded → menjalankan listener yang
          didaftarkan skrip inline (seperti saat muatan normal) */
    document.dispatchEvent(new Event("DOMContentLoaded"));

    /* 7. Inisialisasi app.js dipanggil paling akhir (urutan normal) */
    if (typeof appInit === "function") {
      appInit();
    }

    swapCount++;
    if (u) currentPagePath = u.pathname + u.search;

    /* 8. Posisi scroll */
    if (u && u.hash) {
      var anchor = document.getElementById(decodeURIComponent(u.hash.slice(1)));
      if (anchor) {
        anchor.scrollIntoView();
        return;
      }
    }
    instantScrollTo(0);
  }

  /* ------------------------------------------------------------------ */
  /* Transisi & progress bar                                            */
  /* ------------------------------------------------------------------ */

  /* Transisi fade murni TANPA View Transitions API. VT memotret halaman
     lama & baru lalu crossfade — lompatan scroll (kembali ke atas) dan
     resize address bar di mobile membuat snapshot meloncat sehingga
     terlihat kedipan / "kelap-kelip". Cara yang stabil dan sederhana:
       1) <main> lama memudar cepat (120 ms) — header tetap diam;
       2) DOM diganti + scroll ke posisi tujuan saat layar sedang gelap;
       3) <main> baru muncul dari transparan (180 ms).
     Total ~300 ms: cepat tapi terasa halus, tidak mengganggu.
     prefers-reduced-motion / tab tersembunyi: pergantian instan. */
  var FADE_OUT_MS = 120;
  var FADE_IN_MS = 180;
  var fadeGen = 0; /* generasi navigasi: klik baru membatalkan animasi lama */

  function swapSmooth(html, urlStr, onDone) {
    var gen = ++fadeGen;

    if (REDUCED_MOTION || document.hidden) {
      swapDocument(html, urlStr);
      if (onDone) onDone();
      return;
    }

    /* Tahap 1: konten lama memudar. Kelas enter dilepas dulu agar animasi
       fade-in yang mungkin masih berjalan tidak mengalahkan opacity. */
    var oldMain = document.querySelector("main");
    var phase1 = Promise.resolve();
    if (oldMain) {
      oldMain.classList.remove("orv-pjax-enter");
      oldMain.classList.add("orv-pjax-exit");
      phase1 = new Promise(function (resolve) {
        setTimeout(resolve, FADE_OUT_MS + 30);
      });
    }

    phase1.then(function () {
      if (gen !== fadeGen) return; /* navigasi lain mengambil alih — batal */

      /* Tahap 2: ganti dokumen saat layar sudah gelap */
      swapDocument(html, urlStr);
      if (onDone) onDone();

      /* Tahap 3: konten baru muncul. Kelas dipasang sinkron pada task yang
         sama dengan swap → frame pertamanya sudah transparan, tidak ada
         kedip sebelum fade-in dimulai. */
      var newMain = document.querySelector("main");
      if (!newMain) return;
      newMain.classList.add("orv-pjax-enter");
      setTimeout(function () {
        if (gen !== fadeGen) return;
        newMain.classList.remove("orv-pjax-enter");
      }, FADE_IN_MS + 40);
    });
  }

  /* Progress bar tipis di tepi atas — hanya terlihat ketika navigasi
     terasa lambat (>180 ms). Warna koral tema Orvelion. */
  var progressBar = null;
  var progressTimer = null;

  function showProgressBar() {
    if (progressBar) return;
    progressBar = document.createElement("div");
    progressBar.className = "orv-pjax-progress";
    document.body.appendChild(progressBar);
    /* paksa reflow agar transisi width terpicu */
    void progressBar.offsetWidth;
    progressBar.classList.add("orv-pjax-progress-active");
  }

  function startProgressTimer() {
    if (!progressTimer) {
      progressTimer = setTimeout(showProgressBar, PROGRESS_DELAY_MS);
    }
  }

  function finishProgressBar() {
    if (progressTimer) {
      clearTimeout(progressTimer);
      progressTimer = null;
    }
    if (!progressBar) return;
    var bar = progressBar;
    progressBar = null;
    bar.classList.add("orv-pjax-progress-done");
    setTimeout(function () {
      if (bar.parentNode) bar.parentNode.removeChild(bar);
    }, 350);
  }

  /* ------------------------------------------------------------------ */
  /* Navigasi                                                            */
  /* ------------------------------------------------------------------ */

  function navigate(urlStr, push) {
    if (activeController) {
      try { activeController.abort(); } catch (e) { /* abaikan */ }
    }

    /* Simpan posisi scroll halaman saat ini untuk tombol back */
    scrollMap.set(window.location.href, window.scrollY);

    var cached = getCachedHTML(urlStr);
    if (cached) {
      if (push) history.pushState({ pjax: true }, "", urlStr);
      swapSmooth(cached, urlStr);
      return;
    }

    startProgressTimer();
    fetchHTML(urlStr).then(function (html) {
      if (push) history.pushState({ pjax: true }, "", urlStr);
      swapSmooth(html, urlStr);
      finishProgressBar();
    }).catch(function () {
      finishProgressBar();
      /* fallback reload penuh sudah ditangani di fetchHTML */
    });
  }

  /* ------------------------------------------------------------------ */
  /* Event global (delegasi)                                             */
  /* ------------------------------------------------------------------ */

  document.addEventListener("click", function (ev) {
    var a = findAnchor(ev.target);
    if (!a) return;
    if (!linkAllowed(a, ev)) return;
    ev.preventDefault();
    navigate(a.href, true);
  });

  var hoverTimer = null;
  document.addEventListener("pointerover", function (ev) {
    var a = findAnchor(ev.target);
    if (!a || !linkAllowed(a, null)) return;
    clearTimeout(hoverTimer);
    var href = a.href;
    hoverTimer = setTimeout(function () { prefetch(href); }, HOVER_DELAY_MS);
  }, { passive: true });

  document.addEventListener("pointerout", function () {
    clearTimeout(hoverTimer);
  }, { passive: true });

  /* Sentuhan: prefetch langsung saat jari menyentuh tautan */
  document.addEventListener("pointerdown", function (ev) {
    var a = findAnchor(ev.target);
    if (!a || !linkAllowed(a, null)) return;
    prefetch(a.href);
  }, { passive: true });

  window.addEventListener("popstate", function () {
    var u = toURL(window.location.href);

    /* Navigasi hash pada dokumen yang sama (mis. klik tautan #footer)
       juga memicu popstate — biarkan browser menangani scroll native. */
    if (u && u.pathname + u.search === currentPagePath) {
      return;
    }

    if (!eligibleURL(u)) {
      window.location.reload();
      return;
    }
    var saved = scrollMap.get(window.location.href) || 0;
    if (activeController) {
      try { activeController.abort(); } catch (e) { /* abaikan */ }
    }
    var cached = getCachedHTML(window.location.href);
    if (cached) {
      swapSmooth(cached, window.location.href, function () {
        instantScrollTo(saved);
      });
      return;
    }
    startProgressTimer();
    fetchHTML(window.location.href).then(function (html) {
      swapSmooth(html, window.location.href, function () {
        instantScrollTo(saved);
      });
      finishProgressBar();
    }).catch(function () { finishProgressBar(); /* fallback reload penuh */ });
  });

  /* API kecil untuk debugging / pengujian */
  window.OrvelionPJAX = {
    version: "1.2",
    get swaps() { return swapCount; },
    eligible: function (urlStr) { return eligibleURL(toURL(urlStr)); }
  };
})();
