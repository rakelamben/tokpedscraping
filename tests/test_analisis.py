"""
Unit test lapisan analisis data dan filter IQR.
"""
import pandas as pd
import analisis


def test_bersihkan_outlier_iqr(sample_dataset):
    df = pd.DataFrame(sample_dataset)
    df_bersih = analisis.bersihkan(df)

    # Casing seharga Rp25.000 harus tersaring keluar
    iqr_filtered = analisis.bersihkan_outlier_iqr(df_bersih)
    assert 25000.0 not in iqr_filtered["harga"].values
    assert len(iqr_filtered) == 3


def test_ringkasan_pasar(sample_dataset):
    df = pd.DataFrame(sample_dataset)
    r = analisis.ringkasan_pasar(df, "iphone 15")

    assert r["total_sampel"] == 4
    assert r["sampel_valid"] == 3  # Tanpa aksesoris Rp25rb
    assert r["harga_median"] == 15499000.0
    assert r["total_terjual"] == 1200 + 450 + 800 + 90


def test_cari_best_value(sample_dataset):
    df = pd.DataFrame(sample_dataset)
    bv = analisis.cari_best_value(df, "iphone 15", limit=2)

    assert not bv.empty
    # Produk rating 4.9 dan harga <= median harus masuk
    assert bv.iloc[0]["nama_produk"] == "Apple iPhone 15 128GB"


def test_temuan_pasar(sample_dataset):
    df = pd.DataFrame(sample_dataset)
    temuan = analisis.temuan_pasar(df, "iphone 15")
    assert len(temuan) == 3
    assert "Harga wajar (median)" in temuan[0]
