/**
 * =========================================================================
 * GOOGLE APPS SCRIPT: NORDELIA 2026 PER-CABANG LOMBA SPREADSHEET BACKEND
 * SMA Ignatius Global School (IGS) Palembang - Kabinet Orvelion 2026-2027
 * =========================================================================
 * 
 * ATURAN DISTRIBUSI SHEET:
 * 1. Setiap lomba memiliki 1 Sheet tersendiri (Olimpiade Kimia 1 sheet, Olimpiade Biologi 1 sheet,
 *    Olimpiade AI 1 sheet, Literasi Numerasi 1 sheet, Basket 1 sheet, Futsal 1 sheet, dst.)
 * 2. Terdapat tab 'Master Pendaftaran' yang otomatis merekap semua pendaftaran yang masuk.
 * 3. Terdapat tab 'Format Pendaftaran' sesuai format resmi Sheet 2.
 * 4. Pembuatan Sheet Otomatis: Jika sheet suatu lomba belum ada, sistem otomatis membuatnya
 *    dan memberi desain header pastel rapi saat data pertama kali masuk.
 * 
 * CARA MENGGUNAKAN (Cukup 1 Menit):
 * 1. Buka Google Spreadsheet pendaftaran Nordelia Anda.
 * 2. Klik menu 'Extensions' (Ekstensi) > 'Apps Script'.
 * 3. Hapus semua kode lama dan PASTE (tempel) seluruh isi file ini.
 * 4. Klik ikon 'Save' (Simpan) disket.
 * 5. Pilih fungsi 'setupNordeliaSpreadsheet' di dropdown atas, lalu klik 'Run' (Jalankan)
 *    agar SELURUH 43 SHEET CABANG LOMBA terbuat otomatis di spreadsheet Anda!
 *    (Atau cukup buka Web App URL dengan parameter ?setup=1 di browser).
 * 6. Klik tombol 'Deploy' (Terapkan) di pojok kanan atas:
 *    - Pilih 'Manage deployments' (Kelola penerapan).
 *    - Klik ikon pensil (Edit).
 *    - Pada bagian Version pilih: 'New version' (Versi baru).
 *    - Klik 'Deploy' (Terapkan).
 */

const COLOR_PINK = "#FFB7C5";    // Pink Pastel (Bahasa & Olahraga)
const COLOR_CREAM = "#FFE5B4";   // Oranye / Krem Pastel (Seni)
const COLOR_BLUE = "#AEC6CF";    // Biru Muda Pastel (Akademik & Sains)
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

// Daftar 43 Cabang Lomba Resmi Nordelia 2026 (1 Lomba = 1 Sheet)
const DAFTAR_CABANG_LOMBA = [
  // AKADEMIK & SAINS
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

function setupNordeliaSpreadsheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Buat / Siapkan Sheet: Format Pendaftaran (Sesuai Sheet 2)
  let sheetFormat = findSheetCaseInsensitive(ss, "Format Pendaftaran") || ss.insertSheet("Format Pendaftaran");
  sheetFormat.clear();
  sheetFormat.setTabColor(COLOR_PINK);
  
  sheetFormat.getRange("A1:G1").merge()
    .setValue("PANDUAN & FORMAT RESMI PENDAFTARAN LOMBA NORDELIA 2026 (SHEET 2)")
    .setBackground(COLOR_PINK)
    .setFontWeight("bold")
    .setFontColor("#3B1724")
    .setHorizontalAlignment("center")
    .setFontSize(13);

  const formatRows = [
    ["KATEGORI LOMBA", "FORMAT ISIAN WAJIB", "", "", "CONTOH ISIAN / KETERANGAN", "", ""],
    [
      "OLIMPIADE MATEMATIKA, FISIKA, BIOLOGI, KIMIA, INFORMATIKA, KEBUMIAN, ASTRONOMI, GEOGRAFI, EKONOMI, KECERDASAN ARTIFISIAL (9 CABANG)",
      "1.) NAMA LENGKAP\n2.) KELAS (Cth: 10.1 CGC, 10.2 MAYOR)",
      "", "",
      "Budi Pratama\n10.1 CGC (Maksimal 20 orang per cabang)",
      "", ""
    ],
    [
      "LOMBA DEBAT INDONESIA (LDBI) & NSDC",
      "1.) Nama Tim\n2.) Asal Kelas Tim\n3.) 1st, 2nd, and 3rd Speaker (NSDC) [Beri (-) jika tdk ikut]\n4.) Pembicara 1, 2, 3 (LDBI) [Beri (-) jika tdk ikut]",
      "", "",
      "Rhetoric Squad IGS\n11.1 MAYOR & 11.2 CGC\n1st: Alex, 2nd: Cindy, 3rd: David",
      "", ""
    ],
    [
      "FLS3N - TARI KREASI (BEREGU 2 ORANG)",
      "1.) Nama Tim / Grup Tari\n2.) Asal Kelas Tim\n3.) Nama Lengkap Peserta 1\n4.) Nama Lengkap Peserta 2\n5.) No. WhatsApp",
      "", "",
      "Sanggar Melati CGC\n10.2 CGC\n1. Alya Syahrini, 2. Tiara Andini\n081234567890",
      "", ""
    ],
    [
      "FLS3N - VOKAL SOLO PUTRA & PUTRI",
      "1.) Nama & Kategori (cth: Rahmat Ardhani (Putra))\n2.) Kelas\n3.) Link lagu karaoke babak penyisihan\n4.) Link lagu karaoke babak final",
      "", "",
      "Rahmat Ardhani (Putra)\n11.1 CGC\nLink lagu penyisihan & final",
      "", ""
    ],
    [
      "KOMIK DIGITAL & DESAIN POSTER",
      "1.) Nama\n2.) Kelas\n3.) Link Karya / Portofolio",
      "", "",
      "Wahyu Satria\n10.3 MAYOR\nLink Google Drive / Portofolio",
      "", ""
    ],
    [
      "CABANG OLAHRAGA BEREGU (Basket, Futsal, Voli)",
      "1.) Nama Tim / Kelas Kontingen\n2.) Asal Kelas Kontingen\n3.) Nama Anggota 1-2-3 (Basket) / 1-2-3-4-5 (Futsal/Voli) & Cadangan (opsional)",
      "", "",
      "Tim Kontingen Kelas 10.2 MAYOR\nPemain 1, Pemain 2, Pemain 3, dst.",
      "", ""
    ],
    [
      "CABANG OLAHRAGA INDIVIDU (Silat, Atletik, Catur)",
      "1.) Nama\n2.) Kelas\n3.) Nomor Tanding",
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

  return "Seluruh 43 sheet lomba berhasil disiapkan!";
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
  // Karakter terlarang di Google Sheets: : \ / ? * [ ]
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
  
  // Jika sheet masih baru atau kosong, pasang banner & headers
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
    s.autoResizeColumns(1, 8);
  }
  return s;
}

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

    // 2. Simpan ke Tab Khusus Cabang Lomba (1 Lomba 1 Sheet)
    let cabangSheet = findSheetCaseInsensitive(ss, targetSheetName);
    if (!cabangSheet) {
      // Tentukan warna tab berdasarkan kategori
      let tabColor = COLOR_BLUE;
      if (category.indexOf("BAHASA") !== -1) tabColor = COLOR_PINK;
      else if (category.indexOf("SENI") !== -1) tabColor = COLOR_CREAM;
      else if (category.indexOf("OLAHRAGA") !== -1) tabColor = COLOR_PINK;

      cabangSheet = initOrFormatSheet(ss, targetSheetName, tabColor, "PENDAFTARAN: " + targetSheetName.toUpperCase());
    }
    cabangSheet.appendRow(rowData);

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Data berhasil dicatat ke Master Pendaftaran dan sheet '" + targetSheetName + "'",
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

function doGet(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  // Jika dibuka di browser dengan parameter ?setup=1, otomatis jalankan pembuatan semua sheet lomba!
  if (e && e.parameter && (e.parameter.setup === "1" || e.parameter.action === "setup")) {
    setupNordeliaSpreadsheet();
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "BERHASIL! Seluruh 48 sheet cabang lomba + Master Pendaftaran + Format Pendaftaran telah selesai dibuat otomatis!",
      total_sheets: ss.getSheets().length
    })).setMimeType(ContentService.MimeType.JSON);
  }

  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    app: "Nordelia Webhook Backend (1 Lomba 1 Sheet)",
    total_sheets_aktif: ss.getSheets().length,
    petunjuk_setup: "Kunjungi URL ini dengan tambahan '?setup=1' di browser untuk otomatis membuat seluruh 48 sheet cabang lomba sekarang juga!"
  })).setMimeType(ContentService.MimeType.JSON);
}
