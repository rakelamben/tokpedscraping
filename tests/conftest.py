"""
Fixtures dan data uji untuk pengujian offline pytest.
"""
import pytest

SAMPLE_HTML_TOKOPEDIA = """
<html>
<body>
<div data-testid="master-product-card">
    <a href="https://www.tokopedia.com/tokoapple/iphone-15-128gb-garansi-resmi?extParam=src%3Dsearch">
        <div data-testid="spnSRPProdName">Apple iPhone 15 128GB Garansi Resmi iBox</div>
    </a>
    <div data-testid="spnSRPProdPrice">Rp13.999.000</div>
    <span data-testid="spnSRPProdRating">4.9</span>
    <span data-testid="spnSRPProdSold">Terjual 1rb+</span>
    <span data-testid="spnSRPProdTabShopLoc">Jakarta Pusat</span>
    <span data-testid="spnSRPProdTabShopName">Apple Official Store</span>
    <img data-testid="imgSRPProdBadge" alt="Official Store" src="badge.png" />
</div>
<div data-testid="master-product-card">
    <a href="https://www.tokopedia.com/caseshop/casing-case-iphone-15-bening-clear">
        <div data-testid="spnSRPProdName">Case Casing Bening iPhone 15 Anti Crack</div>
    </a>
    <div data-testid="spnSRPProdPrice">Rp25.000</div>
    <span data-testid="spnSRPProdRating">4.7</span>
    <span data-testid="spnSRPProdSold">500+ terjual</span>
    <span data-testid="spnSRPProdTabShopLoc">Jakarta Barat</span>
    <span data-testid="spnSRPProdTabShopName">Case Shop Official</span>
    <img data-testid="imgSRPProdBadge" alt="Power Merchant Pro" src="badge2.png" />
</div>
<div data-testid="master-product-card">
    <a href="https://www.tokopedia.com/gadgetzone/iphone-15-256gb-inter-all-operator">
        <div data-testid="spnSRPProdName">Apple iPhone 15 256GB All Operator</div>
    </a>
    <div data-testid="spnSRPProdPrice">Rp12.499.000</div>
    <span data-testid="spnSRPProdRating">4.8</span>
    <span data-testid="spnSRPProdSold">Terjual 250+</span>
    <span data-testid="spnSRPProdTabShopLoc">Surabaya</span>
    <span data-testid="spnSRPProdTabShopName">Gadget Zone</span>
</div>
</body>
</html>
"""


@pytest.fixture
def sample_html():
    return SAMPLE_HTML_TOKOPEDIA


@pytest.fixture
def sample_dataset():
    return [
        {
            "url": "https://tokopedia.com/p1",
            "keyword": "iphone 15",
            "nama_produk": "Apple iPhone 15 128GB",
            "harga": 13999000.0,
            "harga_asli": 15999000.0,
            "diskon_persen": 12,
            "rating": 4.9,
            "terjual": 1200,
            "toko": "iBox Official",
            "lokasi_toko": "Jakarta Pusat",
            "badge_toko": "Official Store",
        },
        {
            "url": "https://tokopedia.com/p2",
            "keyword": "iphone 15",
            "nama_produk": "Apple iPhone 15 256GB",
            "harga": 15499000.0,
            "harga_asli": None,
            "diskon_persen": 0,
            "rating": 4.8,
            "terjual": 450,
            "toko": "Digimap",
            "lokasi_toko": "Jakarta Selatan",
            "badge_toko": "Official Store",
        },
        {
            "url": "https://tokopedia.com/p3",
            "keyword": "iphone 15",
            "nama_produk": "Casing iPhone 15 Bening",
            "harga": 25000.0,  # Outlier
            "harga_asli": None,
            "diskon_persen": 0,
            "rating": 4.6,
            "terjual": 800,
            "toko": "Case Store",
            "lokasi_toko": "Jakarta Barat",
            "badge_toko": "Power Merchant",
        },
        {
            "url": "https://tokopedia.com/p4",
            "keyword": "iphone 15",
            "nama_produk": "Apple iPhone 15 512GB",
            "harga": 18999000.0,
            "harga_asli": None,
            "diskon_persen": 0,
            "rating": 5.0,
            "terjual": 90,
            "toko": "Gadget Store",
            "lokasi_toko": "Surabaya",
            "badge_toko": "Reguler",
        },
    ]


@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_tokopedia.db"
