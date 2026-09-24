import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import requests
from dotenv import load_dotenv

# ============================================================
# CONFIG WEBSITE
# ============================================================

BASE_URL = "https://csm01.easdroid.com/cscmdashboard"
LOGIN_URL = f"{BASE_URL}/login.php"
REPORT_URL = f"{BASE_URL}/pages/rptData.php"

# ============================================================
# JENIS DATA YANG TERSEDIA
# ============================================================

DATA_TYPES = {
    6: "PRSP",
    7: "PRSP_UNIT",
    8: "SPK",
    9: "SPK_UNIT",
    10: "SPK_KELUARGA",
    11: "LSNG",
}

# ============================================================
# LOKASI PENYIMPANAN
# ============================================================

OUTPUT_DIRS = {
    "PRSP": Path(r"D:\H1\PBI\PBI\STAR\db_star_PRSP"),
    "PRSP_UNIT": Path(r"D:\H1\PBI\PBI\STAR\db_star_PRSP_UNIT"),
    "SPK": Path(r"D:\H1\PBI\PBI\STAR\db_star_SPK"),
    "SPK_UNIT": Path(r"D:\H1\PBI\PBI\STAR\db_star_SPK UNIT"),
    "SPK_KELUARGA": Path(r"D:\H1\PBI\PBI\STAR\db_star_SPK KELUARGA"),
    "LSNG": Path(r"D:\H1\PBI\PBI\STAR\db_star_LSNG"),
}

# ============================================================
# ENV
# ============================================================

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# ============================================================
# USER AGENT
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

# ============================================================
# SESSION
# ============================================================

def create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT
    })
    return session

# ============================================================
# LOGIN
# ============================================================

def login(session):

    if not USERNAME:
        raise RuntimeError(
            "USERNAME belum ditemukan di file .env"
        )

    if not PASSWORD:
        raise RuntimeError(
            "PASSWORD belum ditemukan di file .env"
        )

    print()
    print("=" * 65)
    print("LOGIN")
    print("=" * 65)

    # Browser menggunakan multipart/form-data.
    files = {
        "USERNAME": (None, USERNAME),
        "PASSWORD": (None, PASSWORD),
        "login": (None, ""),
    }

    headers = {
        "Origin": "https://csm01.easdroid.com",
        "Referer": f"{BASE_URL}/",
    }

    response = session.post(
        LOGIN_URL,
        params={"act": "in"},
        files=files,
        headers=headers,
        allow_redirects=True,
        timeout=60,
    )

    response.raise_for_status()

    # Cek PHP session
    phpsessid = session.cookies.get("PHPSESSID")

    if not phpsessid:
        raise RuntimeError(
            "PHPSESSID tidak ditemukan. Login kemungkinan gagal."
        )

    print(f"Login berhasil sebagai: {USERNAME}")

# ============================================================
# CEK TANGGAL
# ============================================================

def validate_date(date_string):

    try:
        datetime.strptime(
            date_string,
            "%d-%m-%Y"
        )

        return True
    except ValueError:
        return False

# ============================================================
# INPUT TANGGAL
# ============================================================

def ask_date(label, default):

    while True:

        value = input(
            f"{label} [{default}]: "
        ).strip()

        if not value:
            value = default

        if validate_date(value):
            return value

        print(
            "Format tanggal salah. "
            "Gunakan DD-MM-YYYY."
        )

# ============================================================
# PILIH JENIS DATA
# ============================================================

def choose_types():

    print()
    print("=" * 65)
    print("PILIH JENIS DATA")
    print("=" * 65)
    print("0. SEMUA")

    for number, jenis in DATA_TYPES.items():
        print(
            f"{number}. {jenis}"
        )

    while True:
        choice = input(
            "\nPilihan "
            "(contoh: 6,8,11) [0 = SEMUA]: "
        ).strip()

        if not choice:

            choice = "0"

        # ----------------------------------------------------
        # PILIH SEMUA
        # ----------------------------------------------------

        if choice == "0":

            return list(
                DATA_TYPES.values()
            )

        try:

            numbers = [
                int(x.strip())
                for x in choice.split(",")
                if x.strip()
            ]

        except ValueError:

            print(
                "Format salah. "
                "Contoh: 6,8,11"
            )

            continue
        # ----------------------------------------------------
        # CEK NOMOR VALID
        # ----------------------------------------------------

        invalid_numbers = [
            number
            for number in numbers
            if number not in DATA_TYPES
        ]

        if invalid_numbers:

            print(
                f"Pilihan tidak valid: "
                f"{invalid_numbers}"
            )

            print(
                "Gunakan hanya nomor 6 sampai 11."
            )
            continue

        # ----------------------------------------------------
        # HILANGKAN DUPLIKAT
        # ----------------------------------------------------

        numbers = list(
            dict.fromkeys(numbers)
        )
        # ----------------------------------------------------
        # HASIL PILIHAN
        # ----------------------------------------------------

        selected_types = [
            DATA_TYPES[number]
            for number in numbers
        ]
        return selected_types

# ============================================================
# LOKASI OUTPUT
# ============================================================

def get_output_dir(jenis):
    jenis = jenis.upper()
    if jenis not in OUTPUT_DIRS:
        raise RuntimeError(
            f"Folder untuk {jenis} belum dikonfigurasi."
        )
    output_dir = OUTPUT_DIRS[jenis]
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )
    return output_dir

# ============================================================
# AMBIL NAMA FILE DARI SERVER
# ============================================================

def extract_filename(
    content_disposition,
    jenis,
    tanggal_from,
    tanggal_to
):
    if content_disposition:
        match = re.search(
            r'filename\s*=\s*(?:"([^"]+)"|([^;]+))',
            content_disposition,
            flags=re.IGNORECASE
        )
        if match:
            filename = (
                match.group(1)
                or match.group(2)
            ).strip()
            if filename:
                return filename

    # Fallback jika server tidak memberikan nama file

    return (
        f"CSCM - "
        f"{jenis} "
        f"{tanggal_from} - "
        f"{tanggal_to}.csv"
    )

# ============================================================
# BERSIHKAN NAMA FILE
# ============================================================

def safe_filename(filename):
    return re.sub(
        r'[<>:"/\\|?*]',
        "_",
        filename
    )

# ============================================================
# DOWNLOAD CSV
# ============================================================

def download_csv(
    session,
    jenis,
    tanggal_from,
    tanggal_to
):
    print()
    print("-" * 65)
    print(
        f"Download {jenis}"
    )
    print("-" * 65)

    params = {
        "act": "inputdata",
        "searchtype": jenis,
        "inputTanggal": tanggal_from,
        "inputTanggal2": tanggal_to,
        "submit": "",
    }

    headers = {
        "Referer": (
            f"{BASE_URL}/pages/"
            "dashboard_rpt_datastg.php"
        ),
    }

    response = session.get(
        REPORT_URL,
        params=params,
        headers=headers,
        timeout=300,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    content_disposition = response.headers.get(
        "Content-Disposition",
        ""
    )

    print(
        f"Status       : "
        f"{response.status_code}"
    )

    print(
        f"Content-Type : "
        f"{content_type}"
    )
    # --------------------------------------------------------
    # DETEKSI LOGIN/SESSION EXPIRED
    # --------------------------------------------------------

    if "text/html" in content_type:

        raise RuntimeError(
            "Server mengembalikan HTML "
            "bukan CSV. "
            "Kemungkinan session login tidak valid."
        )
    # --------------------------------------------------------
    # AMBIL NAMA FILE
    # --------------------------------------------------------
    filename = extract_filename(
        content_disposition,
        jenis,
        tanggal_from,
        tanggal_to
    )
    filename = safe_filename(
        filename
    )
    # --------------------------------------------------------
    # FOLDER
    # --------------------------------------------------------
    output_dir = get_output_dir(
        jenis
    )
    # --------------------------------------------------------
    # PATH FILE
    # --------------------------------------------------------
    output_file = (
        output_dir / filename
    )
    # --------------------------------------------------------
    # SIMPAN
    # --------------------------------------------------------
    output_file.write_bytes(
        response.content
    )
    return (
        output_file,
        len(response.content)
    )

# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 65)
    print("CSCM DATA DOWNLOADER")
    print("=" * 65)

    # --------------------------------------------------------
    # DEFAULT = HARI KEMARIN
    # --------------------------------------------------------

    yesterday = (
        datetime.now()
        - timedelta(days=1)
    ).strftime("%d-%m-%Y")

    # --------------------------------------------------------
    # TANGGAL
    # --------------------------------------------------------

    tanggal_from = ask_date(
        "Tanggal FROM",
        yesterday
    )

    tanggal_to = ask_date(
        "Tanggal TO",
        yesterday
    )

    # --------------------------------------------------------
    # VALIDASI RENTANG
    # --------------------------------------------------------

    if tanggal_from > tanggal_to:

        print()
        print(
            "ERROR: "
            "Tanggal FROM tidak boleh "
            "lebih besar dari TO."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # PILIH DATA
    # --------------------------------------------------------

    jenis_list = choose_types()

    # --------------------------------------------------------
    # TAMPILKAN RINGKASAN
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("RINGKASAN")
    print("=" * 65)

    print(
        f"FROM : {tanggal_from}"
    )

    print(
        f"TO   : {tanggal_to}"
    )

    print(
        f"DATA : {', '.join(jenis_list)}"
    )

    print()
    print("LOKASI PENYIMPANAN:")

    for jenis in jenis_list:

        output_dir = get_output_dir(
            jenis
        )

        print(
            f"  {jenis:<15} -> "
            f"{output_dir}"
        )

    # --------------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------------

    session = create_session()

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    try:

        login(session)

    except Exception as exc:

        print()
        print(
            f"LOGIN ERROR: {exc}"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    success = 0
    failed = 0

    print()
    print("=" * 65)
    print("PROSES DOWNLOAD")
    print("=" * 65)

    for jenis in jenis_list:

        try:

            output_file, size = (
                download_csv(
                    session=session,
                    jenis=jenis,
                    tanggal_from=tanggal_from,
                    tanggal_to=tanggal_to,
                )
            )

            print(
                f"  BERHASIL : "
                f"{output_file}"
            )

            print(
                f"  SIZE     : "
                f"{size:,} bytes"
            )

            success += 1

        except Exception as exc:

            print(
                f"  GAGAL    : "
                f"{jenis}"
            )

            print(
                f"  ERROR    : "
                f"{exc}"
            )

            failed += 1
    # --------------------------------------------------------
    # HASIL AKHIR
    # --------------------------------------------------------
    print()
    print("=" * 65)
    print("SELESAI")
    print("=" * 65)

    print(
        f"Berhasil : {success}"
    )

    print(
        f"Gagal    : {failed}"
    )

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    main()