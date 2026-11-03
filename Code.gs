/**
 * =========================================================================
 * Code.gs — NORDELIA 2026  |  Backend Spreadsheet Pendaftaran
 * SMA Ignatius Global School (IGS) Palembang — Kabinet Orvélion 2026–2027
 * =========================================================================
 *
 * APA YANG DILAKUKAN:
 *  - Menerima POST dari website Flask (/api/nordelia/register)
 *  - Menulis 1 baris ke tab "Master Pendaftaran"
 *  - Menulis 1 baris ke tab cabang lomba (1 lomba = 1 sheet)
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
 *  6. Salin Web app URL, tempel di file .env website:
 *
 *       GOOGLE_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/XXXX/exec
 *       NORDELIA_SPREADSHEET_ID=<ID spreadsheet dari URL /d/ID/edit>
 *       NORDELIA_SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/<ID>/edit
 *
 *  7. Restart Flask. Pendaftaran baru akan masuk ke spreadsheet.
 *  8. Tes: buka Web app URL di browser (GET) harus balas {"status":"ok",...}
 */

const COLOR_PINK = "#FFB7C5";
const COLOR_CREAM = "#FFE5B4";
const COLOR_BLUE = "#AEC6CF";
const COLOR_HEADER = "#2D2622";

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

const DAFTAR_CABANG_LOMBA = [
  { name: "Literasi Numerasi", color: COLOR_BLUE },
  { name: "Literasi Bahasa Indonesia", color: COLOR_PINK },
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
  { name: "OPSI", color: COLOR_BLUE },
  { name: "FIKSI", color: COLOR_BLUE },
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
  { name: "Kaligrafi Bahasa Arab", color: COLOR_CREAM },
  { name: "Menyanyi Bahasa Mandarin", color: COLOR_CREAM },
  { name: "Cosplay", color: COLOR_CREAM },
  { name: "Baca Puisi", color: COLOR_CREAM },
  { name: "Cipta Puisi", color: COLOR_CREAM },
  { name: "Jurnalistik", color: COLOR_CREAM },
  { name: "Menulis Cerpen", color: COLOR_CREAM },
  { name: "Monolog", color: COLOR_CREAM },
  { name: "Cipta Lagu", color: COLOR_CREAM },
  { name: "Desain Poster", color: COLOR_CREAM },
  { name: "Fotografi", color: COLOR_CREAM },
  { name: "Instrumen Solo Gitar", color: COLOR_CREAM },
  { name: "Menyanyi Solo Putri", color: COLOR_CREAM },
  { name: "Menyanyi Solo Putra", color: COLOR_CREAM },
  { name: "Kriya", color: COLOR_CREAM },
  { name: "Komik Digital", color: COLOR_CREAM },
  { name: "Film Pendek", color: COLOR_CREAM },
  { name: "Silat", color: COLOR_PINK },
  { name: "Atletik", color: COLOR_PINK },
  { name: "Basket", color: COLOR_PINK },
  { name: "Futsal", color: COLOR_PINK },
  { name: "Voli", color: COLOR_PINK },
  { name: "Catur", color: COLOR_PINK }
];

const SKIP_DETAIL_KEYS = {
  cabang_id: true,
  cabang_name: true,
  category_id: true,
  nama_lengkap: true,
  nama_tim: true,
  nama: true,
  kelas: true,
  whatsapp: true,
  target_sheet: true,
  action: true,
  spreadsheet_id: true,
  timestamp: true
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
    var targetSheetName = cleanSheetTitle(data.target_sheet || cabang || "Lomba");
    var nama = data.nama || data.participant_name || data.nama_lengkap || data.nama_tim || "-";
    var kelas = data.kelas || "-";
    var kontak = data.kontak || data.whatsapp || "-";
    var detailStr = formatDetail_(data.detail);
    var status = "Terverifikasi Web";

    var rowData = [timestamp, category, cabang, nama, kelas, kontak, detailStr, status];

    var masterSheet = findSheetCaseInsensitive(ss, "Master Pendaftaran");
    if (!masterSheet) {
      masterSheet = initOrFormatSheet(ss, "Master Pendaftaran", "#FFFFFF", "SEMUA PENDAFTARAN MASUK");
    }
    masterSheet.appendRow(rowData);

    var cabangSheet = findSheetCaseInsensitive(ss, targetSheetName);
    if (!cabangSheet) {
      cabangSheet = initOrFormatSheet(
        ss,
        targetSheetName,
        colorForCategory_(category),
        "PENDAFTARAN: " + targetSheetName.toUpperCase()
      );
    }
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

  if (setup === "1" || action === "setup") {
    var msg = setupNordeliaSpreadsheet();
    return jsonOut_({
      status: "success",
      message: msg,
      total_sheets: ss.getSheets().length
    });
  }

  return jsonOut_({
    status: "ok",
    app: "Nordelia Webhook Backend",
    spreadsheet: ss.getName(),
    total_sheets: ss.getSheets().length,
    hint: "Tambah ?setup=1 pada URL ini untuk membuat semua tab cabang lomba."
  });
}
