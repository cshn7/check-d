import os
import json
import time
import requests
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from oauth2client.service_account import ServiceAccountCredentials

# === KONFIGURASI ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")          # ID Spreadsheet
SHEET_NAME = os.getenv("SHEET_NAME", "TELEGRAM UPDATE") # Nama Sheet
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Token bot Telegram
CHAT_ID = os.getenv("CHAT_ID")                        # ID chat / grup
CHECK_URL = os.getenv("CHECK_URL")                    # URL halaman checker

# === AUTENTIKASI GOOGLE SHEETS ===
def get_google_client():
    creds_dict = json.loads(os.environ["GSPREAD_CREDENTIALS"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_domains_from_sheet():
    client = get_google_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    domains = sheet.col_values(2)  # Ambil kolom B
    return "\n".join(domains)

# === TELEGRAM ===
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram token/Chat ID tidak diset.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")

# === SELENIUM (HEADLESS CHROMIUM) ===
def create_driver():
    chrome_options = Options()
    chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN", "/usr/bin/google-chrome")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)

# === CEK DOMAIN ===
def check_domains():
    driver = create_driver()
    wait = WebDriverWait(driver, 15)

    try:
        driver.get(CHECK_URL)

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
        print("✅ Hasil dikirim ke Telegram.")

    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
        send_telegram_message("❌ Gagal melakukan pengecekan domain.")
    finally:
        driver.quit()

# === MAIN (single run) ===
if __name__ == "__main__":
    while True:
        check_domains()
        time.sleep(900)  # 15 menit
