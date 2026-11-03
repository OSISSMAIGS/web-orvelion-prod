/**
 * =========================================================================
 * Code.gs — NORDELIA 2026  |  Backend Spreadsheet Pendaftaran
 * SMA Ignatius Global School (IGS) Palembang — Kabinet Orvélion 2026–2027
 * =========================================================================
 *
 * APA YANG DILAKUKAN:
 *  - Menerima POST dari website Flask (halaman /daftar)
 *  - Menulis 1 baris ke tab "Master Pendaftaran"
 *  - Menulis 1 baris ke tab cabang lomba (1 lomba = 1 sheet), tab tujuan
 *    ditentukan field "target_sheet" dari situs
 *  - MENEGAKKAN KUOTA: 10 cabang Olimpiade (9 sains + Kecerdasan Artifisial)
 *    maksimal 20 peserta — pendaftaran ke-21 ditolak dengan pesan jelas
 *  - Menyajikan hitungan peserta per tab via GET ?counts=1 (dipakai situs
 *    untuk menampilkan sisa kuota di formulir)
 *  - Mencatat field tambahan (cth. jenis_debat LDBI/NSDC) ke kolom DETAIL
 *
 * PASANG (sekali saja):
 *  1. Buka Google Spreadsheet Nordelia
 *  2. Extensions → Apps Script
 *  3. Hapus kode default, tempel SELURUH file ini, Save
 *  4. Di dropdown fungsi pilih setupNordeliaSpreadsheet → Run
 *     (izinkan akses ke spreadsheet saat diminta)
 *  5. Deploy → New deployment → type: Web app
 *       Execute as: Me
 *       Who has access: Anyone
 *  6. Salin Web app URL (diakhiri /exec), tempel di file .env website:
 *       GOOGLE_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/XXXX/exec
 *  7. Restart Flask. Pendaftaran baru akan masuk ke spreadsheet.
 *  8. Tes: buka Web app URL di browser (GET) harus balas {"status":"ok",...}
 *
 * CATATAN PENTING:
 *  - Nama tab di DAFTAR_CABANG_LOMBA HARUS sama dengan nama sheet yang
 *    dikirim situs (lihat "sheet"/"sheet_fmt"/"sheet_map" di
 *    orvelion/nordelia.py). Cek otomatis: python tools/cek-konsistensi.py
 *  - Setelah mengubah kode ini, WAJIB Deploy → Manage deployments →
 *    Edit → Version: New version, agar versi baru yang aktif.
 */

const COLOR_PINK = "#FFB7C5";    // Bahasa & Olahraga
const COLOR_CREAM = "#FFE5B4";   // Seni
const COLOR_BLUE = "#AEC6CF";    // Akademik & Sains
const COLOR_HEADER = "#2D2622";  // Dark Elegant Header

const TABLE_HEADERS = [
  "WAKTU PENDAFTARAN",
  "KATEGORI",
  "CABANG LOMBA",
  "NAMA PESERTA / TIM",
  "KELAS",
  "NO. WHATSAPP / KONTAK",
  "DETAIL TAMBAHAN / FORMAT ISIAN",
  "STATUS"
];

// 43 cabang resmi Nordelia 2026 (1 lomba = 1 sheet).
// Urutan & penamaan selaras orvelion/nordelia.py.
const DAFTAR_CABANG_LOMBA = [
  // AKADEMIK & SAINS
  { name: "Literasi Numerasi", color: COLOR_BLUE },
  { name: "Literasi Bahasa Indonesia", color: COLOR_BLUE },
  { name: "Literasi Science", color: COLOR_BLUE },
  { name: "Olimpiade Matematika", color: COLOR_BLUE },
  { name: "Olimpiade Fisika", color: COLOR_BLUE },
  { name: "Olimpiade Biologi", color: COLOR_BLUE },
  { name: "Olimpiade Kimia", color: COLOR_BLUE },
  { name: "Olimpiade Informatika", color: COLOR_BLUE },
  { name: "Olimpiade Kebumian", color: COLOR_BLUE },
  { name: "Olimpiade Astronomi", color: COLOR_BLUE },
  { name: "Olimpiade Geografi", color: COLOR_BLUE },
  { name: "Olimpiade Ekonomi", color: COLOR_BLUE },
  { name: "Olimpiade Kecerdasan Artifisial", color: COLOR_BLUE },

  // BAHASA & DEBAT
  { name: "LDBI", color: COLOR_PINK },
  { name: "NSDC", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Jerman", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Jepang", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Korea", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Mandarin", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Spanyol", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Prancis", color: COLOR_PINK },
  { name: "Olimpiade Bahasa Arab", color: COLOR_PINK },
  { name: "Story Telling Korea", color: COLOR_PINK },

  // SENI & FLS3N
  { name: "Kaligrafi Bahasa Arab", color: COLOR_CREAM },
  { name: "Menyanyi Bahasa Mandarin", color: COLOR_CREAM },
  { name: "Cosplay", color: COLOR_CREAM },
  { name: "Baca Puisi", color: COLOR_CREAM },
  { name: "Cipta Puisi", color: COLOR_CREAM },
  { name: "Menulis Cerpen", color: COLOR_CREAM },
  { name: "Monolog", color: COLOR_CREAM },
  { name: "Desain Poster", color: COLOR_CREAM },
  { name: "Instrumen Solo Gitar", color: COLOR_CREAM },
  { name: "Menyanyi Solo Putri", color: COLOR_CREAM },
  { name: "Menyanyi Solo Putra", color: COLOR_CREAM },
  { name: "Kriya", color: COLOR_CREAM },
  { name: "Komik Digital", color: COLOR_CREAM },
  { name: "Tari Kreasi", color: COLOR_CREAM },

  // OLAHRAGA & O2SN
  { name: "Silat", color: COLOR_PINK },
  { name: "Atletik", color: COLOR_PINK },
  { name: "Basket", color: COLOR_PINK },
  { name: "Futsal", color: COLOR_PINK },
  { name: "Voli", color: COLOR_PINK },
  { name: "Catur", color: COLOR_PINK }
];

// Kuota resmi: 9 cabang Olimpiade Sains + Kecerdasan Artifisial,
// maksimal 20 peserta per cabang (sesuai sheet "Format Pendaftaran").
const KUOTA_CABANG = {
  "Olimpiade Matematika": 20,
  "Olimpiade Fisika": 20,
  "Olimpiade Biologi": 20,
  "Olimpiade Kimia": 20,
  "Olimpiade Informatika": 20,
  "Olimpiade Kebumian": 20,
  "Olimpiade Astronomi": 20,
  "Olimpiade Geografi": 20,
  "Olimpiade Ekonomi": 20,
  "Olimpiade Kecerdasan Artifisial": 20
};

// Field inti yang TIDAK masuk kolom DETAIL (sudah punya kolom sendiri).
const SKIP_DETAIL_KEYS = {
  cabang_id: true,
  cabang_name: true,
  category_id: true,
  category: true,
  cabang: true,
  nama_lengkap: true,
  nama_tim: true,
  nama: true,
  participant_name: true,
  kelas: true,
  whatsapp: true,
  kontak: true,
  target_sheet: true,
  action: true,
  spreadsheet_id: true,
  timestamp: true,
  detail: true,
  status: true
};

function jsonOut_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function cleanSheetTitle(title) {
  if (!title) return "Lomba";
  var cleaned = title.toString().replace(/[:\\/?*\[\]]/g, "-").trim();
  if (cleaned.length > 50) cleaned = cleaned.substring(0, 50).trim();
  return cleaned || "Lomba";
}

function findSheetCaseInsensitive(ss, targetName) {
  if (!targetName) return null;
  var cleanTarget = cleanSheetTitle(targetName).toLowerCase();
  var sheets = ss.getSheets();
  for (var i = 0; i < sheets.length; i++) {
    if (sheets[i].getName().trim().toLowerCase() === cleanTarget) {
      return sheets[i];
    }
  }
  return null;
}

function colorForCategory_(category) {
  var cat = (category || "").toUpperCase();
  if (cat.indexOf("BAHASA") !== -1) return COLOR_PINK;
  if (cat.indexOf("SENI") !== -1) return COLOR_CREAM;
  if (cat.indexOf("OLAHRAGA") !== -1) return COLOR_PINK;
  return COLOR_BLUE;
}

function initOrFormatSheet(ss, sheetName, tabColor, bannerTitle) {
  var safeName = cleanSheetTitle(sheetName);
  var s = findSheetCaseInsensitive(ss, safeName);
  if (!s) s = ss.insertSheet(safeName);
  s.setTabColor(tabColor || COLOR_BLUE);

  if (s.getLastRow() < 2) {
    s.clear();
    s.getRange("A1:H1").merge()
      .setValue("NORDELIA 2026 — " + (bannerTitle || safeName.toUpperCase()))
      .setBackground(tabColor || COLOR_BLUE)
      .setFontWeight("bold")
      .setFontColor("#1C1518")
      .setHorizontalAlignment("center")
      .setFontSize(12);

    s.getRange("A2:H2").setValues([TABLE_HEADERS])
      .setBackground(COLOR_HEADER)
      .setFontColor("#FFFFFF")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    s.setFrozenRows(2);
    s.setColumnWidths(1, 8, 160);
    s.setColumnWidth(7, 320);
  }
  return s;
}

// Jumlah peserta tercatat di sebuah sheet (baris 1 banner, baris 2 header).
function hitungPeserta_(sheet) {
  var n = sheet.getLastRow() - 2;
  return n > 0 ? n : 0;
}

function formatDetail_(detail) {
  if (detail === null || detail === undefined || detail === "") return "-";
  if (typeof detail === "string") {
    try {
      detail = JSON.parse(detail);
    } catch (e) {
      return detail;
    }
  }
  if (typeof detail !== "object") return String(detail);

  var lines = [];
  var keys = Object.keys(detail);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    if (SKIP_DETAIL_KEYS[key]) continue;
    var val = detail[key];
    if (val === null || val === undefined || val === "") continue;
    if (typeof val === "object") val = JSON.stringify(val);
    lines.push(key + ": " + val);
  }
  return lines.length ? lines.join("\n") : "-";
}

// Field tambahan di luar field inti (cth. jenis_debat) -> teks untuk kolom DETAIL.
function kumpulkanExtras_(data) {
  var lines = [];
  var keys = Object.keys(data);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    if (SKIP_DETAIL_KEYS[key]) continue;
    var val = data[key];
    if (val === null || val === undefined || val === "") continue;
    if (typeof val === "object") val = JSON.stringify(val);
    var label = key.split(/_/).map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(" ");
    lines.push(label + ": " + val);
  }
  return lines.join("\n");
}

function parsePayload_(e) {
  if (!e) return {};
  if (e.postData && e.postData.contents) {
    var raw = e.postData.contents;
    var type = (e.postData.type || "").toLowerCase();
    if (type.indexOf("json") !== -1 || raw.trim().charAt(0) === "{") {
      return JSON.parse(raw);
    }
    if (e.parameter) return e.parameter;
    return { detail: raw };
  }
  return e.parameter || {};
}

function setupNordeliaSpreadsheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var sheetFormat = findSheetCaseInsensitive(ss, "Format Pendaftaran") || ss.insertSheet("Format Pendaftaran");
  sheetFormat.clear();
  sheetFormat.setTabColor(COLOR_PINK);
  sheetFormat.getRange("A1:G1").merge()
    .setValue("PANDUAN & FORMAT RESMI PENDAFTARAN LOMBA NORDELIA 2026")
    .setBackground(COLOR_PINK)
    .setFontWeight("bold")
    .setFontColor("#3B1724")
    .setHorizontalAlignment("center")
    .setFontSize(13);

  var formatRows = [
    ["KATEGORI LOMBA", "FORMAT ISIAN WAJIB", "", "", "CONTOH ISIAN / KETERANGAN", "", ""],
    [
      "OLIMPIADE 9 CABANG + KECERDASAN ARTIFISIAL",
      "1.) NAMA LENGKAP\n2.) KELAS (Cth: 10.1 CGC, 10.2 MAYOR)",
      "", "",
      "Budi Pratama\n10.1 CGC (Maksimal 20 orang per cabang)",
      "", ""
    ],
    [
      "LDBI & NSDC",
      "1.) Nama Tim\n2.) Asal Kelas Tim\n3.) Speaker NSDC\n4.) Pembicara LDBI",
      "", "",
      "Rhetoric Squad IGS\n11.1 MAYOR & 11.2 CGC",
      "", ""
    ],
    [
      "FLS3N VOKAL SOLO PUTRA & PUTRI",
      "1.) Nama & Kategori\n2.) Kelas\n3.) Link karaoke penyisihan\n4.) Link karaoke final",
      "", "",
      "Rahmat Ardhani (Putra)\n11.1 CGC",
      "", ""
    ],
    [
      "KOMIK DIGITAL & DESAIN POSTER",
      "1.) Nama\n2.) Kelas\n3.) Link Karya / Portofolio",
      "", "",
      "Wahyu Satria\n10.3 MAYOR",
      "", ""
    ],
    [
      "OLAHRAGA BEREGU (Basket, Futsal, Voli)",
      "1.) Nama Tim\n2.) Asal Kelas\n3.) Nama anggota + cadangan",
      "", "",
      "Tim Kontingen Kelas 10.2 MAYOR",
      "", ""
    ],
    [
      "OLAHRAGA INDIVIDU (Silat, Atletik, Catur)",
      "1.) Nama\n2.) Kelas\n3.) Nomor Tanding",
      "", "",
      "Siti Aisyah\n11.2 CGC",
      "", ""
    ]
  ];
  sheetFormat.getRange(2, 1, formatRows.length, 7).setValues(formatRows);
  sheetFormat.getRange("A2:G2").setBackground(COLOR_CREAM).setFontWeight("bold").setFontColor("#332412");
  sheetFormat.autoResizeColumns(1, 7);

  initOrFormatSheet(ss, "Master Pendaftaran", "#FFFFFF", "SEMUA PENDAFTARAN MASUK (REKAPITULASI LENGKAP)");

  for (var i = 0; i < DAFTAR_CABANG_LOMBA.length; i++) {
    var c = DAFTAR_CABANG_LOMBA[i];
    initOrFormatSheet(ss, c.name, c.color, "PENDAFTARAN: " + c.name.toUpperCase());
  }

  return "Sheet Nordelia siap. Total tab: " + ss.getSheets().length;
}

function doPost(e) {
  try {
    var data = parsePayload_(e);
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    var timestamp = data.timestamp || Utilities.formatDate(new Date(), "Asia/Jakarta", "yyyy-MM-dd HH:mm:ss");
    var category = (data.category || data.category_id || "").toString().toUpperCase();
    var cabang = (data.cabang || data.cabang_name || "-").toString().trim();
    // Tab tujuan: eksplisit dari situs; fallback jenis debat (LDBI/NSDC),
    // lalu nama cabang (kompatibel format lama tanpa target_sheet).
    var targetSheetName = cleanSheetTitle(
      data.target_sheet || data.jenis_debat || cabang || "Lomba"
    );
    var nama = data.nama || data.participant_name || data.nama_lengkap || data.nama_tim || "-";
    var kelas = data.kelas || "-";
    var kontak = data.kontak || data.whatsapp || "-";

    // Kolom DETAIL: field tambahan (jenis_debat dll.) + objek detail lama.
    var bagian = [];
    var extras = kumpulkanExtras_(data);
    if (extras) bagian.push(extras);
    var detailStr = formatDetail_(data.detail);
    if (detailStr !== "-") bagian.push(detailStr);
    detailStr = bagian.length ? bagian.join("\n") : "-";

    var status = "Terverifikasi Web";
    var rowData = [timestamp, category, cabang, nama, kelas, kontak, detailStr, status];

    var cabangSheet = findSheetCaseInsensitive(ss, targetSheetName);
    if (!cabangSheet) {
      cabangSheet = initOrFormatSheet(
        ss,
        targetSheetName,
        colorForCategory_(category),
        "PENDAFTARAN: " + targetSheetName.toUpperCase()
      );
    }

    // --- Penegakan kuota (sumber kebenaran ada di sini) ---
    var kuota = KUOTA_CABANG[targetSheetName] || 0;
    if (kuota > 0) {
      var terpakai = hitungPeserta_(cabangSheet);
      if (terpakai >= kuota) {
        return jsonOut_({
          status: "error",
          message: "Kuota " + targetSheetName + " sudah penuh (" + kuota + "/" + kuota +
                   " peserta). Pilih cabang lain ya."
        });
      }
    }

    var masterSheet = findSheetCaseInsensitive(ss, "Master Pendaftaran");
    if (!masterSheet) {
      masterSheet = initOrFormatSheet(ss, "Master Pendaftaran", "#FFFFFF", "SEMUA PENDAFTARAN MASUK");
    }
    masterSheet.appendRow(rowData);
    cabangSheet.appendRow(rowData);

    return jsonOut_({
      status: "success",
      message: "Tercatat di Master Pendaftaran dan sheet '" + targetSheetName + "'",
      sheet: targetSheetName,
      timestamp: timestamp
    });
  } catch (err) {
    return jsonOut_({
      status: "error",
      message: err.toString()
    });
  }
}

function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var action = e && e.parameter ? e.parameter.action : "";
  var setup = e && e.parameter ? e.parameter.setup : "";
  var counts = e && e.parameter ? e.parameter.counts : "";

  if (setup === "1" || action === "setup") {
    var msg = setupNordeliaSpreadsheet();
    return jsonOut_({
      status: "success",
      message: msg,
      total_sheets: ss.getSheets().length
    });
  }

  // Hitungan peserta per tab — dipakai situs untuk indikator sisa kuota.
  if (counts === "1" || action === "counts") {
    var hasil = {};
    var sheets = ss.getSheets();
    for (var i = 0; i < sheets.length; i++) {
      var nm = sheets[i].getName().trim().toLowerCase();
      if (nm === "master pendaftaran" || nm === "format pendaftaran") continue;
      hasil[sheets[i].getName()] = hitungPeserta_(sheets[i]);
    }
    return jsonOut_({
      status: "ok",
      counts: hasil,
      quota: KUOTA_CABANG
    });
  }

  return jsonOut_({
    status: "ok",
    app: "Nordelia Webhook Backend",
    spreadsheet: ss.getName(),
    total_sheets: ss.getSheets().length,
    hint: "Tambah ?setup=1 untuk membuat semua tab cabang, ?counts=1 untuk hitungan peserta."
  });
}
