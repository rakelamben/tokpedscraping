"""
Unit test parser scraper Tokopedia.
Berjalan offline tanpa koneksi internet.
"""
import asyncio

from scraper import parse_harga, parse_terjual, parse_rating, parse_html_produk
from scraper import TokopediaScraper, _posisi_tengah_jendela
from config import buat_url_pencarian


def test_parse_harga():
    assert parse_harga("Rp13.999.000") == 13999000.0
    assert parse_harga("Rp 850.000") == 850000.0
    assert parse_harga("Rp25.000") == 25000.0
    assert parse_harga("") is None
    assert parse_harga(None) is None


def test_parse_terjual():
    assert parse_terjual("Terjual 1rb+") == 1000
    assert parse_terjual("Terjual 2.5rb+") == 2500
    assert parse_terjual("500+ terjual") == 500
    assert parse_terjual("Terjual 25") == 25
    assert parse_terjual("Baru") == 0
    assert parse_terjual("") == 0


def test_parse_rating():
    assert parse_rating("4.9") == 4.9
    assert parse_rating("5.0") == 5.0
    assert parse_rating("4.75") == 4.75
    assert parse_rating("") == 0.0


def test_parse_html_produk(sample_html):
    produk = parse_html_produk(sample_html, "iphone 15")
    assert len(produk) == 3

    p1 = produk[0]
    assert p1["nama_produk"] == "Apple iPhone 15 128GB Garansi Resmi iBox"
    assert p1["harga"] == 13999000.0
    assert p1["rating"] == 4.9
    assert p1["terjual"] == 1000
    assert p1["lokasi_toko"] == "Jakarta Pusat"
    assert p1["toko"] == "Apple Official Store"
    assert p1["badge_toko"] == "Official Store"
    assert p1["url"] == "https://www.tokopedia.com/tokoapple/iphone-15-128gb-garansi-resmi"

    p2 = produk[1]
    assert p2["nama_produk"] == "Case Casing Bening iPhone 15 Anti Crack"
    assert p2["harga"] == 25000.0
    assert p2["terjual"] == 500


def test_parse_html_produk_membuang_produk_tanpa_semua_kata_keyword():
    html = """
    <div data-testid="master-product-card">
        <a href="https://www.tokopedia.com/shop/iphone-15">
            <div data-testid="spnSRPProdName">iPhone 15</div>
        </a>
        <div data-testid="spnSRPProdPrice">Rp15.000.000</div>
    </div>
    <div data-testid="master-product-card">
        <a href="https://www.tokopedia.com/shop/phone-case">
            <div data-testid="spnSRPProdName">Phone Case</div>
        </a>
        <div data-testid="spnSRPProdPrice">Rp50.000</div>
    </div>
    """

    produk = parse_html_produk(html, "iphone 15")

    assert [item["nama_produk"] for item in produk] == ["iPhone 15"]


def test_buat_url_pencarian_tidak_menggunakan_parameter_page():
    url = buat_url_pencarian("iphone 15")

    assert "q=iphone+15" in url
    assert "page=" not in url


def test_posisi_jendela_browser_dihitung_ke_tengah_layar():
    assert _posisi_tengah_jendela(1920, 1080) == (277, 156)


def test_ambil_keyword_menggunakan_satu_url_dan_menggabungkan_scroll(
    monkeypatch, sample_html
):
    class Locator:
        async def count(self):
            return 0

    class Page:
        def __init__(self):
            self.urls = []
            self.jumlah_scroll = 0
            self.mouse = self

        async def goto(self, url, **kwargs):
            self.urls.append(url)

        async def wheel(self, x, y):
            self.jumlah_scroll += 1

        def get_by_role(self, *args, **kwargs):
            return Locator()

        async def content(self):
            return sample_html

    class Context:
        async def new_page(self):
            return page

    class Browser:
        async def new_context(self, **kwargs):
            return Context()

        async def close(self):
            pass

    class Chromium:
        async def launch(self, **kwargs):
            return Browser()

    class PlaywrightManager:
        async def __aenter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        async def __aexit__(self, *args):
            pass

    class StealthStub:
        async def apply_stealth_async(self, page):
            pass

    page = Page()

    async def no_wait(_):
        pass

    monkeypatch.setattr("scraper.async_playwright", PlaywrightManager)
    monkeypatch.setattr("scraper.Stealth", StealthStub)
    monkeypatch.setattr("scraper.asyncio.sleep", no_wait)
    monkeypatch.setattr("scraper.random.uniform", lambda lower, upper: 0.1)
    monkeypatch.setattr("scraper.random.randint", lambda lower, upper: 700)

    produk = asyncio.run(TokopediaScraper().ambil_keyword("iphone 15", halaman_maks=2))

    assert len(page.urls) == 1
    assert "page=" not in page.urls[0]
    assert page.jumlah_scroll == 8
    assert len(produk) == 3
