/**
 * =========================================================================
 * GOOGLE APPS SCRIPT: NORDELIA 2026 BACKEND SPREADSHEET RESMI
 * SMA Ignatius Global School (IGS) Palembang - Kabinet Orvelion 2026-2027
 * =========================================================================
 * 
 * SISTEM KERJA SPREADSHEET:
 * 1. Seluruh pendaftaran dari website masuk otomatis secara real-time.
 * 2. Tab 'Master Pendaftaran': Merekapitulasi seluruh pendaftar secara kronologis.
 * 3. Tab Khusus Cabang Lomba: Setiap cabang lomba memiliki lembar kerja (sheet) tersendiri.
 * 4. Tab 'Format Pendaftaran': Berisi panduan format resmi isian data peserta.
 * 
 * PANDUAN PENERAPAN (DEPLOYMENT):
 * 1. Buka Google Spreadsheet pendaftaran Nordelia Anda.
 * 2. Klik menu 'Extensions' (Ekstensi) > 'Apps Script'.
 * 3. Hapus semua kode yang ada di editor, lalu TEMPELKAN (PASTE) seluruh kode ini.
 * 4. Klik ikon 'Save' (Simpan) disket atau tekan Ctrl+S.
 * 5. Klik tombol 'Deploy' (Terapkan) berwarna biru di kanan atas:
 *    - Pilih 'New deployment' (Penerapan baru).
 *    - Klik ikon gerigi (Select type) > pilih 'Web app' (Aplikasi web).
 *    - Description: Masukkan "Nordelia 2026 Webhook".
 *    - Execute as: Pilih "Me (email akun Anda)".
 *    - Who has access: WAJIB pilih "Anyone" (Siapa saja) agar server website bisa mengirim data.
 *    - Klik 'Deploy' (Terapkan) dan berikan izin akses (Authorize access).
 * 6. Salin URL Web App yang muncul (berakhiran /exec) dan ID Spreadsheet Anda,
 *    lalu kirimkan ke chat agar dipasangkan ke server website!
 */

const COLOR_PINK = "#FFB7C5";    // Pink Pastel (Bahasa & Olahraga)
const COLOR_CREAM = "#FFE5B4";   // Oranye / Krem Pastel (Seni)
const COLOR_BLUE = "#AEC6CF";    // Biru Muda Pastel (Akademik & Sains)
const COLOR_GOLD = "#F5D061";    // Gold Nordelia (Cosplay & Khusus)
const COLOR_HEADER = "#1E293B";  // Dark Slate Elegant Header

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

// Daftar Seluruh Cabang Lomba Resmi Nordelia 2026 (1 Lomba = 1 Tab Sheet)
const DAFTAR_CABANG_LOMBA = [
  // AKADEMIK, SAINS & RISET
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

  // COSPLAY (BIDANG MANDIRI)
  { name: "Cosplay", color: COLOR_GOLD },

  // SENI & FLS3N
  { name: "Kaligrafi Bahasa Arab", color: COLOR_CREAM },
  { name: "Menyanyi Bahasa Mandarin", color: COLOR_CREAM },
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
  { name: "Tari Kreasi", color: COLOR_CREAM },

  // OLAHRAGA & O2SN
  { name: "Silat", color: COLOR_PINK },
  { name: "Atletik", color: COLOR_PINK },
  { name: "Basket", color: COLOR_PINK },
  { name: "Futsal", color: COLOR_PINK },
  { name: "Voli", color: COLOR_PINK },
  { name: "Catur", color: COLOR_PINK }
];

/**
 * Jalankan fungsi ini sekali untuk otomatis menata seluruh sheet pendaftaran.
 */
function setupNordeliaSpreadsheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Buat / Siapkan Sheet: Format Pendaftaran
  let sheetFormat = findSheetCaseInsensitive(ss, "Format Pendaftaran") || ss.insertSheet("Format Pendaftaran");
  sheetFormat.clear();
  sheetFormat.setTabColor(COLOR_PINK);
  
  sheetFormat.getRange("A1:G1").merge()
    .setValue("PANDUAN & FORMAT RESMI PENDAFTARAN LOMBA NORDELIA 2026")
    .setBackground(COLOR_PINK)
    .setFontWeight("bold")
    .setFontColor("#3B1724")
    .setHorizontalAlignment("center")
    .setFontSize(13);

  const formatRows = [
    ["KATEGORI LOMBA", "FORMAT ISIAN WAJIB", "", "", "CONTOH ISIAN / KETERANGAN", "", ""],
    [
      "OLIMPIADE MATEMATIKA, FISIKA, BIOLOGI, KIMIA, INFORMATIKA, KEBUMIAN, ASTRONOMI, GEOGRAFI, EKONOMI, KECERDASAN ARTIFISIAL (9 CABANG + AI)",
      "1.) NAMA LENGKAP\n2.) KELAS (Cth: 10.1 CGC, 10.2 MAYOR)",
      "", "",
      "Budi Pratama\n10.1 CGC (Maksimal 20 orang per cabang lomba)",
      "", ""
    ],
    [
      "LOMBA DEBAT (LDBI) & NSDC",
      "1.) Nama Tim\n2.) Asal Kelas Tim\n3.) 1st, 2nd, and 3rd Speaker (NSDC) [Beri (-) jika tdk ikut]\n4.) Pembicara 1, 2, 3 (LDBI) [Beri (-) jika tdk ikut]",
      "", "",
      "Rhetoric Squad IGS\n11.1 MAYOR & 11.2 CGC\n1st: Alex, 2nd: Cindy, 3rd: David",
      "", ""
    ],
    [
      "COSPLAY (JEPANG / ANIME / POP CULTURE)",
      "1.) Nama Lengkap Peserta\n2.) Asal Kelas (Cth: 10.1 CGC, 10.2 MAYOR)\n3.) Nama Karakter yang Diperankan\n4.) Judul Serial Anime / Manga / Game Asal",
      "", "",
      "Ahmad Fauzan\n10.2 MAYOR\nKarakter: Roronoa Zoro (One Piece)",
      "", ""
    ],
    [
      "FLS3N - TARI KREASI (BEREGU 2 ORANG)",
      "1.) Nama Tim / Grup Tari\n2.) Asal Kelas Tim\n3.) Nama Lengkap Peserta 1\n4.) Nama Lengkap Peserta 2\n5.) No. WhatsApp Perwakilan",
      "", "",
      "Sanggar Melati CGC\n10.2 CGC\n1. Alya Syahrini, 2. Tiara Andini\n081234567890",
      "", ""
    ],
    [
      "FLS3N - VOKAL SOLO PUTRA & PUTRI",
      "1.) Nama & Kategori (cth: Rahmat Ardhani (Putra))\n2.) Kelas\n3.) Link lagu karaoke babak penyisihan\n4.) Link lagu karaoke babak final",
      "", "",
      "Rahmat Ardhani (Putra)\n11.1 CGC\nLink lagu penyisihan & final Google Drive / YouTube",
      "", ""
    ],
    [
      "KOMIK DIGITAL & DESAIN POSTER",
      "1.) Nama Lengkap\n2.) Kelas\n3.) Link Portofolio / Berkas Karya",
      "", "",
      "Wahyu Satria\n10.3 MAYOR\nLink Google Drive publik / Portofolio",
      "", ""
    ],
    [
      "CABANG OLAHRAGA BEREGU (Basket, Futsal, Voli)",
      "1.) Nama Tim / Kelas Kontingen\n2.) Asal Kelas Kontingen\n3.) Nama Anggota Inti & Cadangan",
      "", "",
      "Tim Kontingen Kelas 10.2 MAYOR\nPemain 1, Pemain 2, Pemain 3, dst.",
      "", ""
    ],
    [
      "CABANG OLAHRAGA INDIVIDU (Silat, Atletik, Catur)",
      "1.) Nama Lengkap Peserta\n2.) Kelas\n3.) Nomor Tanding",
      "", "",
      "Siti Aisyah\n11.2 CGC\nLari 60m / Tolak Peluru / Catur / Silat",
      "", ""
    ]
  ];

  sheetFormat.getRange(2, 1, formatRows.length, 7).setValues(formatRows);
  sheetFormat.getRange("A2:G2").setBackground(COLOR_CREAM).setFontWeight("bold").setFontColor("#332412");
  sheetFormat.autoResizeColumns(1, 7);

  // 2. Siapkan Tab Rekapitulasi Utama: Master Pendaftaran
  initOrFormatSheet(ss, "Master Pendaftaran", "#FFFFFF", "SEMUA PENDAFTARAN MASUK (REKAPITULASI LENGKAP)");

  // 3. Siapkan Tab Tersendiri per Cabang Lomba (1 Lomba = 1 Sheet)
  DAFTAR_CABANG_LOMBA.forEach(c => {
    initOrFormatSheet(ss, c.name, c.color, "PENDAFTARAN: " + c.name.toUpperCase());
  });

  return "Seluruh sheet cabang lomba berhasil disiapkan dengan rapi!";
}

function findSheetCaseInsensitive(ss, targetName) {
  if (!targetName) return null;
  const cleanTarget = targetName.toString().trim().toLowerCase().replace(/[:\\/?*\[\]]/g, "-");
  const sheets = ss.getSheets();
  for (let i = 0; i < sheets.length; i++) {
    const sName = sheets[i].getName().trim().toLowerCase();
    if (sName === cleanTarget || sName === targetName.toString().trim().toLowerCase()) {
      return sheets[i];
    }
  }
  return null;
}

function cleanSheetTitle(title) {
  if (!title) return "Lomba";
  let cleaned = title.toString().replace(/[:\\/?*\[\]]/g, "-").trim();
  if (cleaned.length > 50) cleaned = cleaned.substring(0, 50).trim();
  return cleaned;
}

function initOrFormatSheet(ss, sheetName, tabColor, bannerTitle) {
  const safeName = cleanSheetTitle(sheetName);
  let s = findSheetCaseInsensitive(ss, safeName);
  if (!s) {
    s = ss.insertSheet(safeName);
  }
  s.setTabColor(tabColor || COLOR_BLUE);
  
  if (s.getLastRow() < 2) {
    s.clear();
    s.getRange("A1:H1").merge()
      .setValue("NORDELIA 2026 — " + (bannerTitle || safeName.toUpperCase()))
      .setBackground(tabColor || COLOR_BLUE)
      .setFontWeight("bold")
      .setFontColor("#0F172A")
      .setHorizontalAlignment("center")
      .setFontSize(12);

    s.getRange("A2:H2").setValues([TABLE_HEADERS])
      .setBackground(COLOR_HEADER)
      .setFontColor("#FFFFFF")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");
      
    s.setFrozenRows(2);
    s.autoResizeColumns(1, 8);
  }
  return s;
}

/**
 * Webhook POST Receiver dari Portal Web Orvelion
 */
function doPost(e) {
  try {
    const raw = e.postData.contents;
    const data = JSON.parse(raw);
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    const timestamp = data.timestamp || new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta" });
    const category = (data.category || "").toUpperCase();
    const cabang = (data.cabang || data.cabang_name || "-").trim();
    const targetSheetRaw = data.target_sheet || cabang || "Lomba";
    const targetSheetName = cleanSheetTitle(targetSheetRaw);
    const nama = data.nama || "-";
    const kelas = data.kelas || "-";
    const kontak = data.kontak || "-";
    const detailStr = typeof data.detail === "object" ? JSON.stringify(data.detail) : (data.detail || "-");
    const status = "Terverifikasi Web";

    const rowData = [timestamp, category, cabang, nama, kelas, kontak, detailStr, status];

    // 1. Simpan ke Tab Rekapitulasi: "Master Pendaftaran"
    let masterSheet = findSheetCaseInsensitive(ss, "Master Pendaftaran");
    if (!masterSheet) {
      masterSheet = initOrFormatSheet(ss, "Master Pendaftaran", "#FFFFFF", "SEMUA PENDAFTARAN MASUK (REKAPITULASI LENGKAP)");
    }
    masterSheet.appendRow(rowData);

    // 2. Simpan ke Tab Khusus Cabang Lomba (1 Lomba = 1 Sheet)
    let cabangSheet = findSheetCaseInsensitive(ss, targetSheetName);
    if (!cabangSheet) {
      let tabColor = COLOR_BLUE;
      if (category.indexOf("BAHASA") !== -1) tabColor = COLOR_PINK;
      else if (category.indexOf("SENI") !== -1) tabColor = COLOR_CREAM;
      else if (category.indexOf("COSPLAY") !== -1) tabColor = COLOR_GOLD;
      else if (category.indexOf("OLAHRAGA") !== -1) tabColor = COLOR_PINK;

      cabangSheet = initOrFormatSheet(ss, targetSheetName, tabColor, "PENDAFTARAN: " + targetSheetName.toUpperCase());
    }
    cabangSheet.appendRow(rowData);

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Data berhasil dicatat ke Master Pendaftaran dan tab '" + targetSheetName + "'",
      sheet: targetSheetName,
      timestamp: timestamp
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Webhook GET Ping / Setup Generator
 */
function doGet(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (e && e.parameter && (e.parameter.setup === "1" || e.parameter.action === "setup")) {
    setupNordeliaSpreadsheet();
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "BERHASIL! Seluruh sheet cabang lomba + Master Pendaftaran + Format Pendaftaran telah selesai dibuat otomatis!",
      total_sheets: ss.getSheets().length
    })).setMimeType(ContentService.MimeType.JSON);
  }

  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    app: "Nordelia Webhook Backend 2026 (1 Lomba = 1 Sheet)",
    total_sheets_aktif: ss.getSheets().length,
    petunjuk_setup: "Akses URL ini dengan tambahan '?setup=1' di browser untuk otomatis menata seluruh tab sheet cabang lomba."
  })).setMimeType(ContentService.MimeType.JSON);
}
