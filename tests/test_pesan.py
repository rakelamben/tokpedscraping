"""
Unit test pemformatan pesan bot Telegram.
"""
import pandas as pd
import pesan


def test_format_intel_pasar():
    r = {
        "keyword": "iphone 15",
        "total_sampel": 60,
        "total_terjual": 3500,
        "rating_rata": 4.85,
        "harga_min": 12500000.0,
        "harga_median": 13999000.0,
        "harga_rata": 14100000.0,
        "harga_max": 18500000.0,
        "persen_official": 65.0,
    }
    teks = pesan.format_intel_pasar(r, ["Temuan 1", "Temuan 2"])

    assert "INTELIJEN PASAR: IPHONE 15" in teks
    assert "Rp 13,999,000" in teks
    assert "65.0%" in teks
    assert "Temuan 1" in teks


def test_format_best_value(sample_dataset):
    df = pd.DataFrame(sample_dataset)
    teks = pesan.format_best_value(df.head(2), "iphone 15")

    assert "REKOMENDASI BEST VALUE" in teks
    assert "Apple iPhone 15" in teks
    assert "Lihat Produk di Tokopedia" in teks
