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
}

# Default kategori kalau kolom "Sub Kategori Awal" kosong (aturan dari Anda)
DEFAULT_SUB_KATEGORI_AWAL = "INTERNET DOWN/NO INTERNET"

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
