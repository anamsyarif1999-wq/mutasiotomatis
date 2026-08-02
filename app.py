import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import random
import time
import json

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import (
    FORM_URL,
    ENTRY,
    CATEGORY_MAP,
    CATEGORY_VALID_OPTIONS,
    DEFAULT_SUB_KATEGORI_AWAL,
    SUB_BIDANG_VALID_OPTIONS,
    SUB_BIDANG_ALIAS,
    SBU_OPTIONS,
    SBU_ALIAS,
)

# =====================================================
# CONFIG
# =====================================================

PROGRESS_FILE = "progress.json"

REQUIRED_COLS = [
    "Nama",
    "ID Ticket",
    "Jenis Ticket",
    "Sub Kategori Awal",
    "Sub Kategori Akhir",
    "SBU",
    "Create Ticket date",
    "Create Ticket Time",
]

# =====================================================
# PICKUP TIME
# =====================================================
# CATATAN PERBAIKAN:
# Versi lama menyambung pickup dari pickup baris sebelumnya
# (pickup_baru = pickup_lama + random(1,10) detik), TANPA pernah
# mengacu ke waktu submit yang sebenarnya (`now`). Karena antar
# submit ada jeda nyata random(min_delay, max_delay) detik (default
# 10-30 detik) lewat time.sleep(), sementara pickup cuma nambah
# 1-10 detik per baris, pickup jadi makin lama makin ketinggalan
# jauh dari waktu asli. Akibatnya AHT (Create Ticket Time - Pick Up
# Time) terus membesar tanpa batas seiring banyaknya baris yang
# diimport, alih-alih konsisten kecil seperti yang diinginkan.
#
# Fix: pickup dihitung ulang dari `now` (waktu submit sebenarnya)
# di SETIAP pemanggilan, independen dari baris sebelumnya. Dengan
# ini AHT tiap tiket akan konsisten random 9-15 detik, berapa pun
# banyak baris yang diimport dan berapa pun lama proses importnya.


def get_pickup_time():
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    pickup = now - timedelta(seconds=random.randint(9, 15))
    return pickup


# =====================================================
# PROGRESS
# =====================================================

def load_progress():
    try:
        if Path(PROGRESS_FILE).exists():
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
            return data.get("last_success", 0)
    except Exception:
        pass
    return 0


def save_progress(row_number):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"last_success": row_number}, f)


def reset_progress():
    save_progress(0)


# =====================================================
# HELPER
# =====================================================

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_for_match(s):
    """Huruf besar semua, buang tanda '-' dan rapikan spasi, untuk pencocokan
    yang tidak peduli beda kapitalisasi/tanda hubung antara Excel & form."""
    s = s.upper().replace("-", " ")
    return " ".join(s.split())


_CATEGORY_VALID_LOOKUP = {
    _normalize_for_match(opt): opt for opt in CATEGORY_VALID_OPTIONS
}


def map_category(raw_value):
    """
    Terjemahkan nilai mentah Excel ke label dropdown Google Form.
    Kembalikan (nilai_untuk_dikirim, dikenali_bool).

    Urutan pencocokan:
      1. CATEGORY_MAP -- alias eksplisit untuk penulisan yang beda jauh
         dari label form (mis. "INTERNET DOWN/NO INTERNET" -> "Gangguan
         Internet Down").
      2. Pencocokan longgar ke CATEGORY_VALID_OPTIONS (daftar lengkap
         opsi dropdown form) -- mengabaikan beda huruf besar/kecil dan
         tanda "-", supaya "KELUHAN - LAIN LAIN" otomatis cocok dengan
         "Keluhan lain lain".
      3. Kalau tetap tidak cocok, dikenali_bool=False -- field ini JANGAN
         dikirim mentah-mentah, karena field dropdown akan ditolak form
         dengan HTTP 400 kalau nilainya tidak cocok persis dengan salah
         satu opsi.
    """
    raw_value = clean(raw_value)
    if raw_value == "":
        return "", True

    # Buang prefix "GANGGUAN - " kalau ada (format lama, tetap didukung)
    normalized = raw_value.replace("GANGGUAN - ", "").strip()
    if normalized in CATEGORY_MAP:
        return CATEGORY_MAP[normalized], True

    match = _CATEGORY_VALID_LOOKUP.get(_normalize_for_match(raw_value))
    if match:
        return match, True

    return "", False


def resolve_sub_kategori_awal(row):
    raw = clean(row.get("Sub Kategori Awal", ""))
    if raw == "":
        raw = DEFAULT_SUB_KATEGORI_AWAL
    return map_category(raw)


def resolve_sub_bidang(raw_value):
    """
    Kembalikan (nilai_untuk_dikirim, dilewati_bool).
    Nilai raw dinormalisasi dulu lewat SUB_BIDANG_ALIAS (mis. "NOC SBU"
    -> "NOC RITEL SBU") sebelum dicocokkan ke daftar pilihan valid.
    Kalau setelah dinormalisasi tetap tidak cocok dengan salah satu
    pilihan valid di dropdown form, field dikosongkan (bukan dipaksakan)
    dan dilewati_bool=True supaya baris ini bisa dilaporkan ke user.
    """
    raw = clean(raw_value)
    if raw == "":
        return "", False
    normalized = SUB_BIDANG_ALIAS.get(raw, raw)
    if normalized in SUB_BIDANG_VALID_OPTIONS:
        return normalized, False
    return "", True


def resolve_sbu(raw_value):
    """
    Kembalikan (nilai_untuk_dikirim, dikenali_bool).
    Nilai raw dinormalisasi dulu lewat SBU_ALIAS (mis. "BALI & NUSA
    TENGGARA" -> "BALI & NUSRA", penulisan yang sering dipakai di Excel
    tapi beda dari label persis di dropdown form) sebelum dicocokkan ke
    SBU_OPTIONS. Kalau tetap tidak cocok, dikenali_bool=False -- SBU
    adalah field dropdown juga di form, jadi kalau dikirim mentah-mentah
    dan tidak persis sama dengan salah satu opsi, form akan menolak
    dengan HTTP 400.
    """
    raw = clean(raw_value)
    if raw == "":
        return "", False
    normalized = SBU_ALIAS.get(raw.upper(), raw)
    if normalized in SBU_OPTIONS:
        return normalized, True
    return "", False


def resolve_create_datetime(row):
    """
    Gabungkan kolom Create Ticket date + Create Ticket Time jadi datetime.
    Kalau salah satu kosong, TIDAK diisi otomatis dengan waktu upload —
    baris ini akan diminta diisi manual lewat tabel 'Perlu Ditinjau'
    di UI (lihat build_review_queue), supaya waktu tiket tetap
    mencerminkan data historis yang sebenarnya, bukan waktu proses import.
    """
    date_raw = row.get("Create Ticket date", None)
    time_raw = row.get("Create Ticket Time", None)

    if pd.isna(date_raw) or pd.isna(time_raw):
        return None

    try:
        # dayfirst=True karena format tanggal di Excel Anda adalah
        # DD/MM/YYYY (contoh: 01/08/2026 = 1 Agustus 2026), bukan
        # format Amerika MM/DD/YYYY. Tanpa ini, tanggal seperti
        # "01/08/2026" bisa salah terbaca jadi 8 Januari 2026.
        date_str = pd.to_datetime(date_raw, dayfirst=True).strftime("%Y-%m-%d")
        time_str = str(time_raw).strip()
        return pd.to_datetime(f"{date_str} {time_str}")
    except Exception:
        return None


# =====================================================
# DATA QUALITY CHECK
# =====================================================

def build_review_queue(df):
    """
    Cari baris yang butuh keputusan manual:
      - SBU kosong ATAU tidak cocok dropdown -> perlu pilih dari daftar
        SBU valid (bukan random, dan bukan dikirim mentah-mentah apa
        adanya dari Excel -- SBU adalah field dropdown juga di form,
        jadi nilai yang tidak cocok persis akan ditolak HTTP 400).
      - Create Ticket date/time kosong -> perlu isi tanggal & jam yang benar
      - Sub Kategori Awal/Akhir tidak dikenal -> nilainya tidak cocok
        dengan opsi dropdown manapun di form (kalau dipaksa kirim, form
        akan menolak dengan HTTP 400), jadi perlu dipetakan manual ke
        salah satu opsi yang valid.
    Field lain yang boleh kosong (SUB BIDANG AWAL/AKHIR, Keterangan Tambahan)
    tidak masuk sini karena memang tidak wajib.
    """
    issues = []
    for idx, row in df.iterrows():
        row_issues = []
        sbu_raw = clean(row.get("SBU", ""))
        if sbu_raw == "":
            row_issues.append("SBU kosong")
        else:
            _, sbu_ok = resolve_sbu(sbu_raw)
            if not sbu_ok:
                row_issues.append(f"SBU tidak dikenal ('{sbu_raw}')")
        if resolve_create_datetime(row) is None:
            row_issues.append("Create Ticket date/time kosong")

        _, awal_ok = resolve_sub_kategori_awal(row)
        if not awal_ok:
            row_issues.append(
                f"Sub Kategori Awal tidak dikenal ('{clean(row.get('Sub Kategori Awal', ''))}')"
            )

        _, akhir_ok = map_category(row.get("Sub Kategori Akhir", ""))
        if not akhir_ok:
            row_issues.append(
                f"Sub Kategori Akhir tidak dikenal ('{clean(row.get('Sub Kategori Akhir', ''))}')"
            )

        if row_issues:
            issues.append(
                {
                    "idx": idx,
                    "ID Ticket": row.get("ID Ticket", ""),
                    "issues": row_issues,
                }
            )
    return issues


# =====================================================
# BUILD PAYLOAD
# =====================================================

def build_payload(row, manual_sbu=None, manual_datetime=None,
                   manual_kategori_awal=None, manual_kategori_akhir=None):
    payload = {}

    # ---------------------------------
    # PICK UP TIME (persis app.py lama - dari chain delay, bukan dari Excel)
    # ---------------------------------
    pickup = get_pickup_time()

    # ---------------------------------
    # CREATE DATE & TIME
    # ---------------------------------
    create_dt = manual_datetime or resolve_create_datetime(row)

    # CATATAN: nilai pickup time & create ticket time sebelumnya tertukar
    # saat masuk ke Google Form (field "Pick Up Time" kebagian jam Create
    # Ticket, dan sebaliknya). Ditukar balik di sini supaya masing-masing
    # entry menerima nilai yang benar.
    payload[ENTRY["pickup_hour"]] = create_dt.strftime("%H")
    payload[ENTRY["pickup_minute"]] = create_dt.strftime("%M")
    payload[ENTRY["pickup_second"]] = create_dt.strftime("%S")

    payload[ENTRY["create_time_hour"]] = pickup.strftime("%H")
    payload[ENTRY["create_time_minute"]] = pickup.strftime("%M")
    payload[ENTRY["create_time_second"]] = pickup.strftime("%S")

    payload[ENTRY["create_date_year"]] = create_dt.strftime("%Y")
    payload[ENTRY["create_date_month"]] = create_dt.strftime("%m")
    payload[ENTRY["create_date_day"]] = create_dt.strftime("%d")

    # ---------------------------------
    # FIELD FORM
    # ---------------------------------
    payload[ENTRY["nama"]] = clean(row["Nama"])
    payload[ENTRY["id_ticket"]] = clean(row["ID Ticket"])
    payload[ENTRY["jenis_ticket"]] = clean(row["Jenis Ticket"])
    payload[ENTRY["jenis_ticket_sentinel"]] = ""

    if manual_kategori_awal:
        kategori_awal_val = manual_kategori_awal
    else:
        kategori_awal_val, _ = resolve_sub_kategori_awal(row)
    payload[ENTRY["sub_kategori_awal"]] = kategori_awal_val

    if manual_kategori_akhir:
        kategori_akhir_val = manual_kategori_akhir
    else:
        kategori_akhir_val, _ = map_category(row.get("Sub Kategori Akhir", ""))
    payload[ENTRY["sub_kategori_akhir"]] = kategori_akhir_val

    if manual_sbu:
        sbu_value = manual_sbu
    else:
        sbu_value, _ = resolve_sbu(row.get("SBU", ""))
    payload[ENTRY["sbu"]] = sbu_value

    skipped_fields = []

    sub_bidang_awal_val, skipped_awal = resolve_sub_bidang(row.get("SUB BIDANG AWAL", ""))
    payload[ENTRY["sub_bidang_awal"]] = sub_bidang_awal_val
    if skipped_awal:
        skipped_fields.append(f"SUB BIDANG AWAL ('{clean(row.get('SUB BIDANG AWAL',''))}' tidak valid)")

    sub_bidang_akhir_val, skipped_akhir = resolve_sub_bidang(row.get("SUB BIDANG AKHIR", ""))
    payload[ENTRY["sub_bidang_akhir"]] = sub_bidang_akhir_val
    if skipped_akhir:
        skipped_fields.append(f"SUB BIDANG AKHIR ('{clean(row.get('SUB BIDANG AKHIR',''))}' tidak valid)")

    payload[ENTRY["keterangan_tambahan"]] = clean(row.get("Keterangan Tambahan", ""))

    # Nama CSO Perbantuan selalu kosong di data -> dikirim string kosong
    # (bukan "0", karena "0" ikut tampil di hasil form padahal field ini
    # memang tidak dipakai untuk alur "Ticket Mutation From CSO")
    payload[ENTRY["nama_cso_perbantuan"]] = ""

    payload["fvv"] = "1"
    payload["pageHistory"] = "0"

    return payload, skipped_fields


# =====================================================
# SUBMIT
# =====================================================

def submit_form(session, payload):
    last_error = ""

    for attempt in range(3):
        try:
            response = session.post(
                FORM_URL,
                data=payload,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": FORM_URL.replace("formResponse", "viewform"),
                },
                timeout=60,
            )

            if response.status_code in [200, 302]:
                return True, ""

            last_error = f"HTTP {response.status_code}"

        except Exception as e:
            last_error = str(e)

        time.sleep(3)

    return False, last_error


# =====================================================
# UI
# =====================================================

st.set_page_config(page_title="MONIT Importer v2", layout="wide")
st.title("Excel → Google Form MONIT (Mutation)")

# Jam real-time (WIB) sebagai referensi saat isi Create Ticket date/time
# manual -- jalan sendiri tiap detik di browser, tidak perlu buka tab lain.
components.html(
    """
    <div id="live-clock-wib"
         style="font-family:sans-serif;font-size:1.4em;font-weight:600;
                color:#fafafa;padding:6px 0 12px 0;">
        Memuat jam...
    </div>
    <script>
    function updateLiveClock() {
        var now = new Date();
        var utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
        var wib = new Date(utcMs + 7 * 3600000); // WIB = UTC+7
        function pad(n) { return String(n).padStart(2, "0"); }
        var hh = pad(wib.getHours());
        var mm = pad(wib.getMinutes());
        var ss = pad(wib.getSeconds());
        var dd = pad(wib.getDate());
        var mo = pad(wib.getMonth() + 1);
        var yy = wib.getFullYear();
        document.getElementById("live-clock-wib").innerText =
            "🕒 " + dd + "/" + mo + "/" + yy + "  " + hh + ":" + mm + ":" + ss + " WIB";
    }
    setInterval(updateLiveClock, 1000);
    updateLiveClock();
    </script>
    """,
    height=45,
)

col1, col2 = st.columns(2)

with col1:
    if st.button("Reset Progress"):
        reset_progress()
        st.success("Progress berhasil direset")

with col2:
    st.info(f"Last Success Row : {load_progress()}")

min_delay = st.number_input("Min Delay", min_value=1, max_value=60, value=10)
max_delay = st.number_input("Max Delay", min_value=1, max_value=120, value=30)

file = st.file_uploader("Upload Excel", type=["xlsx"])

if file:
    df = pd.read_excel(file, engine="openpyxl")
    st.dataframe(df.head())

    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        st.error(f"Kolom tidak ditemukan: {missing_cols}")
        st.stop()

    st.write(f"Total Data : {len(df)}")

    # -------------------------------------------------
    # REVIEW QUEUE - SBU kosong / tanggal-jam kosong
    # -------------------------------------------------
    issues = build_review_queue(df)

    manual_sbu_map = {}
    manual_datetime_map = {}
    manual_kategori_awal_map = {}
    manual_kategori_akhir_map = {}

    known_sbu = SBU_OPTIONS
    known_kategori = sorted(set(CATEGORY_VALID_OPTIONS))
    LAINNYA = "-- Lainnya (ketik label persis dari form) --"

    if issues:
        st.warning(
            f"Ada {len(issues)} baris dengan data yang wajib diisi manual "
            f"sebelum import (SBU, tanggal tiket, dan/atau kategori yang tidak "
            f"dikenal tidak boleh dikarang / dikirim asal, karena Google Form "
            f"akan menolaknya - HTTP 400):"
        )

        for item in issues:
            idx = item["idx"]
            st.markdown(f"**Baris {idx + 1} — ID Ticket: {item['ID Ticket']}** ({', '.join(item['issues'])})")

            c1, c2, c3 = st.columns(3)

            sbu_bermasalah = "SBU kosong" in item["issues"] or any(
                i.startswith("SBU tidak dikenal") for i in item["issues"]
            )
            if sbu_bermasalah:
                with c1:
                    chosen_sbu = st.selectbox(
                        f"Pilih SBU (baris {idx + 1})",
                        options=[""] + known_sbu,
                        key=f"sbu_{idx}",
                    )
                    if chosen_sbu:
                        manual_sbu_map[idx] = chosen_sbu

            if "Create Ticket date/time kosong" in item["issues"]:
                now_jakarta = datetime.now(ZoneInfo("Asia/Jakarta"))
                with c2:
                    chosen_date = st.date_input(
                        f"Create Ticket date (baris {idx + 1})",
                        value=now_jakarta.date(),
                        key=f"date_{idx}",
                    )
                with c3:
                    time_text = st.text_input(
                        f"Create Ticket time (baris {idx + 1}) - format HH:MM",
                        value=now_jakarta.strftime("%H:%M"),
                        key=f"time_{idx}",
                    )
                    try:
                        chosen_time = datetime.strptime(time_text.strip(), "%H:%M").time()
                    except ValueError:
                        chosen_time = None
                        st.error(f"Format jam salah (baris {idx + 1}): pakai HH:MM, contoh 14:05")
                if chosen_time is not None:
                    manual_datetime_map[idx] = pd.to_datetime(
                        f"{chosen_date} {chosen_time}"
                    )

            if any(i.startswith("Sub Kategori Awal tidak dikenal") for i in item["issues"]):
                chosen = st.selectbox(
                    f"Pilih Sub Kategori Awal yang benar (baris {idx + 1})",
                    options=[""] + known_kategori + [LAINNYA],
                    key=f"kat_awal_{idx}",
                )
                if chosen == LAINNYA:
                    chosen = st.text_input(
                        f"Ketik label persis dari dropdown form (baris {idx + 1}, Sub Kategori Awal)",
                        key=f"kat_awal_manual_{idx}",
                    )
                if chosen:
                    manual_kategori_awal_map[idx] = chosen

            if any(i.startswith("Sub Kategori Akhir tidak dikenal") for i in item["issues"]):
                chosen = st.selectbox(
                    f"Pilih Sub Kategori Akhir yang benar (baris {idx + 1})",
                    options=[""] + known_kategori + [LAINNYA],
                    key=f"kat_akhir_{idx}",
                )
                if chosen == LAINNYA:
                    chosen = st.text_input(
                        f"Ketik label persis dari dropdown form (baris {idx + 1}, Sub Kategori Akhir)",
                        key=f"kat_akhir_manual_{idx}",
                    )
                if chosen:
                    manual_kategori_akhir_map[idx] = chosen

    all_resolved = all(
        (
            idx in manual_sbu_map
            or (
                "SBU kosong" not in item["issues"]
                and not any(i.startswith("SBU tidak dikenal") for i in item["issues"])
            )
        )
        and (idx in manual_datetime_map or "Create Ticket date/time kosong" not in item["issues"])
        and (
            idx in manual_kategori_awal_map
            or not any(i.startswith("Sub Kategori Awal tidak dikenal") for i in item["issues"])
        )
        and (
            idx in manual_kategori_akhir_map
            or not any(i.startswith("Sub Kategori Akhir tidak dikenal") for i in item["issues"])
        )
        for item in issues
        for idx in [item["idx"]]
    )

    if issues and not all_resolved:
        st.info("Lengkapi semua isian di atas dulu sebelum import bisa dimulai.")

    import_ready = (not issues) or all_resolved

    if import_ready and st.button("START IMPORT", disabled=not import_ready):
        start_row = load_progress()
        session = requests.Session()

        progress_bar = st.progress(0)
        status_box = st.empty()

        success = 0
        failed = 0

        for idx in range(start_row, len(df)):
            row = df.iloc[idx]

            payload, skipped_fields = build_payload(
                row,
                manual_sbu=manual_sbu_map.get(idx),
                manual_datetime=manual_datetime_map.get(idx),
            )

            ok, err = submit_form(session, payload)

            note = f" | dilewati: {'; '.join(skipped_fields)}" if skipped_fields else ""

            if ok:
                save_progress(idx + 1)
                success += 1
                status_box.success(f"✓ {row['ID Ticket']}{note}")
            else:
                failed += 1
                status_box.error(f"✗ {row['ID Ticket']} | {err}{note}")

            progress_bar.progress((idx + 1) / len(df))

            if idx < len(df) - 1:
                delay = random.randint(min_delay, max_delay)
                time.sleep(delay)

        st.success(f"\nImport selesai\n\nBerhasil : {success}\n\nGagal : {failed}\n")
