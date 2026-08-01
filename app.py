import streamlit as st
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
    DEFAULT_SUB_KATEGORI_AWAL,
    SUB_BIDANG_VALID_OPTIONS,
    SUB_BIDANG_ALIAS,
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
# PICKUP TIME CHAIN (persis logika app.py lama)
# =====================================================

if "last_submit_time" not in st.session_state:
    st.session_state.last_submit_time = None


def get_pickup_time():
    now = datetime.now(ZoneInfo("Asia/Jakarta"))

    if st.session_state.last_submit_time is None:
        pickup = now - timedelta(seconds=random.randint(20, 40))
    else:
        pickup = st.session_state.last_submit_time + timedelta(
            seconds=random.randint(1, 10)
        )

    st.session_state.last_submit_time = pickup
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


def map_category(raw_value):
    """Terjemahkan nilai mentah Excel ke label dropdown Google Form."""
    raw_value = clean(raw_value)
    if raw_value == "":
        return ""
    # Buang prefix "GANGGUAN - " kalau ada (format kolom Sub Kategori Akhir)
    normalized = raw_value.replace("GANGGUAN - ", "").strip()
    return CATEGORY_MAP.get(normalized, raw_value)


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
      - SBU kosong        -> perlu pilih dari daftar SBU valid (bukan random)
      - Create Ticket date/time kosong -> perlu isi tanggal & jam yang benar
    Field lain yang boleh kosong (SUB BIDANG AWAL/AKHIR, Keterangan Tambahan)
    tidak masuk sini karena memang tidak wajib.
    """
    issues = []
    for idx, row in df.iterrows():
        row_issues = []
        if clean(row.get("SBU", "")) == "":
            row_issues.append("SBU kosong")
        if resolve_create_datetime(row) is None:
            row_issues.append("Create Ticket date/time kosong")
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

def build_payload(row, manual_sbu=None, manual_datetime=None):
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

    payload[ENTRY["sub_kategori_awal"]] = resolve_sub_kategori_awal(row)
    payload[ENTRY["sub_kategori_akhir"]] = map_category(row.get("Sub Kategori Akhir", ""))

    sbu_value = manual_sbu if manual_sbu else clean(row.get("SBU", ""))
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

    known_sbu = sorted(df["SBU"].dropna().unique().tolist())

    if issues:
        st.warning(
            f"Ada {len(issues)} baris dengan data yang wajib diisi manual "
            f"sebelum import (SBU dan/atau tanggal tiket tidak boleh dikarang):"
        )

        for item in issues:
            idx = item["idx"]
            st.markdown(f"**Baris {idx + 1} — ID Ticket: {item['ID Ticket']}** ({', '.join(item['issues'])})")

            c1, c2, c3 = st.columns(3)

            if "SBU kosong" in item["issues"]:
                with c1:
                    chosen_sbu = st.selectbox(
                        f"Pilih SBU (baris {idx + 1})",
                        options=[""] + known_sbu,
                        key=f"sbu_{idx}",
                    )
                    if chosen_sbu:
                        manual_sbu_map[idx] = chosen_sbu

            if "Create Ticket date/time kosong" in item["issues"]:
                with c2:
                    chosen_date = st.date_input(
                        f"Create Ticket date (baris {idx + 1})",
                        key=f"date_{idx}",
                    )
                with c3:
                    chosen_time = st.time_input(
                        f"Create Ticket time (baris {idx + 1})",
                        key=f"time_{idx}",
                    )
                manual_datetime_map[idx] = pd.to_datetime(
                    f"{chosen_date} {chosen_time}"
                )

    all_resolved = all(
        (idx in manual_sbu_map or "SBU kosong" not in item["issues"])
        and (idx in manual_datetime_map or "Create Ticket date/time kosong" not in item["issues"])
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
