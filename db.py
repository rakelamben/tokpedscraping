"""
Lapisan Penyimpanan Data (Persistence): SQLite3.
Mengelola tabel produk_pasar (Upsert idempoten), riwayat_harga, snapshot_pasar,
dan persistensi langganan pengguna bot.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
import pandas as pd
import config


@contextmanager
def koneksi(path=config.DB_PATH):
    """Context manager untuk koneksi database SQLite."""
    con = sqlite3.connect(path)
    try:
        with con:
            yield con
    finally:
        con.close()


def siapkan(path=config.DB_PATH):
    """Membuat tabel jika belum ada."""
    with koneksi(path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS produk_pasar (
                url              TEXT PRIMARY KEY,
                keyword          TEXT NOT NULL,
                nama_produk      TEXT NOT NULL,
                harga            REAL NOT NULL,
                harga_asli       REAL,
                diskon_persen    INTEGER DEFAULT 0,
                rating           REAL DEFAULT 0.0,
                terjual          INTEGER DEFAULT 0,
                toko             TEXT,
                lokasi_toko      TEXT,
                badge_toko       TEXT,
                pertama_dilihat  TEXT,
                terakhir_dilihat TEXT
            );

            CREATE TABLE IF NOT EXISTS riwayat_harga (
                url          TEXT,
                waktu_scrape TEXT,
                harga        REAL,
                terjual      INTEGER,
                PRIMARY KEY (url, waktu_scrape)
            );

            CREATE TABLE IF NOT EXISTS snapshot_pasar (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword         TEXT NOT NULL,
                waktu_ambil     TEXT NOT NULL,
                jumlah_sampel   INTEGER,
                harga_terendah  REAL,
                harga_median    REAL,
                harga_rata      REAL,
                harga_tertinggi REAL,
                total_terjual   INTEGER
            );

            CREATE TABLE IF NOT EXISTS langganan (
                chat_id      INTEGER NOT NULL,
                keyword      TEXT NOT NULL,
                jam_kirim    TEXT DEFAULT '08:00',
                status_aktif INTEGER DEFAULT 1,
                dibuat_pada  TEXT,
                PRIMARY KEY (chat_id, keyword)
            );
            """
        )


def simpan_produk(data: list[dict], keyword: str, waktu: str = None, path=config.DB_PATH) -> int:
    """
    Menyimpan data hasil scraping ke tabel produk_pasar menggunakan ON CONFLICT DO UPDATE (Upsert).
    Mengembalikan jumlah produk baru.
    """
    if not data:
        return 0

    waktu = waktu or datetime.now().isoformat(timespec="seconds")
    siapkan(path)

    with koneksi(path) as con:
        sebelum = con.execute("SELECT COUNT(*) FROM produk_pasar WHERE keyword = ?", (keyword,)).fetchone()[0]

        # Upsert produk master
        con.executemany(
            """
            INSERT INTO produk_pasar (
                url, keyword, nama_produk, harga, harga_asli, diskon_persen,
                rating, terjual, toko, lokasi_toko, badge_toko, pertama_dilihat, terakhir_dilihat
            )
            VALUES (
                :url, :keyword, :nama_produk, :harga, :harga_asli, :diskon_persen,
                :rating, :terjual, :toko, :lokasi_toko, :badge_toko, :waktu, :waktu
            )
            ON CONFLICT(url) DO UPDATE SET
                keyword = excluded.keyword,
                nama_produk = excluded.nama_produk,
                harga = excluded.harga,
                harga_asli = excluded.harga_asli,
                diskon_persen = excluded.diskon_persen,
                rating = excluded.rating,
                terjual = excluded.terjual,
                toko = excluded.toko,
                lokasi_toko = excluded.lokasi_toko,
                badge_toko = excluded.badge_toko,
                terakhir_dilihat = excluded.terakhir_dilihat
            """,
            [{**b, "waktu": waktu} for b in data],
        )

        # Simpan log ke riwayat_harga
        con.executemany(
            """
            INSERT OR IGNORE INTO riwayat_harga (url, waktu_scrape, harga, terjual)
            VALUES (?, ?, ?, ?)
            """,
            [(b["url"], waktu, b["harga"], b.get("terjual", 0)) for b in data],
        )

        sesudah = con.execute("SELECT COUNT(*) FROM produk_pasar WHERE keyword = ?", (keyword,)).fetchone()[0]

    return sesudah - sebelum


def simpan_snapshot_pasar(ringkasan: dict, waktu: str = None, path=config.DB_PATH):
    """Mencatat histori kondisi pasar per sesi analisis."""
    if not ringkasan:
        return
    waktu = waktu or datetime.now().isoformat(timespec="seconds")
    siapkan(path)
    with koneksi(path) as con:
        con.execute(
            """
            INSERT INTO snapshot_pasar (
                keyword, waktu_ambil, jumlah_sampel, harga_terendah,
                harga_median, harga_rata, harga_tertinggi, total_terjual
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ringkasan["keyword"],
                waktu,
                ringkasan.get("total_sampel", 0),
                ringkasan.get("harga_min", 0.0),
                ringkasan.get("harga_median", 0.0),
                ringkasan.get("harga_rata", 0.0),
                ringkasan.get("harga_max", 0.0),
                ringkasan.get("total_terjual", 0),
            ),
        )


def baca_produk(keyword: str = None, path=config.DB_PATH) -> pd.DataFrame:
    """Membaca seluruh produk atau filter berdasarkan kata kunci."""
    siapkan(path)
    with koneksi(path) as con:
        if keyword:
            return pd.read_sql(
                "SELECT * FROM produk_pasar WHERE LOWER(keyword) = LOWER(?)",
                con,
                params=[keyword.strip()],
            )
        return pd.read_sql("SELECT * FROM produk_pasar", con)


def cari_produk(kata: str, batas: int = 5, path=config.DB_PATH) -> pd.DataFrame:
    """Mencari produk berdasarkan nama produk."""
    siapkan(path)
    with koneksi(path) as con:
        return pd.read_sql(
            """
            SELECT nama_produk, toko, lokasi_toko, harga, rating, terjual, url
            FROM produk_pasar
            WHERE nama_produk LIKE ?
            ORDER BY rating DESC, terjual DESC, harga ASC
            LIMIT ?
            """,
            con,
            params=[f"%{kata}%", batas],
        )


# ---------- Manajemen Langganan Pengguna (Persistensi) ----------
def tambah_langganan(chat_id: int, keyword: str, jam_kirim: str = "08:00", path=config.DB_PATH):
    """Menyimpan atau mengaktifkan langganan pengguna di database."""
    siapkan(path)
    waktu = datetime.now().isoformat(timespec="seconds")
    with koneksi(path) as con:
        con.execute(
            """
            INSERT INTO langganan (chat_id, keyword, jam_kirim, status_aktif, dibuat_pada)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(chat_id, keyword) DO UPDATE SET
                jam_kirim = excluded.jam_kirim,
                status_aktif = 1
            """,
            (chat_id, keyword.strip().lower(), jam_kirim, waktu),
        )


def hapus_langganan(chat_id: int, keyword: str = None, path=config.DB_PATH) -> int:
    """Menonaktifkan langganan (spesifik keyword atau semua keyword milik chat_id)."""
    siapkan(path)
    with koneksi(path) as con:
        if keyword:
            cur = con.execute(
                "UPDATE langganan SET status_aktif = 0 WHERE chat_id = ? AND LOWER(keyword) = LOWER(?)",
                (chat_id, keyword.strip()),
            )
        else:
            cur = con.execute("UPDATE langganan SET status_aktif = 0 WHERE chat_id = ?", (chat_id,))
        return cur.rowcount


def daftar_langganan_aktif(path=config.DB_PATH) -> list[tuple]:
    """Mengambil semua langganan aktif: [(chat_id, keyword, jam_kirim), ...]"""
    siapkan(path)
    with koneksi(path) as con:
        return con.execute(
            "SELECT chat_id, keyword, jam_kirim FROM langganan WHERE status_aktif = 1"
        ).fetchall()
