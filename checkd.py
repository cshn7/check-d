import os
import json
import time
import requests
import gspread
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from oauth2client.service_account import ServiceAccountCredentials
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# === LOGGING ===
LOG_FILE = "checker.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# === KONFIGURASI ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "TELEGRAM UPDATE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_URL = os.getenv("CHECK_URL")

# === AUTENTIKASI GOOGLE SHEETS ===
def get_google_client():
    try:
        creds_dict = json.loads(os.environ["GSPREAD_CREDENTIALS"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Error autentikasi Google Sheets: {e}")
        raise

def get_domains_from_sheet():
    try:
        client = get_google_client()
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        domains = sheet.col_values(2)
        logging.info(f"{len(domains)} domain berhasil diambil dari sheet")
        return "\n".join(domains)
    except Exception as e:
        logging.error(f"Gagal mengambil domain dari sheet: {e}")
        raise

# === TELEGRAM ===
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        logging.warning("Telegram token/Chat ID tidak diset.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        requests.post(url, data=data, timeout=10)
        logging.info("Pesan Telegram terkirim")
    except Exception as e:
        logging.error(f"Gagal kirim Telegram: {e}")

# === SELENIUM (HEADLESS CHROMIUM) ===
def create_driver():
    try:
        chrome_options = Options()
        chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN", "/usr/bin/chromium")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("Chromium driver berhasil dibuat")
        return driver
    except Exception as e:
        logging.error(f"Gagal membuat driver: {e}")
        raise

# === CEK DOMAIN ===
def check_domains():
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 15)
        driver.get(CHECK_URL)
        logging.info(f"Membuka halaman: {CHECK_URL}")

        # Ambil domain dari Google Sheets
        domain_list = get_domains_from_sheet()

        # Isi textarea
        domain_input = wait.until(EC.presence_of_element_located((By.ID, "domains")))
        domain_input.clear()
        domain_input.send_keys(domain_list)
        time.sleep(1)

        # Klik tombol submit
        check_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        check_button.click()

        # Tunggu hasil
        table_rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.min-w-full tbody tr")))

        # Format hasil
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
        logging.info("Hasil cek domain berhasil dikirim ke Telegram")

    except Exception as e:
        logging.error(f"Terjadi kesalahan saat cek domain: {e}")
        send_telegram_message(f"❌ Gagal melakukan pengecekan domain: {e}")
    finally:
        if driver:
            driver.quit()
            logging.info("Chromium driver ditutup")

# === LOOP UTAMA (15 MENIT) ===
def run_loop():
    while True:
        try:
            check_domains()
        except Exception as e:
            logging.error(f"⚠️ Terjadi error di loop: {e}")
        time.sleep(900)

# === DUMMY HTTP SERVER agar Render tidak complain port ===
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Domain Checker Worker Running\n")

def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    logging.info(f"HTTP server listening on port {port}")
    server.serve_forever()

# === MAIN ===
if __name__ == "__main__":
    # Jalankan loop domain checker di thread terpisah
    Thread(target=run_loop, daemon=True).start()
    # Jalankan HTTP server untuk Render
    start_http_server()
