"""
Pesan dan template balasan Bot Telegram.
Fungsi murni (Pure functions) tanpa dependensi Telegram agar 100% mudah diuji dengan pytest.
"""

BANTUAN = (
    "🤖 *Bot Intelijen Pasar Tokopedia*\n"
    "Berikut adalah daftar perintah yang tersedia:\n\n"
    "📊 *Analisis Pasar:*\n"
    "• `/pasar <keyword>` - Estimasi harga wajar (median), rentang harga riil & statistik pasar\n"
    "• `/bestvalue <keyword>` - 5 rekomendasi produk nilai terbaik (harga hemat & reputasi tinggi)\n"
    "• `/toko <keyword>` - Peta kota asal pengiriman dan dominasi jenis toko\n"
    "• `/grafik <keyword>` - Mengirimkan 3 grafik visual analisis pasar\n"
    "• `/laporan <keyword>` - Unduh file riset pasar lengkap (.xlsx & .pdf)\n\n"
    "🔄 *Otomasi & Pemantauan:*\n"
    "• `/scrape <keyword> [min:jumlah] [scroll:n]` - Scrape data realtime; filter minimum dan jumlah putaran scroll opsional\n"
    "• `/langganan <keyword>` - Menerima rekap intelijen pasar otomatis setiap pukul 08:00 WIB\n"
    "• `/berhenti` - Hentikan langganan laporan harian\n"
    "• `/help` - Tampilkan panduan ini\n\n"
    "💡 _Contoh: `/pasar iphone 14`, `/scrape iphone 14 min:500rb`, atau `/scrape iphone 14 scroll:3`_"
)


def format_intel_pasar(r: dict, temuan: list[str] = None) -> str:
    """Format ringkasan pasar dari hasil analisis."""
    if not r:
        return (
            "⚠️ *Data pasar belum tersedia!*\n"
            "Gunakan perintah `/scrape <kata kunci>` terlebih dahulu untuk mengambil data dari Tokopedia."
        )

    baris = [
        f"📊 *INTELIJEN PASAR: {r['keyword'].upper()}*",
        "────────────────────────",
        f"📦 *Total Sampel*: {r['total_sampel']} penawaran",
        f"🔥 *Volume Terjual*: {r['total_terjual']:,}+ unit",
        f"⭐ *Rating Rata-rata*: {r.get('rating_rata', 0.0)} / 5.0",
        "",
        f"💰 *Estimasi Harga Wajar (Median)*: Rp {r['harga_median']:,.0f}",
        f"📈 *Rentang Harga Pasar*: Rp {r['harga_min']:,.0f} - Rp {r['harga_max']:,.0f}",
        f"🏷 *Rata-rata Harga*: Rp {r['harga_rata']:,.0f}",
        f"🏬 *Pangsa Official Store*: {r['persen_official']}%",
        "────────────────────────",
    ]

    if temuan:
        baris.append("📌 *Temuan Analisis:*")
        for i, t in enumerate(temuan, 1):
            baris.append(f"{i}. {t}")
        baris.append("────────────────────────")

    baris.append(f"💡 _Ketik /bestvalue {r['keyword']} untuk produk rekomendasi terbaik._")
    return "\n".join(baris)


def format_best_value(df, keyword: str) -> str:
    """Format daftar 5 produk Best Value."""
    if df.empty:
        return f"Tidak ditemukan produk yang memenuhi kriteria Best Value untuk '{keyword}'."

    baris = [
        f"🏆 *REKOMENDASI BEST VALUE: {keyword.upper()}*",
        "_(Harga <= Median, Rating >= 4.7, Terjual Teruji)_",
        "────────────────────────",
    ]

    for i, p in enumerate(df.itertuples(), 1):
        nama = p.nama_produk[:50] + ("..." if len(p.nama_produk) > 50 else "")
        bintang = "★" * int(min(5, max(1, round(p.rating))))
        toko = f"{p.toko} ({p.lokasi_toko})"
        baris.append(
            f"{i}. *{nama}*\n"
            f"   💰 Rp {p.harga:,.0f} | {bintang} {p.rating} ({p.terjual}+ terjual)\n"
            f"   🏬 {toko}\n"
            f"   🔗 [Lihat Produk di Tokopedia]({p.url})\n"
        )

    baris.append("────────────────────────")
    baris.append(f"💡 _Ketik /laporan {keyword} untuk mengunduh spreadsheet lengkap._")
    return "\n".join(baris)


def format_analisis_toko(toko_info: dict, keyword: str) -> str:
    """Format informasi persebaran toko dan lokasi pengiriman."""
    kota = toko_info.get("kota")
    badge = toko_info.get("badge")

    if kota is None or kota.empty:
        return f"Belum ada data toko untuk kata kunci '{keyword}'."

    baris = [
        f"🏬 *PETA PENJUAL & LOGISTIK: {keyword.upper()}*",
        "────────────────────────",
        "📍 *Kota Asal Pengiriman Terbanyak:*",
    ]
    for k, val in kota.items():
        baris.append(f"• {k}: {val} penawaran")

    if badge is not None and not badge.empty:
        baris.append("\n🏷 *Distribusi Reputasi Toko:*")
        for b, val in badge.items():
            b_label = b if b else "Reguler Merchant"
            baris.append(f"• {b_label}: {val} toko")

    baris.append("────────────────────────")
    return "\n".join(baris)
