"""
Lapisan 3: ANALISIS DAN VISUALISASI INTELIJEN PASAR.

Fitur:
- Pembersihan outlier harga via metode IQR (menghapus aksesoris casing/kabel).
- Estimasi harga wajar (median pasar) dan sebaran harga riil.
- Kurasi produk Best Value (harga <= median, rating >= 4.7, terjual banyak).
- Analisis sebaran reputasi toko dan kota asal pengiriman.
- Generator 3 grafik analisis visual (Matplotlib Agg backend).
"""
import logging
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Mode headless tanpa GUI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import config

log = logging.getLogger(__name__)
WARNA_UTAMA = "#03AC0E"  # Hijau khas Tokopedia
WARNA_SEKUNDER = "#FA591D"  # Oranye aksen


def bersihkan(df: pd.DataFrame) -> pd.DataFrame:
    """Memastikan tipe data numerik dan menghapus duplikat URL."""
    if df.empty:
        return df.copy()
    df = df.copy()
    df["harga"] = pd.to_numeric(df["harga"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0.0)
    df["terjual"] = pd.to_numeric(df["terjual"], errors="coerce").fillna(0).astype(int)
    df["diskon_persen"] = pd.to_numeric(df["diskon_persen"], errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["nama_produk", "harga"]).drop_duplicates(subset="url")
    return df


def bersihkan_outlier_iqr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menyaring produk yang harganya terlalu rendah (anomali/aksesoris seperti casing atau kabel)
    atau harga ekstrem terlalu tinggi menggunakan metode Interquartile Range (IQR).
    """
    if len(df) < 4:
        return df.copy()

    q1 = df["harga"].quantile(0.25)
    q3 = df["harga"].quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return df.copy()

    batas_bawah = max(0, q1 - 1.5 * iqr)
    batas_atas = q3 + 1.5 * iqr

    hasil = df[(df["harga"] >= batas_bawah) & (df["harga"] <= batas_atas)]
    # Jika penyaringan terlalu agresif hingga menyisakan < 20% data, kembalikan data asli
    if len(hasil) < len(df) * 0.2:
        return df.copy()
    return hasil


def ringkasan_pasar(df: pd.DataFrame, keyword: str) -> dict:
    """Menghitung metrik agregat pasar untuk satu kata kunci."""
    sub = df[df["keyword"].str.lower() == keyword.lower().strip()]
    if sub.empty:
        return {}

    sub_bersih = bersihkan_outlier_iqr(sub)
    total_sampel = len(sub)
    total_terjual = int(sub["terjual"].sum())

    is_official = sub["badge_toko"].str.contains("Official|OS", case=False, na=False)
    persen_official = round(100 * is_official.mean(), 1) if not is_official.empty else 0.0

    return {
        "keyword": keyword,
        "total_sampel": total_sampel,
        "sampel_valid": len(sub_bersih),
        "harga_min": float(sub_bersih["harga"].min()),
        "harga_max": float(sub_bersih["harga"].max()),
        "harga_median": float(sub_bersih["harga"].median()),
        "harga_rata": float(round(sub_bersih["harga"].mean(), 0)),
        "total_terjual": total_terjual,
        "persen_official": persen_official,
        "rating_rata": round(float(sub_bersih["rating"].mean()), 2),
    }


def cari_best_value(df: pd.DataFrame, keyword: str, limit: int = 5) -> pd.DataFrame:
    """
    Menemukan produk Best Value:
    - Harga berada di bawah atau setara median pasar.
    - Rating tinggi (>= 4.7) dan sudah terjual minimal 5 unit.
    """
    sub = df[df["keyword"].str.lower() == keyword.lower().strip()].copy()
    if sub.empty:
        return pd.DataFrame()

    sub_bersih = bersihkan_outlier_iqr(sub)
    median_harga = sub_bersih["harga"].median()

    kandidat = sub_bersih[
        (sub_bersih["harga"] <= median_harga) &
        (sub_bersih["rating"] >= 4.7) &
        (sub_bersih["terjual"] >= 5)
    ].copy()

    # Fallback jika kriteria terlalu ketat
    if len(kandidat) < limit:
        kandidat = sub_bersih[
            (sub_bersih["harga"] <= median_harga * 1.1) &
            (sub_bersih["rating"] >= 4.5)
        ].copy()

    # Urutkan berdasarkan rating tertinggi, terjual terbanyak, dan harga termurah
    kandidat = kandidat.sort_values(
        by=["rating", "terjual", "harga"],
        ascending=[False, False, True]
    )
    return kandidat.head(limit)


def analisis_toko(df: pd.DataFrame, keyword: str, top_n: int = 5) -> dict:
    """Menganalisis sebaran kota pengiriman dan reputasi toko."""
    sub = df[df["keyword"].str.lower() == keyword.lower().strip()]
    if sub.empty:
        return {"kota": pd.Series(dtype=int), "badge": pd.Series(dtype=int)}

    kota_top = sub["lokasi_toko"].value_counts().head(top_n)
    badge_dist = sub["badge_toko"].value_counts()
    return {"kota": kota_top, "badge": badge_dist}


def temuan_pasar(df: pd.DataFrame, keyword: str) -> list[str]:
    """Menyusun kalimat temuan intelijen pasar secara otomatis."""
    r = ringkasan_pasar(df, keyword)
    if not r:
        return ["Belum ada cukup data untuk menyusun temuan pasar."]

    bv = cari_best_value(df, keyword, limit=1)
    toko = analisis_toko(df, keyword, top_n=1)

    kota_utama = toko["kota"].index[0] if not toko["kota"].empty else "Indonesia"
    persen_kota = (
        round(100 * toko["kota"].iloc[0] / r["total_sampel"], 1)
        if not toko["kota"].empty and r["total_sampel"] > 0
        else 0
    )

    t1 = (
        f"Harga wajar (median) untuk '{keyword}' adalah Rp {r['harga_median']:,.0f} "
        f"dengan rentang pasar Rp {r['harga_min']:,.0f} - Rp {r['harga_max']:,.0f}."
    )
    t2 = (
        f"Pusat pengiriman terbanyak berasal dari {kota_utama} ({persen_kota}% dari total penawaran), "
        f"dengan dominasi Official Store sebesar {r['persen_official']}%."
    )
    if not bv.empty:
        top_bv = bv.iloc[0]
        t3 = (
            f"Pilihan Best Value teratas: '{top_bv['nama_produk'][:45]}...' "
            f"seharga Rp {top_bv['harga']:,.0f} (Rating {top_bv['rating']} ★, Terjual {top_bv['terjual']}+ unit)."
        )
    else:
        t3 = f"Total volume peredaran barang untuk '{keyword}' tercatat {r['total_terjual']:,}+ unit terjual."

    return [t1, t2, t3]


def buat_grafik_pasar(df: pd.DataFrame, keyword: str, folder=config.OUTPUT_DIR) -> dict[str, Path]:
    """
    Menghasilkan 3 grafik visual:
    1. Distribusi harga (Histogram + Garis Median)
    2. Scatter plot Harga vs Terjual (Peta Hot Sellers)
    3. Diagram batang Kota Asal Penjual
    Mengembalikan dict path file gambar.
    """
    sub = df[df["keyword"].str.lower() == keyword.lower().strip()]
    if sub.empty:
        return {}

    sub_bersih = bersihkan_outlier_iqr(sub)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}

    slug = keyword.replace(" ", "_").lower()

    # 1. Grafik Distribusi Harga
    fig, ax = plt.subplots(figsize=(8, 4.8))
    harga_juta = sub_bersih["harga"] / 1_000_000
    n, bins, patches = ax.hist(harga_juta, bins=15, color="#BFDBFE", edgecolor="#2563EB", alpha=0.8)
    median_juta = sub_bersih["harga"].median() / 1_000_000
    ax.axvline(median_juta, color="#DC2626", linestyle="--", linewidth=2, label=f"Median: Rp {sub_bersih['harga'].median():,.0f}")
    ax.set_title(f"Distribusi Harga Pasar: {keyword.title()}", loc="left", fontweight="bold", fontsize=12)
    ax.set_xlabel("Harga (Juta Rupiah)")
    ax.set_ylabel("Frekuensi Produk")
    ax.legend(loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p1 = folder / f"grafik_distribusi_{slug}.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    paths["distribusi"] = p1

    # 2. Grafik Scatter Plot (Harga vs Terjual)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    scatter = ax.scatter(
        harga_juta,
        sub_bersih["terjual"],
        c=sub_bersih["rating"],
        cmap="viridis",
        s=60,
        alpha=0.75,
        edgecolor="none",
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Rating Produk")
    ax.set_title(f"Peta Penjualan vs Harga: {keyword.title()}", loc="left", fontweight="bold", fontsize=12)
    ax.set_xlabel("Harga (Juta Rupiah)")
    ax.set_ylabel("Estimasi Unit Terjual")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    p2 = folder / f"grafik_scatter_{slug}.png"
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    paths["scatter"] = p2

    # 3. Grafik Kota Penjual
    fig, ax = plt.subplots(figsize=(8, 4.8))
    kota = sub["lokasi_toko"].value_counts().head(7)
    if not kota.empty:
        ax.barh(kota.index, kota.values, color=WARNA_UTAMA)
        ax.invert_yaxis()
        ax.set_title(f"7 Kota Asal Pengiriman Terbanyak: {keyword.title()}", loc="left", fontweight="bold", fontsize=12)
        ax.set_xlabel("Jumlah Penawaran Toko")
        ax.bar_label(ax.containers[0], padding=3)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        p3 = folder / f"grafik_kota_{slug}.png"
        fig.savefig(p3, dpi=140)
        plt.close(fig)
        paths["kota"] = p3

    return paths
