/**
 * =========================================================================
 * GOOGLE APPS SCRIPT: NORDELIA 2026 REAL-TIME SPREADSHEET BACKEND
 * SMA Ignatius Global School (IGS) Palembang - Kabinet Orvelion 2026-2027
 * =========================================================================
 * 
 * CARA MENGGUNAKAN (Cukup 1 Menit):
 * 1. Buka Google Spreadsheet baru (atau spreadsheet yang sudah ada).
 * 2. Klik menu 'Extensions' (Ekstensi) > 'Apps Script'.
 * 3. Hapus semua kode default dan PASTE (tempel) seluruh isi file ini.
 * 4. Klik tombol 'Run' (Jalankan) pada fungsi 'setupNordeliaSpreadsheet'
 *    (Ini otomatis membuat 6 Tab dengan desain warna pastel pastel: Format Pendaftaran,
 *     Master Pendaftaran, Akademik, Bahasa, Seni, Olahraga).
 * 5. Klik 'Deploy' (Terapkan) di pojok kanan atas > 'New deployment' (Penerapan baru).
 * 6. Pilih tipe: 'Web app' (Aplikasi Web).
 *    - Description: Nordelia Form Hook
 *    - Execute as: 'Me' (Saya)
 *    - Who has access: 'Anyone' (Siapa saja)
 * 7. Salin Web App URL yang dihasilkan, lalu masukkan ke file .env Anda:
 *    GOOGLE_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
 * 8. Selesai! Setiap pendaftaran di web langsung masuk real-time ke spreadsheet ini!
 */

const COLOR_PINK = "#FFB7C5";    // Pink Pastel (Sisi Kiri)
const COLOR_CREAM = "#FFE5B4";   // Oranye / Krem Pastel (Tengah Bawah)
const COLOR_BLUE = "#AEC6CF";    // Biru Muda Pastel (Sisi Kanan)
const COLOR_HEADER = "#2D2622";  // Dark Elegant Header

function setupNordeliaSpreadsheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Buat / Siapkan Sheet: Format Pendaftaran (Sesuai Sheet 2)
  let sheetFormat = ss.getSheetByName("Format Pendaftaran") || ss.insertSheet("Format Pendaftaran");
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
      "Budi Pratama\n10.1 CGC",
      "", ""
    ],
    [
      "LOMBA DEBAT INDONESIA (LDBI) & NSDC",
      "1.) Nama Tim\n2.) Asal Kelas Tim\n3.) 1st, 2nd, and 3rd Speaker (NSDC) [Beri (-) jika tdk ikut]\n4.) Pembicara 1, 2, 3 (LDBI) [Beri (-) jika tdk ikut]",
      "", "",
      "Rhetoric Squad IGS\n11.1 MAYOR & 11.2 CGC\n1st: Alex (11.1), 2nd: Cindy (11.2), 3rd: David (11.1)",
      "", ""
    ],
    [
      "FLS3N - VOKAL SOLO PUTRA & PUTRI",
      "1.) Nama & Kategori (cth: Rahmat Ardhani (Putra))\n2.) Kelas\n3.) Link lagu karaoke babak penyisihan\n4.) Link lagu karaoke babak final",
      "", "",
      "Rahmat Ardhani (Putra)\n11.1 CGC\nhttps://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=...",
      "", ""
    ],
    [
      "KOMIK DIGITAL & DESAIN POSTER",
      "1.) Nama\n2.) Kelas\n3.) Link Karya / Portofolio",
      "", "",
      "Wahyu Satria\n10.3 MAYOR\nhttps://drive.google.com/file/d/...",
      "", ""
    ],
    [
      "CABANG OLAHRAGA BEREGU (Basket, Futsal, Voli)",
      "1.) Nama Tim\n2.) Kelas Kontingen\n3.) Nama Kapten\n4.) Daftar Pemain & No Punggung",
      "", "",
      "Garuda Mayor Futsal\n10.2 MAYOR\nKapten: Daniel (08123456789)\nPemain: Daniel (10), Kevin (7), Budi (9), ...",
      "", ""
    ],
    [
      "CABANG OLAHRAGA PERORANGAN (Silat, Atletik, Catur)",
      "1.) Nama Lengkap Atlet\n2.) Kelas\n3.) Nomor Tanding (Lari 60m / Tolak Peluru / Lompat Jauh / Catur / Silat)",
      "", "",
      "Siti Aisyah\n11.2 CGC\nLari 60 meter & Tolak Peluru",
      "", ""
    ]
  ];

  sheetFormat.getRange(2, 1, formatRows.length, 7).setValues(formatRows);
  sheetFormat.getRange("A2:G2").setBackground(COLOR_CREAM).setFontWeight("bold").setFontColor("#332412");
  sheetFormat.autoResizeColumns(1, 7);

  // 2. Siapkan Tabs Klasifikasi: Master, Akademik, Bahasa, Seni, Olahraga
  const categoryTabs = [
    { name: "Master Pendaftaran", color: "#FFFFFF", title: "SEMUA PENDAFTARAN MASUK (REAL-TIME)" },
    { name: "Akademik", color: COLOR_BLUE, title: "DATA PENDAFTARAN: BIDANG AKADEMIK & SAINS" },
    { name: "Bahasa", color: COLOR_PINK, title: "DATA PENDAFTARAN: BIDANG BAHASA & DEBAT" },
    { name: "Seni", color: COLOR_CREAM, title: "DATA PENDAFTARAN: BIDANG SENI & FLS3N" },
    { name: "Olahraga", color: COLOR_PINK, title: "DATA PENDAFTARAN: BIDANG OLAHRAGA & O2SN" },
  ];

  const headers = [
    "WAKTU PENDAFTARAN",
    "KATEGORI",
    "CABANG LOMBA",
    "NAMA PESERTA / TIM",
    "KELAS",
    "NO. WHATSAPP / KONTAK",
    "DETAIL TAMBAHAN / FORMAT ISIAN",
    "STATUS"
  ];

  categoryTabs.forEach(tab => {
    let s = ss.getSheetByName(tab.name) || ss.insertSheet(tab.name);
    s.clear();
    s.setTabColor(tab.color);
    
    // Header Banner
    s.getRange("A1:H1").merge()
      .setValue("NORDELIA 2026 — " + tab.title)
      .setBackground(tab.color)
      .setFontWeight("bold")
      .setFontColor("#1C1518")
      .setHorizontalAlignment("center")
      .setFontSize(12);

    // Columns Header
    s.getRange("A2:H2").setValues([headers])
      .setBackground(COLOR_HEADER)
      .setFontColor("#FFFFFF")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");
      
    s.setFrozenRows(2);
    s.autoResizeColumns(1, 8);
  });
}

function doPost(e) {
  try {
    const raw = e.postData.contents;
    const data = JSON.parse(raw);
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    const timestamp = data.timestamp || new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta" });
    const category = (data.category || "").toUpperCase();
    const cabang = data.cabang || "-";
    const nama = data.nama || "-";
    const kelas = data.kelas || "-";
    const kontak = data.kontak || "-";
    const detailStr = typeof data.detail === "object" ? JSON.stringify(data.detail) : (data.detail || "-");
    const status = "Terverifikasi Web";

    const rowData = [timestamp, category, cabang, nama, kelas, kontak, detailStr, status];

    // 1. Simpan ke Master Sheet
    const masterSheet = ss.getSheetByName("Master Pendaftaran") || ss.getActiveSheet();
    masterSheet.appendRow(rowData);

    // 2. Klasifikasi otomatis ke Tab Kategori yang sesuai
    let targetSheetName = "Master Pendaftaran";
    if (category.indexOf("AKADEMIK") !== -1) targetSheetName = "Akademik";
    else if (category.indexOf("BAHASA") !== -1) targetSheetName = "Bahasa";
    else if (category.indexOf("SENI") !== -1) targetSheetName = "Seni";
    else if (category.indexOf("OLAHRAGA") !== -1) targetSheetName = "Olahraga";

    const catSheet = ss.getSheetByName(targetSheetName);
    if (catSheet && targetSheetName !== "Master Pendaftaran") {
      catSheet.appendRow(rowData);
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Data berhasil dicatat ke spreadsheet real-time!",
      category: targetSheetName,
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
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    app: "Nordelia Real-Time Spreadsheet Hook",
    description: "Webhook pendaftaran aktif dan siap menerima data real-time."
  })).setMimeType(ContentService.MimeType.JSON);
}
