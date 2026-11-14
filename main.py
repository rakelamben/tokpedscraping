"""
Titik Masuk Pipeline CLI: Scraping -> SQLite -> Analisis Pasar -> Grafik -> Laporan.

Penggunaan:
  python main.py                                      # Menjalankan untuk semua keyword default
  python main.py --keyword "iphone 15" --scroll 2     # Jumlah putaran infinite scroll
  python main.py --tanpa-scrape --keyword "iphone 15" # Hanya buat ulang analisis & laporan dari DB
  python main.py --keyword "iphone 15" --raw          # Simpan raw HTML hasil scraping
  python main.py --jadwal                             # Menjalankan pipeline terjadwal setiap hari
"""
import argparse
import logging
import re
import time
from datetime import datetime
from pathlib import Path
import schedule

import analisis
import config
import db
import laporan
from scraper import TokopediaScraper

config.LOG_DIR.mkdir(exist_ok=True)
config.DATA_DIR.mkdir(exist_ok=True)
config.OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("pipeline")


def simpan_raw_html(keyword: str, halaman_html: list[str], folder: Path = config.OUTPUT_DIR) -> list[Path]:
    """Menyimpan HTML setiap halaman ke folder output."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", keyword.strip()).strip("_") or "keyword"
    waktu = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder.mkdir(parents=True, exist_ok=True)

    file_html = []
    for halaman, html in enumerate(halaman_html, start=1):
        path = folder / f"raw_{slug}_{waktu}_hal_{halaman}.html"
        path.write_text(html, encoding="utf-8")
        file_html.append(path)
    return file_html


def jalankan_pipeline_keyword(
    keyword: str,
    halaman_maks: int = config.DEFAULT_PAGES,
    tanpa_scrape: bool = False,
    raw: bool = False,
    pmin: float | None = None,
    pmax: float | None = None
):
    """Menjalankan siklus analisis pasar lengkap untuk satu kata kunci."""
    keyword = keyword.strip()
    log.info("=== Memulai Pipeline Intelijen Pasar: '%s' ===", keyword)
    mulai = time.time()

    try:
        # 1. Ekstraksi Data dari Tokopedia (jika tidak tanpa_scrape)
        if not tanpa_scrape:
            scraper = TokopediaScraper(headless=config.HEADLESS)
            data = scraper.jalankan([keyword], halaman_maks=halaman_maks, raw=raw, pmin=pmin, pmax=pmax)
            if raw:
                if not all(isinstance(html, str) for html in data):
                    raise TypeError("Scraper harus mengembalikan HTML per halaman dalam mode raw.")
                file_html = simpan_raw_html(keyword, data)
                for path in file_html:
                    log.info("Raw HTML tersimpan: %s", path)
            else:
                baru = db.simpan_produk(data, keyword)
                log.info("Tersimpan %d produk (%d produk baru) untuk keyword '%s'", len(data), baru, keyword)

        # 2. Pembacaan & Pembersihan Data dari Database
        df = analisis.bersihkan(db.baca_produk(keyword))
        if df.empty:
            log.warning("Database kosong untuk keyword '%s'. Jalankan tanpa --tanpa-scrape dulu.", keyword)
            return None

        # 3. Analisis Statistik & Ringkasan Pasar
        r = analisis.ringkasan_pasar(df, keyword)
        db.simpan_snapshot_pasar(r)

        # 4. Pembuatan Grafik Visual & Dokumen Laporan
        grafik = analisis.buat_grafik_pasar(df, keyword)
        xlsx = laporan.buat_excel(df, keyword, grafik)
        pdf = laporan.buat_pdf(df, keyword, grafik)

        # 5. Log Temuan Pasar
        for t in analisis.temuan_pasar(df, keyword):
            log.info("Temuan: %s", t)

        durasi = time.time() - mulai
        log.info(
            "Pipeline '%s' selesai dalam %.1f detik. Laporan: %s, %s",
            keyword, durasi, xlsx.name, pdf.name
        )
        return {"xlsx": xlsx, "pdf": pdf, "ringkasan": r, "grafik": grafik}

    except Exception:
        log.exception("Pipeline gagal untuk keyword '%s'", keyword)
        return None


def jalankan_semua(
    keywords: list[str],
    halaman_maks: int = config.DEFAULT_PAGES,
    tanpa_scrape: bool = False,
    raw: bool = False,
    pmin: float | None = None,
    pmax: float | None = None
):
    """Menjalankan pipeline untuk daftar kata kunci."""
    for kw in keywords:
        jalankan_pipeline_keyword(kw, halaman_maks, tanpa_scrape, raw, pmin, pmax)


def main():
    parser = argparse.ArgumentParser(description="Pipeline Bot Intelijen Pasar Tokopedia")
    parser.add_argument("--keyword", type=str, help="Kata kunci pencarian (misal: 'iphone 15')")
    parser.add_argument(
        "--scroll", "--halaman", dest="halaman",
        type=int, default=config.DEFAULT_PAGES,
        help="Jumlah halaman / putaran scroll (default: 2)",
    )
    parser.add_argument("--pmin", type=float, default=None, help="Filter harga minimum (opsional, misal: 5000000)")
    parser.add_argument("--pmax", type=float, default=None, help="Filter harga maksimum (opsional)")
    parser.add_argument("--tanpa-scrape", action="store_true", help="Gunakan data yang sudah ada di SQLite")
    parser.add_argument("--raw", action="store_true", help="Simpan raw HTML setelah infinite scroll ke folder output")
    parser.add_argument("--jadwal", action="store_true", help="Jalankan otomatis setiap hari pada JAM_JADWAL")
    args = parser.parse_args()

    target_keywords = [args.keyword] if args.keyword else config.DEFAULT_KEYWORDS

    if args.jadwal:
        log.info("Menjadwalkan pipeline setiap hari pukul %s WIB untuk kata kunci: %s", config.JAM_JADWAL, target_keywords)
        schedule.every().day.at(config.JAM_JADWAL).do(jalankan_semua, target_keywords, args.halaman, False, False, args.pmin, args.pmax)
        while True:
            schedule.run_pending()
            time.sleep(30)
    else:
        jalankan_semua(target_keywords, args.halaman, args.tanpa_scrape, args.raw, args.pmin, args.pmax)


if __name__ == "__main__":
    main()
