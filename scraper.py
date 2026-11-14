"""
Lapisan 1: PENGAMBILAN DATA (Ingestion).
Engine Hybrid: Playwright (browser window visible) +
Smart Incremental Scroll + BeautifulSoup Universal Parser.
"""
import asyncio
import ctypes
import logging
import os
import random
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import config

log = logging.getLogger(__name__)


def _posisi_tengah_jendela(lebar_layar: int, tinggi_layar: int) -> tuple[int, int]:
    return (lebar_layar - 1366) // 2, (tinggi_layar - 768) // 2


def parse_harga(teks: str) -> float | None:
    """Mengubah format 'Rp15.499.000' atau 'Rp 850.000' menjadi 15499000.0"""
    if not teks:
        return None
    angka = re.sub(r"[^\d]", "", teks)
    return float(angka) if angka else None


def parse_terjual(teks: str) -> int:
    """Mengubah 'Terjual 1rb+' -> 1000, 'Terjual 250+' -> 250, '10rb+ terjual' -> 10000"""
    if not teks:
        return 0
    t = teks.lower().replace("+", "").replace("terjual", "").strip()
    m_rb = re.search(r"(\d+(?:[.,]\d+)?)\s*rb", t)
    if m_rb:
        return int(float(m_rb.group(1).replace(",", ".")) * 1000)
    m = re.search(r"\d+", t)
    return int(m.group()) if m else 0


def parse_rating(teks: str) -> float:
    """Mengubah '4.9' -> 4.9"""
    if not teks:
        return 0.0
    m = re.search(r"\d+(?:\.\d+)?", teks)
    return float(m.group()) if m else 0.0


def _sesuai_keyword(nama_produk: str, keyword: str) -> bool:
    """Memastikan semua kata dalam keyword muncul pada nama produk."""
    kata_kunci = set(re.findall(r"\w+", keyword.casefold()))
    kata_produk = set(re.findall(r"\w+", nama_produk.casefold()))
    return kata_kunci.issubset(kata_produk)


def parse_html_produk(html: str, keyword: str) -> list[dict]:
    """
    Universal Parser Tokopedia:
    - Strategi 1: Selektor semantik data-testid kartu produk (jika tersedia).
    - Strategi 2: Container link produk interaktif (tampilan live produksi Tokopedia).
    """
    soup = BeautifulSoup(html, "html.parser")
    hasil = []
    seen_urls = set()

    # Strategi 1: data-testid wrapper
    kartu_cards = soup.select('div[data-testid="master-product-card"]')
    if kartu_cards:
        for kartu in kartu_cards:
            link = kartu.select_one('a[href*="tokopedia.com"]')
            judul = kartu.select_one('div[data-testid="spnSRPProdName"], [class*="product-name"]')
            harga = kartu.select_one('div[data-testid="spnSRPProdPrice"], [class*="product-price"]')
            if not link or not judul or not harga:
                continue

            url = link["href"].split("?")[0]
            if url in seen_urls:
                continue

            p_harga = parse_harga(harga.get_text(strip=True))
            if not p_harga:
                continue

            nama_produk = judul.get_text(strip=True)
            # if not _sesuai_keyword(nama_produk, keyword):
            #     continue

            r_elem = kartu.select_one('span[data-testid="spnSRPProdRating"]')
            t_elem = kartu.select_one('span[data-testid="spnSRPProdSold"]')
            shop_elem = kartu.select_one('span[data-testid="spnSRPProdTabShopName"]')
            loc_elem = kartu.select_one('span[data-testid="spnSRPProdTabShopLoc"]')
            badge_elem = kartu.select_one('img[data-testid="imgSRPProdBadge"]')

            seen_urls.add(url)
            hasil.append({
                "url": url,
                "keyword": keyword.strip(),
                "nama_produk": nama_produk,
                "harga": p_harga,
                "harga_asli": None,
                "diskon_persen": 0,
                "rating": parse_rating(r_elem.get_text(strip=True) if r_elem else ""),
                "terjual": parse_terjual(t_elem.get_text(strip=True) if t_elem else ""),
                "toko": shop_elem.get_text(strip=True) if shop_elem else "Toko Penjual",
                "lokasi_toko": loc_elem.get_text(strip=True) if loc_elem else "Indonesia",
                "badge_toko": badge_elem.get("alt", "Official Store") if badge_elem else ("Official Store" if "official" in kartu.get_text().lower() else "Reguler"),
            })

        if hasil:
            return hasil

    # Strategi 2: Universal link wrapper extractor (untuk tampilan produksi Tokopedia saat ini)
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if not href.startswith("https://www.tokopedia.com/"):
            continue
        if any(x in href for x in ["/promo", "/help", "/discovery", "/cart", "/login", "/register", "/user", "/blog"]):
            continue
        if href in seen_urls:
            continue

        raw_text = a.get_text()
        if "Rp" not in raw_text:
            continue

        strings = [s.strip() for s in a.stripped_strings if s.strip()]
        if len(strings) < 2:
            continue

        nama_produk = None
        harga = None
        harga_asli = None
        diskon = 0
        rating = 0.0
        terjual = 0
        toko = "Toko Penjual"
        lokasi = "Indonesia"

        harga_indices = []
        for i, s in enumerate(strings):
            if s.startswith("Rp") or "Rp" in s:
                m = re.search(r"\d[\d\.]+", s)
                if m:
                    val = float(m.group().replace(".", ""))
                    harga_indices.append((i, val))

        if not harga_indices:
            continue

        harga = harga_indices[0][1]
        idx_harga = harga_indices[0][0]

        if len(harga_indices) > 1:
            harga_asli = harga_indices[1][1]

        kandidat_judul = [s for s in strings[:idx_harga] if not s.endswith("%") and len(s) > 10]
        if kandidat_judul:
            nama_produk = max(kandidat_judul, key=len)
        elif idx_harga > 0:
            nama_produk = strings[idx_harga - 1]
        else:
            nama_produk = strings[0]

        # if not _sesuai_keyword(nama_produk, keyword):
        #     continue

        for s in strings:
            if s.endswith("%"):
                m_disc = re.search(r"\d+", s)
                if m_disc:
                    diskon = int(m_disc.group())
            elif re.match(r"^[345]\.\d$", s):
                rating = float(s)
            elif "terjual" in s.lower():
                terjual = parse_terjual(s)

        sisa = strings[idx_harga + 1:]
        sisa_teks = [
            s for s in sisa
            if not s.startswith("Rp") and not s.endswith("%")
            and "terjual" not in s.lower()
            and not re.match(r"^[345]\.\d$", s)
            and "bonus" not in s.lower()
            and "cashback" not in s.lower()
            and "bebas ongkir" not in s.lower()
        ]
        if len(sisa_teks) >= 2:
            toko = sisa_teks[-2]
            lokasi = sisa_teks[-1]
        elif len(sisa_teks) == 1:
            lokasi = sisa_teks[0]

        seen_urls.add(href)
        hasil.append({
            "url": href,
            "keyword": keyword.strip(),
            "nama_produk": nama_produk,
            "harga": harga,
            "harga_asli": harga_asli,
            "diskon_persen": diskon,
            "rating": rating,
            "terjual": terjual,
            "toko": toko,
            "lokasi_toko": lokasi,
            "badge_toko": "Official Store" if "official" in raw_text.lower() else ("Power Merchant" if "power" in raw_text.lower() else "Reguler"),
        })

    return hasil


# ---------- Controller Browser Otomasi ----------
class TokopediaScraper:
    def __init__(self, headless: bool = config.HEADLESS):
        self.headless = headless

    async def _scroll_halaman(self, page):
        """Scroll bertahap agar lazy load produk terpicu sempurna."""
        for _ in range(4):
            await page.mouse.wheel(0, random.randint(600, 850))
            await asyncio.sleep(random.uniform(0.6, 1.0))

        # Cek tombol 'Muat Lebih Banyak' jika muncul
        try:
            pola_tombol = re.compile(r"Muat Lebih Banyak|Tampilkan Lebih Banyak|Lihat Lainnya", re.IGNORECASE)
            tombol = page.get_by_role("button", name=pola_tombol)
            if await tombol.count() > 0 and await tombol.first.is_visible():
                await tombol.first.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.4, 0.8))
                await tombol.first.click()
                log.info("Tombol 'Muat Lebih Banyak' diklik.")
                await asyncio.sleep(random.uniform(1.5, 2.2))

                for _ in range(4):
                    await page.mouse.wheel(0, random.randint(600, 850))
                    await asyncio.sleep(random.uniform(0.6, 1.0))
        except Exception:
            pass

        await asyncio.sleep(1.0)

    async def ambil_keyword(
        self,
        keyword: str,
        halaman_maks: int = config.DEFAULT_PAGES,
        raw: bool = False,
        pmin: float | None = None,
        pmax: float | None = None
    ) -> list[dict] | list[str]:
        semua_produk = []
        semua_html = []
        seen_urls = set()
        log.info("Memulai scraping untuk keyword '%s' (maks %d halaman)", keyword, halaman_maks)

        if os.name == "nt":
            lebar_layar = ctypes.windll.user32.GetSystemMetrics(0)
            tinggi_layar = ctypes.windll.user32.GetSystemMetrics(1)
        else:
            lebar_layar, tinggi_layar = 1366, 768
        posisi_x, posisi_y = _posisi_tengah_jendela(lebar_layar, tinggi_layar)

        launch_args = [
            f"--window-position={posisi_x},{posisi_y}",
            "--window-size=1366,768",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

        async with async_playwright() as p:
            # Gunakan launch_persistent_context agar cookie & session Tokopedia tersimpan permanen
            if hasattr(p.chromium, "launch_persistent_context"):
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(config.BROWSER_PROFILE_DIR),
                    headless=False,
                    args=launch_args,
                    locale="id-ID",
                    timezone_id="Asia/Jakarta",
                    viewport={"width": 1366, "height": 768},
                    user_agent=config.USER_AGENT,
                )
                page = context.pages[0] if hasattr(context, "pages") and context.pages else await context.new_page()
                close_target = context
            else:
                browser = await p.chromium.launch(headless=self.headless, args=launch_args)
                context = await browser.new_context(
                    locale="id-ID",
                    timezone_id="Asia/Jakarta",
                    viewport={"width": 1366, "height": 768},
                    user_agent=config.USER_AGENT,
                )
                page = await context.new_page()
                close_target = browser

            await Stealth().apply_stealth_async(page)

            url = config.buat_url_pencarian(keyword, pmin, pmax)
            log.info("Navigasi ke: %s", url)

            try:
                await page.goto(url, wait_until="load", timeout=35000)
                # Beri jeda 3.5 - 4.5 detik agar React SPA Tokopedia selesai merender kartu produk
                await asyncio.sleep(random.uniform(3.5, 4.5))

                seen_urls = set()
                for putaran in range(1, halaman_maks + 1):
                    await self._scroll_halaman(page)

                    if raw:
                        continue

                    html = await page.content()
                    produk_hal = parse_html_produk(html, keyword)
                    produk_baru = [p for p in produk_hal if p["url"] not in seen_urls]
                    seen_urls.update(p["url"] for p in produk_baru)
                    semua_produk.extend(produk_baru)
                    log.info("Putaran scroll %d: %d produk baru, total %d", putaran, len(produk_baru), len(semua_produk))

                    if putaran < halaman_maks:
                        await asyncio.sleep(random.uniform(config.JEDA_MIN, config.JEDA_MAX))

                if raw:
                    semua_html.append(await page.content())

            except Exception as e:
                log.error("Gagal mengambil hasil untuk '%s': %s", keyword, e)

            await close_target.close()

        log.info("Scraping '%s' selesai: Total %d produk terkumpul", keyword, len(semua_produk))
        return semua_html if raw else semua_produk

    def jalankan(
        self,
        keywords: list[str],
        halaman_maks: int = config.DEFAULT_PAGES,
        raw: bool = False,
        pmin: float | None = None,
        pmax: float | None = None
    ) -> list[dict] | list[str]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            semua = []
            for kw in keywords:
                data = loop.run_until_complete(self.ambil_keyword(kw, halaman_maks, raw, pmin, pmax))
                semua.extend(data)
            return semua
        finally:
            loop.close()
