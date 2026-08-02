# =====================================================
# KONFIGURASI FORM
# =====================================================
# Diambil dari payload hasil capture (screenshot Anda) untuk form:
# "BACK-OFFICE - Monitoring Division & Mutation National"

FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSeMekvFOyaT4esbVBv2X4v7H82STVghbbX9VbErUlNGp2P6bQ"
    "/formResponse"
)

# Mapping field Excel -> entry ID Google Form
ENTRY = {
    "nama": "entry.1023189111",
    "nama_cso_perbantuan": "entry.944156118",   # selalu "0" (kolom Excel ini 100% kosong, sama seperti contoh capture)
    "sub_kategori_awal": "entry.813210749",
    "sub_kategori_akhir": "entry.1771094549",
    "sbu": "entry.481680192",
    "sub_bidang_awal": "entry.2018209493",
    "sub_bidang_akhir": "entry.628101911",
    "id_ticket": "entry.916053770",
    "keterangan_tambahan": "entry.148392310",
    "jenis_ticket": "entry.1266375959",
    "jenis_ticket_sentinel": "entry.1266375959_sentinel",

    "pickup_hour": "entry.748149884_hour",
    "pickup_minute": "entry.748149884_minute",
    "pickup_second": "entry.748149884_second",

    "create_time_hour": "entry.844611402_hour",
    "create_time_minute": "entry.844611402_minute",
    "create_time_second": "entry.844611402_second",

    "create_date_year": "entry.995843652_year",
    "create_date_month": "entry.995843652_month",
    "create_date_day": "entry.995843652_day",
}

# =====================================================
# MAPPING LABEL DROPDOWN "Sub Kategori Awal" / "Sub Kategori Akhir"
# =====================================================
# SEMUA SUDAH DIKONFIRMASI langsung dari daftar pilihan asli di form
# (hasil fetch halaman form, bukan tebakan lagi).

CATEGORY_MAP = {
    "INTERNET DOWN/NO INTERNET": "Gangguan Internet Down",
    "LINK LOSS": "Gangguan Link Loss",
    "ONT PROBLEM": "Gangguan ONT Problem",
    "INTERNET SLOW": "Gangguan Internet Slow",
    # Ditulis dengan istilah yang sama sekali beda dari label dropdown
    # form (bukan cuma beda kapital/tanda hubung), jadi tidak bisa
    # tertangkap oleh pencocokan otomatis -- perlu alias eksplisit.
    # Dikonfirmasi dari screenshot dropdown form: "Gangguan Tidak dapat
    # akses web/situs tertentu."
    "TIDAK BISA AKSES WEB": "Gangguan Tidak dapat akses web/situs tertentu.",
}

# Default kategori kalau kolom "Sub Kategori Awal" kosong (aturan dari Anda)
DEFAULT_SUB_KATEGORI_AWAL = "INTERNET DOWN/NO INTERNET"

# =====================================================
# DAFTAR LENGKAP PILIHAN VALID "Sub Kategori Awal" / "Sub Kategori Akhir"
# =====================================================
# Diambil PERSIS dari dropdown form (screenshot Anda). Dipakai untuk
# memvalidasi/mencocokkan nilai dari Excel -- kalau nilai Excel (setelah
# dinormalisasi: huruf besar semua, tanda "-" dan spasi berlebih dibuang)
# cocok dengan salah satu daftar ini, nilai PERSIS dari daftar ini yang
# dikirim ke form (bukan nilai mentah dari Excel), supaya selalu sama
# persis dengan opsi dropdown dan tidak ditolak form (HTTP 400).

CATEGORY_VALID_OPTIONS = [
    "Gangguan Internet Down",
    "Gangguan Link Loss",
    "Gangguan Internet Slow",
    "Gangguan Intermitten",
    "Gangguan Tidak dapat akses web/situs tertentu.",
    "Gangguan TV Problem",
    "Gangguan Cable Problem",
    "Gangguan ONT Problem",
    "Gangguan lain lain",
    "Keluhan Pemasangan",
    "Keluhan Isolir",
    "Keluhan Billing",
    "Keluhan Refund",
    "Keluhan Upgrade",
    "Keluhan Downgrade",
    "Keluhan Cable Problem",
    "Keluhan Deaktifasi",
    "Keluhan lain lain",
    "Keluhan Pendaftaran",
    "Keluhan ICONCASH",
    "Keluhan PLN Mobile",
    "Keluhan Coverage",
    "Keluhan Permohonan Upgrade",
    "Keluhan Permohonan Downgrade",
    "Keluhan Komisi mitra",
    "Keluhan Permohonan Ubah Data",
    "Keluhan Ganti Password",
    "Keluhan Ganti SSID",
    "Keluhan Permohonan Pendaftaran",
    "Keluhan MYICON+ Kendala Fitur",
    "Keluhan Petugas Aktivasi",
    "Informasi Billing",
]

# =====================================================
# DAFTAR PILIHAN VALID "SUB BIDANG AWAL" / "SUB BIDANG AKHIR"
# =====================================================
# Diambil persis dari dropdown form (field ini TIDAK wajib diisi).
# Kalau nilai di Excel tidak cocok PERSIS dengan salah satu ini
# (contoh: "NOC SBU" bukan "NOC RITEL SBU" -- sudah dikonfirmasi
# ke Anda bahwa keduanya BEDA unit), field akan dikosongkan saat
# submit dan barisnya dilaporkan di UI sebagai "dilewati (SUB BIDANG
# tidak valid)" supaya tidak hilang diam-diam.

SUB_BIDANG_VALID_OPTIONS = {
    "BILLING RITEL PUSAT",
    "HELPDESK PLN MOBILE",
    "IT ENTERPRISE",
    "SALES RITEL SBU",
    "AKTIVASI RITEL SBU",
    "CM RITEL PUSAT",
    "SALES RITEL PUSAT",
    "NOC RITEL PUSAT",
    "NOC RITEL SBU",
}

# =====================================================
# ALIAS PENULISAN SUB BIDANG
# =====================================================
# Beberapa nilai di Excel ditulis dengan nama singkat/beda tapi
# sebenarnya merujuk ke unit yang SAMA dengan salah satu opsi valid
# di atas. "NOC SBU" == "NOC RITEL SBU" (dikonfirmasi ulang oleh Anda,
# sebelumnya sempat dianggap beda unit -- sekarang dikoreksi).
# Tambahkan alias baru di sini kalau ada penulisan lain yang serupa.

SUB_BIDANG_ALIAS = {
    "NOC SBU": "NOC RITEL SBU",
}

# =====================================================
# DAFTAR PILIHAN VALID "SBU"
# =====================================================
# Diambil persis dari dropdown "SBU" di form. Dipakai sebagai daftar
# pilihan manual di UI saat baris Excel punya SBU kosong, supaya tidak
# tergantung nilai yang kebetulan ada di file Excel yang sedang diupload.

SBU_OPTIONS = [
    "JAWA BAGIAN BARAT",
    "JAWA BAGIAN TENGAH",
    "JAWA BAGIAN TIMUR",
    "JAKARTA & BANTEN",
    "BALI & NUSRA",
    "SULAWESI & INDONESIA TIMUR",
    "KALIMANTAN",
    "SUMATERA BAGIAN SELATAN",
    "SUMATERA BAGIAN TENGAH",
    "SUMATERA BAGIAN UTARA",
]

# =====================================================
# ALIAS PENULISAN SBU
# =====================================================
# Beberapa file Excel menulis SBU wilayah Bali dengan nama panjang
# "BALI & NUSA TENGGARA", padahal label PERSIS di dropdown form adalah
# "BALI & NUSRA" (dikonfirmasi dari screenshot dropdown SBU form).
# Sebelumnya field SBU sama sekali tidak divalidasi terhadap
# SBU_OPTIONS di app.py, jadi nilai yang salah ini lolos tanpa ditahan
# untuk direview lalu ditolak Google Form (HTTP 400) saat submit.
# Tambahkan alias baru di sini kalau ditemukan penulisan lain yang serupa.

SBU_ALIAS = {
    "BALI & NUSA TENGGARA": "BALI & NUSRA",
}
