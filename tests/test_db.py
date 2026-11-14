"""
Unit test lapisan penyimpanan SQLite.
"""
import db


def test_simpan_dan_baca_produk(temp_db, sample_dataset):
    # Simpan produk
    baru = db.simpan_produk(sample_dataset, "iphone 15", path=temp_db)
    assert baru == 4

    # Baca kembali
    df = db.baca_produk("iphone 15", path=temp_db)
    assert len(df) == 4
    assert "Apple iPhone 15 128GB" in df["nama_produk"].values

    # Uji Idempotensi Upsert (tidak boleh menduplikasi baris)
    update_data = [
        {**sample_dataset[0], "harga": 13500000.0}  # Harga turun
    ]
    baru_lagi = db.simpan_produk(update_data, "iphone 15", path=temp_db)
    assert baru_lagi == 0

    df_sesudah = db.baca_produk("iphone 15", path=temp_db)
    assert len(df_sesudah) == 4
    p1 = df_sesudah[df_sesudah["url"] == sample_dataset[0]["url"]].iloc[0]
    assert p1["harga"] == 13500000.0


def test_snapshot_pasar(temp_db):
    ringkasan = {
        "keyword": "iphone 15",
        "total_sampel": 50,
        "harga_min": 12000000.0,
        "harga_median": 14000000.0,
        "harga_rata": 14200000.0,
        "harga_max": 19000000.0,
        "total_terjual": 5000,
    }
    db.simpan_snapshot_pasar(ringkasan, path=temp_db)

    with db.koneksi(temp_db) as con:
        row = con.execute("SELECT * FROM snapshot_pasar WHERE keyword = 'iphone 15'").fetchone()
        assert row is not None
        assert row[5] == 14000000.0  # harga_median


def test_manajemen_langganan(temp_db):
    db.tambah_langganan(123456, "iphone 15", jam_kirim="08:00", path=temp_db)
    aktif = db.daftar_langganan_aktif(path=temp_db)
    assert len(aktif) == 1
    assert aktif[0][0] == 123456
    assert aktif[0][1] == "iphone 15"

    # Hapus langganan
    db.hapus_langganan(123456, "iphone 15", path=temp_db)
    assert len(db.daftar_langganan_aktif(path=temp_db)) == 0
