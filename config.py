"""
Pengaturan konfigurasi terpusat untuk Bot Telegram Intelijen Pasar Tokopedia.
Nilai rahasia dibaca dari file .env.
"""
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Muat variabel lingkungan dari .env jika tersedia
load_dotenv()

# Lokasi direktori proyek
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Database SQLite & Profil Browser Persisten
DB_PATH = DATA_DIR / "tokopedia_pasar.db"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# URL Dasar & Format Pencarian Tokopedia
BASE_URL = "https://www.tokopedia.com"
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Header otentik untuk mengeliminasi fingerprint 'HeadlessChrome' di HTTP/2
DEFAULT_HEADERS = {
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "upgrade-insecure-requests": "1",
    "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Konfigurasi Scraping
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
# DEFAULT_PAGES dipertahankan untuk kompatibilitas; nilainya adalah putaran scroll.
DEFAULT_PAGES = int(os.getenv("DEFAULT_PAGES", "2"))
JEDA_MIN = float(os.getenv("JEDA_MIN", "2.5"))
JEDA_MAX = float(os.getenv("JEDA_MAX", "4.5"))

raw_kw = os.getenv("DEFAULT_KEYWORDS", "iphone 15,keyboard mechanical,tws anc")
DEFAULT_KEYWORDS = [k.strip() for k in raw_kw.split(",") if k.strip()]

# Konfigurasi Bot Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
JAM_JADWAL = os.getenv("JAM_JADWAL", "08:00")


def buat_url_pencarian(
    keyword: str,
    pmin: float | None = None,
    pmax: float | None = None
) -> str:
    """
    Format pencarian resmi Tokopedia dengan st=product (fokus katalog produk utama)
    tanpa parameter page (menggunakan model infinite scroll).
    """
    kw_encoded = quote_plus(keyword.strip())
    url = f"https://www.tokopedia.com/search?st=product&q={kw_encoded}"
    if pmin is not None and pmin > 0:
        url += f"&pmin={int(pmin)}"
    if pmax is not None and pmax > 0:
        url += f"&pmax={int(pmax)}"
    return url
