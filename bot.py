"""
Lapisan Antarmuka: BOT TELEGRAM INTELIJEN PASAR TOKOPEDIA.

Fitur:
- Perintah: /start, /help, /pasar, /bestvalue, /toko, /grafik, /laporan, /scrape, /langganan, /berhenti.
- Pengamanan memori: asyncio.Lock() untuk antrean scraping (maks 1 browser aktif).
- Cooldown proteksi spam untuk pengguna umum.
- Persistensi langganan via SQLite + sinkronisasi otomatis ke JobQueue saat startup.
"""
import asyncio
import datetime
import logging
import re
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import analisis
import config
import db
import laporan
import pesan
from scraper import TokopediaScraper

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
log = logging.getLogger("tokopedia_bot")

WIB = ZoneInfo("Asia/Jakarta")

# Concurrency lock agar tidak ada 2 proses Playwright yang berjalan bersamaan (menghemat RAM)
SCRAPE_LOCK = asyncio.Lock()
USER_COOLDOWN: dict[int, float] = {}
COOLDOWN_DETIK = 300  # 5 menit cooldown untuk non-admin


def _parse_keyword_min_price(args: list[str]) -> tuple[str, float | None]:
    """Pisahkan filter harga minimum eksplisit dari keyword."""
    if len(args) > 1:
        match = re.fullmatch(r"min:(\d+(?:[.,]\d+)?)(rb|jt)?", args[-1], re.IGNORECASE)
        if match:
            jumlah = float(match.group(1).replace(",", "."))
            satuan = (match.group(2) or "").lower()
            pengali = {"rb": 1_000, "jt": 1_000_000}.get(satuan, 1)
            if jumlah > 0:
                return " ".join(args[:-1]).strip(), jumlah * pengali

    return " ".join(args).strip(), None


def cek_cooldown(user_id: int) -> int | None:
    """Mengembalikan sisa detik cooldown jika aktif, atau None jika bebas."""
    if user_id == config.ADMIN_CHAT_ID:
        return None  # Admin bebas cooldown
    sekarang = time.time()
    terakhir = USER_COOLDOWN.get(user_id, 0)
    if sekarang - terakhir < COOLDOWN_DETIK:
        return int(COOLDOWN_DETIK - (sekarang - terakhir))
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Halo, {user_name}! 👋\n"
        f"Selamat datang di *Bot Intelijen Pasar Tokopedia*.\n\n"
        f"{pesan.BANTUAN}",
        parse_mode=ParseMode.MARKDOWN
    )


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(pesan.BANTUAN, parse_mode=ParseMode.MARKDOWN)


async def pasar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Melihat ringkasan kondisi pasar untuk kata kunci tertentu."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Masukkan kata kunci yang ingin dianalisis.\n*Contoh*: `/pasar iphone 15`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keyword, _ = _parse_keyword_min_price(context.args)
    df = analisis.bersihkan(db.baca_produk(keyword))

    if df.empty:
        await update.message.reply_text(
            f"Data untuk *'{keyword}'* belum tersedia di database.\n"
            f"Ketik `/scrape {keyword}` untuk mengambil data terbaru dari Tokopedia.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    r = analisis.ringkasan_pasar(df, keyword)
    temuan = analisis.temuan_pasar(df, keyword)
    teks = pesan.format_intel_pasar(r, temuan)
    await update.message.reply_text(teks, parse_mode=ParseMode.MARKDOWN)


async def bestvalue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Melihat 5 rekomendasi produk nilai terbaik."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Masukkan kata kunci pencarian.\n*Contoh*: `/bestvalue mechanical keyboard`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keyword, _ = _parse_keyword_min_price(context.args)
    df = analisis.bersihkan(db.baca_produk(keyword))

    if df.empty:
        await update.message.reply_text(
            f"Data untuk *'{keyword}'* belum tersedia.\nKetik `/scrape {keyword}` terlebih dahulu.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    bv = analisis.cari_best_value(df, keyword, limit=5)
    teks = pesan.format_best_value(bv, keyword)
    await update.message.reply_text(teks, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def toko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Melihat peta sebaran toko dan kota pengiriman."""
    if not context.args:
        await update.message.reply_text("Contoh penggunaan: `/toko tws anc`", parse_mode=ParseMode.MARKDOWN)
        return

    keyword, _ = _parse_keyword_min_price(context.args)
    df = analisis.bersihkan(db.baca_produk(keyword))

    if df.empty:
        await update.message.reply_text(f"Data untuk '{keyword}' belum tersedia. Jalankan /scrape dulu.")
        return

    info = analisis.analisis_toko(df, keyword, top_n=5)
    teks = pesan.format_analisis_toko(info, keyword)
    await update.message.reply_text(teks, parse_mode=ParseMode.MARKDOWN)


async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengirim 3 grafik visual analisis pasar."""
    if not context.args:
        await update.message.reply_text("Contoh penggunaan: `/grafik iphone 15`", parse_mode=ParseMode.MARKDOWN)
        return

    keyword, _ = _parse_keyword_min_price(context.args)
    df = analisis.bersihkan(db.baca_produk(keyword))

    if df.empty:
        await update.message.reply_text(f"Data untuk '{keyword}' belum tersedia. Jalankan /scrape dulu.")
        return

    pesan_tunggu = await update.message.reply_text("⏳ Sedang merender visualisasi grafik...")
    paths = analisis.buat_grafik_pasar(df, keyword)

    for kunci, caption in [
        ("distribusi", f"Distribusi Harga Pasar ({keyword})"),
        ("scatter", f"Peta Penjualan vs Harga ({keyword})"),
        ("kota", f"Kota Asal Pengiriman Terbanyak ({keyword})"),
    ]:
        p = paths.get(kunci)
        if p and Path(p).exists():
            with open(p, "rb") as foto:
                await update.message.reply_photo(foto, caption=caption)

    await pesan_tunggu.delete()


async def laporan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membuat dan mengirimkan dokumen spreadsheet Excel dan PDF."""
    if not context.args:
        await update.message.reply_text("Contoh penggunaan: `/laporan iphone 15`", parse_mode=ParseMode.MARKDOWN)
        return

    keyword, _ = _parse_keyword_min_price(context.args)
    df = analisis.bersihkan(db.baca_produk(keyword))

    if df.empty:
        await update.message.reply_text(f"Data untuk '{keyword}' belum tersedia. Jalankan /scrape dulu.")
        return

    status_msg = await update.message.reply_text("⏳ Menyusun laporan Excel dan PDF...")
    grafik_paths = analisis.buat_grafik_pasar(df, keyword)
    xlsx = laporan.buat_excel(df, keyword, grafik_paths)
    pdf = laporan.buat_pdf(df, keyword, grafik_paths)

    with open(xlsx, "rb") as f_excel:
        await update.message.reply_document(f_excel, caption=f"📊 Spreadsheet Riset Pasar: {keyword.title()}")
    with open(pdf, "rb") as f_pdf:
        await update.message.reply_document(f_pdf, caption=f"📄 Laporan Eksekutif PDF: {keyword.title()}")

    await status_msg.delete()


async def scrape_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi scraping realtime dengan proteksi lock antrean & cooldown."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "⚠️ Masukkan kata kunci.\n*Contoh*: `/scrape iphone 14` atau `/scrape iphone 14 min:500rb`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keyword, pmin = _parse_keyword_min_price(context.args)

    # Periksa cooldown
    sisa = cek_cooldown(user_id)
    if sisa:
        await update.message.reply_text(f"⏳ Harap tunggu *{sisa} detik* lagi sebelum memicu scraping baru.", parse_mode=ParseMode.MARKDOWN)
        return

    if SCRAPE_LOCK.locked():
        await update.message.reply_text("⚠️ Sistem sedang menjalankan tugas scraping lain. Permintaanmu masuk antrean...", parse_mode=ParseMode.MARKDOWN)

    async with SCRAPE_LOCK:
        USER_COOLDOWN[user_id] = time.time()
        notif = await update.message.reply_text(f"🚀 Memulai browser Playwright untuk *'{keyword}'*... Mohon tunggu $\\approx 15-25$ detik.", parse_mode=ParseMode.MARKDOWN)

        try:
            scraper = TokopediaScraper(headless=config.HEADLESS)
            data = await scraper.ambil_keyword(keyword, halaman_maks=config.DEFAULT_PAGES, pmin=pmin)
            baru = db.simpan_produk(data, keyword)

            df = analisis.bersihkan(db.baca_produk(keyword))
            r = analisis.ringkasan_pasar(df, keyword)
            db.simpan_snapshot_pasar(r)
            temuan = analisis.temuan_pasar(df, keyword)

            await notif.edit_text(
                f"✅ *Scraping Selesai!*\n"
                f"Terkumpul *{len(data)} produk* ({baru} produk baru).\n\n"
                f"{pesan.format_intel_pasar(r, temuan)}",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            log.error("Scraping error: %s", e)
            await notif.edit_text(f"❌ Terjadi kesalahan saat scraping: `{e}`", parse_mode=ParseMode.MARKDOWN)


# ---------- Scheduler Otomatis (JobQueue) ----------
async def tugas_langganan_harian(context: ContextTypes.DEFAULT_TYPE):
    """Callback JobQueue yang berjalan otomatis setiap hari."""
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    keyword = job_data["keyword"]

    log.info("Menjalankan tugas harian otomatis untuk chat %s (keyword: %s)", chat_id, keyword)

    # Scrape data terbaru di latar belakang
    async with SCRAPE_LOCK:
        try:
            scraper = TokopediaScraper(headless=config.HEADLESS)
            data = await scraper.ambil_keyword(keyword, halaman_maks=1)
            db.simpan_produk(data, keyword)
        except Exception as e:
            log.warning("Gagal auto-scrape harian: %s", e)

    df = analisis.bersihkan(db.baca_produk(keyword))
    if not df.empty:
        r = analisis.ringkasan_pasar(df, keyword)
        db.simpan_snapshot_pasar(r)
        temuan = analisis.temuan_pasar(df, keyword)
        teks = f"🌅 *LAPORAN HARIAN PASAR TOKOPEDIA*\n\n" + pesan.format_intel_pasar(r, temuan)
        await context.bot.send_message(chat_id=chat_id, text=teks, parse_mode=ParseMode.MARKDOWN)


async def langganan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mendaftarkan kata kunci untuk laporan harian otomatis pukul 08:00 WIB."""
    if not context.args:
        await update.message.reply_text("Contoh: `/langganan iphone 15`", parse_mode=ParseMode.MARKDOWN)
        return

    chat_id = update.effective_chat.id
    keyword, _ = _parse_keyword_min_price(context.args)
    keyword = keyword.lower()

    # Simpan ke SQLite
    db.tambah_langganan(chat_id, keyword, jam_kirim=config.JAM_JADWAL)

    # Jadwalkan di JobQueue
    nama_job = f"harian_{chat_id}_{keyword}"
    for job in context.job_queue.get_jobs_by_name(nama_job):
        job.schedule_removal()

    jam, menit = map(int, config.JAM_JADWAL.split(":"))
    context.job_queue.run_daily(
        tugas_langganan_harian,
        time=datetime.time(jam, menit, tzinfo=WIB),
        chat_id=chat_id,
        name=nama_job,
        data={"chat_id": chat_id, "keyword": keyword}
    )

    await update.message.reply_text(
        f"✅ *Langganan Berhasil!*\n"
        f"Laporan intelijen pasar untuk *'{keyword}'* akan dikirimkan otomatis setiap hari pukul *{config.JAM_JADWAL} WIB*.",
        parse_mode=ParseMode.MARKDOWN
    )


async def berhenti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menghentikan langganan otomatis."""
    chat_id = update.effective_chat.id
    db.hapus_langganan(chat_id)

    # Hapus semua job milik chat_id
    jobs = [j for j in context.job_queue.jobs() if f"harian_{chat_id}_" in j.name]
    for j in jobs:
        j.schedule_removal()

    await update.message.reply_text("🛑 Semua langganan laporan harian telah dihentikan.")


async def setelah_mulai(app: Application):
    """Dijalankan saat startup bot: Daftarkan command menu & sinkronisasi langganan dari SQLite."""
    await app.bot.set_my_commands([
        BotCommand("pasar", "Ringkasan intelijen pasar"),
        BotCommand("bestvalue", "Rekomendasi produk nilai terbaik"),
        BotCommand("toko", "Peta toko & lokasi pengiriman"),
        BotCommand("grafik", "Kirim visualisasi grafik"),
        BotCommand("laporan", "Unduh spreadsheet Excel & PDF"),
        BotCommand("scrape", "Scrape data realtime kata kunci baru"),
        BotCommand("langganan", "Laporan harian otomatis"),
        BotCommand("berhenti", "Hentikan laporan harian"),
        BotCommand("help", "Panduan bantuan"),
    ])

    # Muat ulang semua langganan aktif dari database SQLite ke JobQueue
    langganan_list = db.daftar_langganan_aktif()
    log.info("Memuat %d langganan aktif dari database ke JobQueue...", len(langganan_list))
    jam, menit = map(int, config.JAM_JADWAL.split(":"))

    for chat_id, keyword, _ in langganan_list:
        nama_job = f"harian_{chat_id}_{keyword}"
        app.job_queue.run_daily(
            tugas_langganan_harian,
            time=datetime.time(jam, menit, tzinfo=WIB),
            chat_id=chat_id,
            name=nama_job,
            data={"chat_id": chat_id, "keyword": keyword}
        )


def buat_aplikasi(token: str) -> Application:
    app = Application.builder().token(token).post_init(setelah_mulai).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", bantuan))
    app.add_handler(CommandHandler("pasar", pasar))
    app.add_handler(CommandHandler("bestvalue", bestvalue))
    app.add_handler(CommandHandler("toko", toko))
    app.add_handler(CommandHandler("grafik", grafik))
    app.add_handler(CommandHandler("laporan", laporan_cmd))
    app.add_handler(CommandHandler("export", laporan_cmd))
    app.add_handler(CommandHandler("scrape", scrape_cmd))
    app.add_handler(CommandHandler("langganan", langganan))
    app.add_handler(CommandHandler("berhenti", berhenti))

    return app


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN belum diatur. Buat file .env dan isi token dari @BotFather.")
    log.info("Memulai Bot Telegram Tokopedia...")
    app = buat_aplikasi(config.BOT_TOKEN)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
