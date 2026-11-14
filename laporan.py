"""
Lapisan 4: DOKUMEN LAPORAN RISET PASAR (Excel & PDF).
Menghasilkan spreadsheet .xlsx berformat rapi dan dokumen PDF eksekutif siap kirim.
"""
from datetime import date
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import analisis
import config


def buat_excel(df: pd.DataFrame, keyword: str, grafik: dict = None, folder=config.OUTPUT_DIR) -> Path:
    """Membuat laporan spreadsheet Excel (.xlsx) dengan tabel dan grafik tersemat."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    slug = keyword.replace(" ", "_").lower()
    nama_file = folder / f"laporan_pasar_{slug}_{date.today():%Y-%m-%d}.xlsx"

    sub = df[df["keyword"].str.lower() == keyword.lower().strip()]
    r = analisis.ringkasan_pasar(df, keyword)
    bv = analisis.cari_best_value(df, keyword, limit=10)

    with pd.ExcelWriter(nama_file, engine="openpyxl") as w:
        # Sheet 1: Ringkasan Pasar
        pd.DataFrame(list(r.items()), columns=["Indikator Pasar", "Nilai"]).to_excel(
            w, sheet_name="Ringkasan Pasar", index=False
        )

        # Sheet 2: Best Value
        if not bv.empty:
            bv_export = bv[["nama_produk", "harga", "rating", "terjual", "toko", "lokasi_toko", "badge_toko", "url"]].copy()
            bv_export.to_excel(w, sheet_name="Best Value", index=False)

        # Sheet 3: Data Seluruh Produk
        sub_export = sub[["nama_produk", "harga", "rating", "terjual", "toko", "lokasi_toko", "badge_toko", "url"]].copy()
        sub_export.sort_values(by="harga").to_excel(w, sheet_name="Semua Produk", index=False)

    # Format Tampilan dengan openpyxl
    wb = load_workbook(nama_file)
    hijau_header = PatternFill("solid", fgColor="03AC0E")
    font_header = Font(bold=True, color="FFFFFF")

    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = font_header
            cell.fill = hijau_header
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = "A2"
        for col in ws.columns:
            lebar = max(len(str(c.value or "")) for c in col[:150])
            ws.column_dimensions[col[0].column_letter].width = min(max(lebar + 3, 12), 55)

    # Sematkan gambar grafik di sheet Ringkasan Pasar
    if grafik and "distribusi" in grafik and Path(grafik["distribusi"]).exists():
        ws_ringkas = wb["Ringkasan Pasar"]
        img = XlImage(str(grafik["distribusi"]))
        img.width, img.height = 550, 330
        ws_ringkas.add_image(img, "D2")

    wb.save(nama_file)
    return nama_file


def _tabel_pdf(df: pd.DataFrame, col_widths=None) -> Table:
    """Helper membuat tabel terformat untuk ReportLab."""
    data = [df.columns.tolist()] + df.astype(str).values.tolist()
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#03AC0E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]))
    return t


def buat_pdf(df: pd.DataFrame, keyword: str, grafik: dict = None, folder=config.OUTPUT_DIR) -> Path:
    """Menghasilkan laporan riset pasar eksekutif dalam format PDF."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    slug = keyword.replace(" ", "_").lower()
    nama_file = folder / f"laporan_pasar_{slug}_{date.today():%Y-%m-%d}.pdf"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Judul", parent=styles["Title"], textColor=colors.HexColor("#03AC0E"), fontSize=20)
    sub_style = ParagraphStyle("SubJudul", parent=styles["Normal"], textColor=colors.dimgrey, fontSize=9)
    h2_style = ParagraphStyle("Heading2", parent=styles["Heading2"], textColor=colors.HexColor("#1F2937"), fontSize=12)

    r = analisis.ringkasan_pasar(df, keyword)
    bv = analisis.cari_best_value(df, keyword, limit=5)
    temuan = analisis.temuan_pasar(df, keyword)

    story = [
        Paragraph(f"Laporan Intelijen Pasar: {keyword.title()}", title_style),
        Paragraph(f"Tanggal: {date.today():%d %B %Y} &middot; Sumber Data: Tokopedia.com", sub_style),
        Spacer(1, 10),
        Paragraph(
            f"Berdasarkan analisis terhadap <b>{r.get('total_sampel', 0)} penawaran produk</b> di Tokopedia, "
            f"estimasi harga wajar (median) berada di angka <b>Rp {r.get('harga_median', 0):,.0f}</b> "
            f"dengan rentang pasar Rp {r.get('harga_min', 0):,.0f} s/d Rp {r.get('harga_max', 0):,.0f}. "
            f"Total estimasi unit yang telah terjual mencapai <b>{r.get('total_terjual', 0):,}+ unit</b>.",
            styles["Normal"]
        ),
        Spacer(1, 10),
        Paragraph("Temuan Kunci Pasar", h2_style),
    ]

    for i, t in enumerate(temuan, 1):
        story.append(Paragraph(f"<b>{i}.</b> {t}", styles["Normal"]))
        story.append(Spacer(1, 4))

    # Sematkan Rekomendasi Best Value jika ada
    if not bv.empty:
        story.append(Spacer(1, 8))
        story.append(Paragraph("5 Rekomendasi Produk Best Value", h2_style))
        bv_tabel = bv[["nama_produk", "harga", "rating", "terjual", "toko"]].copy()
        bv_tabel["nama_produk"] = bv_tabel["nama_produk"].apply(lambda x: x[:35] + "..." if len(x) > 35 else x)
        bv_tabel["harga"] = bv_tabel["harga"].apply(lambda x: f"Rp {x:,.0f}")
        story.append(_tabel_pdf(bv_tabel, col_widths=[190, 80, 45, 65, 100]))

    # Sematkan Grafik
    if grafik:
        for kunci, label in [("distribusi", "Distribusi Harga Pasar"), ("scatter", "Peta Penjualan vs Harga")]:
            if kunci in grafik and Path(grafik[kunci]).exists():
                story.append(Spacer(1, 12))
                story.append(Paragraph(label, h2_style))
                story.append(Image(str(grafik[kunci]), width=450, height=270))

    SimpleDocTemplate(str(nama_file), pagesize=A4, title=f"Laporan Pasar Tokopedia - {keyword}").build(story)
    return nama_file
