import os
import json
import time
import socket
import threading
import requests
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === LOGGING TERPUSAT ===
def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

# === PORT DUMMY (Render Free Plan Web Service) ===
def open_dummy_port(port=10000):
    s = socket.socket()
    s.bind(("0.0.0.0", port))
    s.listen()
    log(f"🔹 Dummy port {port} terbuka untuk Render Web Service")
    while True:
        conn, _ = s.accept()
        conn.close()

threading.Thread(target=open_dummy_port, daemon=True).start()

# === KONFIGURASI ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "TELEGRAM UPDATE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_URL = os.getenv("CHECK_URL")

# === AUTENTIKASI GOOGLE SHEETS ===
def get_google_client():
    creds_dict = json.loads(os.environ["GSPREAD_CREDENTIALS"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_domains_from_sheet():
    client = get_google_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    domains = sheet.col_values(2)
    return "\n".join(domains)

# === TELEGRAM ===
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        log("⚠️ Telegram token/Chat ID tidak diset.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        requests.post(url, data=data, timeout=10)
        log("✅ Pesan Telegram berhasil dikirim")
    except Exception as e:
        log(f"❌ Gagal kirim Telegram: {e}")

# === SELENIUM (HEADLESS CHROMIUM) ===
def create_driver():
    chrome_options = Options()
    chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN", "/usr/bin/chromium")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# === CEK DOMAIN ===
def check_domains(initial_run=False):
    driver = None
    try:
        log("🔹 ===== Mulai cek domain =====")

        # Ambil domain
        try:
            domain_list = get_domains_from_sheet()
            if not domain_list.strip():
                log("⚠️ Tidak ada domain di spreadsheet!")
                if initial_run:
                    send_telegram_message("⚠️ Tidak ada domain di spreadsheet!")
                return
            log(f"✅ Domain berhasil diambil ({len(domain_list.splitlines())} domain)")
        except Exception as e:
            log(f"❌ Gagal ambil domain dari spreadsheet: {e}")
            if initial_run:
                send_telegram_message("❌ Gagal ambil domain dari spreadsheet.")
            return

        # Buat driver & buka halaman checker
        try:
            driver = create_driver()
            driver.get(CHECK_URL)
            log(f"✅ Halaman checker berhasil dibuka: {CHECK_URL}")
        except Exception as e:
            log(f"❌ Gagal membuka halaman checker: {e}")
            if initial_run:
                send_telegram_message("❌ Gagal membuka halaman checker.")
            if driver:
                driver.quit()
            return

        wait = WebDriverWait(driver, 15)

        # Isi form & submit
        try:
            domain_input = wait.until(EC.presence_of_element_located((By.ID, "domains")))
            domain_input.clear()
            domain_input.send_keys(domain_list)
            log("✅ Domain berhasil diisi di textarea")

            check_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            check_button.click()
            log("✅ Tombol submit diklik")
        except Exception as e:
            log(f"❌ Gagal isi form / klik submit: {e}")
            if initial_run:
                send_telegram_message("❌ Gagal submit form di checker.")
            return

        # Ambil hasil tabel
        try:
            table_rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.min-w-full tbody tr")))
            log(f"✅ Hasil tabel ditemukan ({len(table_rows)} baris)")
        except Exception as e:
            log(f"❌ Gagal mengambil hasil tabel: {e}")
            if initial_run:
                send_telegram_message("❌ Gagal mengambil hasil tabel.")
            return

        # Format & kirim hasil
        try:
            results = "\n".join([
                "+----------------------------+---------------------+",
                "| DOMAIN                     | RESULT              |",
                "+----------------------------+---------------------+"
            ])
            blocked_count = 0

            for row in table_rows:
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) >= 2:
                    domain = columns[0].text.strip()
                    status = columns[1].text.strip()
                    if status.lower() == "not blocked":
                        status = "✅NOT BLOCKED✅"
                    elif status.lower() == "blocked":
                        status = "❌BLOCKED❌"
                        blocked_count += 1
                    results += f"\n| {domain.ljust(28)} | {status.ljust(19)} |"

            results += "\n+----------------------------+---------------------+"
            header_status = f"\\[ {blocked_count} \\] BLOCKED ❌" if blocked_count > 0 else "\\[ 0 \\] NOT BLOCKED ✅"
            full_message = f"{header_status}\n\n```{results}```"

            send_telegram_message(full_message)
            log("✅ Hasil pengecekan dikirim ke Telegram")
        except Exception as e:
            log(f"❌ Gagal format/kirim Telegram: {e}")
            if initial_run:
                send_telegram_message("❌ Gagal format/kirim hasil pengecekan domain.")

        log("🔹 ===== Selesai cek domain =====\n")

    finally:
        if driver:
            driver.quit()

# === MAIN LOOP (langsung kirim laporan pertama) ===
if __name__ == "__main__":
    log("🚀 Bot starting... laporan pertama segera dikirim")
    check_domains(initial_run=True)  # Kirim laporan pertama tanpa tunggu
    while True:
        try:
            log("⌛ Menunggu 15 menit untuk pengecekan berikutnya...")
            time.sleep(900)
            check_domains()
        except Exception as e:
            log(f"⚠️ Terjadi error utama: {e}")
