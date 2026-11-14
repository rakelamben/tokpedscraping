# Bot Telegram Intelijen Pasar Tokopedia

Sistem otomasi riset pasar dan bot Telegram berbasis **Playwright-Stealth**, **BeautifulSoup**, **Pandas**, dan **SQLite** untuk menganalisis kondisi pasar produk di Tokopedia berdasarkan kata kunci pencarian.

---

## 🚀 Alur Kerja Pipeline (End-to-End)

```text
Tokopedia.com ──► scraper.py ──► data/tokopedia_pasar.db ──► analisis.py ──► laporan.py ──► output/*.xlsx, *.pdf
  (Pencarian)       (Playwright +        (SQLite Upsert)       (Pandas IQR +      (Excel + PDF)
                     BeautifulSoup)                            Matplotlib)
                                                │
                                                └──► bot.py (Bot Telegram Intelijen Pasar)
```

---

## 📁 Struktur Direktori

| File / Folder   | Lapisan          | Deskripsi                                                                                           |
| :-------------- | :--------------- | :-------------------------------------------------------------------------------------------------- |
| `config.py`   | Konfigurasi      | URL pencarian, delay acak, token, path direktori.                                                   |
| `scraper.py`  | Pengambilan Data | Playwright-Stealth + Smart Scroll + auto-click "Muat Lebih Banyak" + parser BeautifulSoup.          |
| `db.py`       | Penyimpanan Data | Skema tabel SQLite (`produk_pasar`, `snapshot_pasar`, `riwayat_harga`, `langganan`).        |
| `analisis.py` | Intelijen Pasar  | Pembersihan outlier IQR, estimasi harga wajar (median), seleksi Best Value, generator 3 grafik.     |
| `laporan.py`  | Dokumen Laporan  | Ekspor spreadsheet Excel (`.xlsx`) dan ringkasan eksekutif PDF (`.pdf`).                        |
| `pesan.py`    | Format Pesan     | Pure formatters pesan Telegram (teruji 100% via unit test).                                         |
| `bot.py`      | Antarmuka Bot    | Bot Telegram asinkron dengan kontrol antrean `asyncio.Lock()`, cooldown, dan `JobQueue` harian. |
| `main.py`     | CLI & Runner     | Titik masuk terminal untuk menjalankan scraping mandiri atau mode penjadwalan harian.               |
| `tests/`      | Pengujian        | 13 unit test offline pytest (parser, database, analisis, format pesan).                             |
| `data/`       | Database         | Lokasi file database SQLite (`tokopedia_pasar.db`).                                               |
| `output/`     | Keluaran         | File grafik `.png`, spreadsheet `.xlsx`, dan laporan `.pdf`.                                  |
| `logs/`       | Pencatatan       | Log riwayat eksekusi pipeline (`pipeline.log`).                                                   |

---

## 🛠️ Panduan Menjalankan di Lokal

### 1. Salin File Environment

```bash
cp .env.example .env
```

Buka file `.env` dan masukkan:

- `BOT_TOKEN`: Token dari @BotFather.
- `ADMIN_CHAT_ID`: ID akun Telegram Anda.

### 2. Jalankan Pengujian Offline

```bash
python -m pytest -v
```

*(Memastikan seluruh modul parser, database, dan analisis berfungsi normal)*.

### 3. Menjalankan Pipeline CLI

```bash
# Jalankan riset pasar untuk kata kunci tertentu (misal 2 putaran infinite scroll)
python main.py --keyword "iphone 15" --scroll 2

# Simpan raw HTML hasil infinite scroll ke folder output
python main.py --keyword "iphone 15" --scroll 2 --raw

# Buat ulang grafik dan laporan dokumen dari database tanpa scraping ulang
python main.py --tanpa-scrape --keyword "iphone 15"

# Jalankan mode penjadwalan harian di terminal (setiap 08:00 WIB)
python main.py --jadwal
```

### 4. Menyalakan Bot Telegram

```bash
python bot.py
```

Buka bot di Telegram dan kirim perintah `/start`.

---

## 🤖 Perintah Bot Telegram

| Perintah                 | Deskripsi                                                                                            |
| :----------------------- | :--------------------------------------------------------------------------------------------------- |
| `/pasar <keyword>`     | Menampilkan estimasi harga wajar (median), rentang harga riil, total penjualan, & % toko official.   |
| `/bestvalue <keyword>` | Menampilkan 5 produk nilai terbaik (rating $\ge 4.7$, harga $\le$ median pasar, terjual teruji). |
| `/toko <keyword>`      | Menampilkan 5 kota asal pengiriman terbanyak dan sebaran reputasi penjual.                           |
| `/grafik <keyword>`    | Mengirimkan 3 grafik visual (Distribusi Harga, Peta Penjualan vs Harga, dan Kota Penjual).           |
| `/laporan <keyword>`   | Mengirimkan file dokumen spreadsheet Excel (`.xlsx`) dan PDF eksekutif langsung ke chat.           |
| `/scrape <keyword>`    | Memicu scraping realtime kata kunci baru (diamankan dengan antrean lock & cooldown).                 |
| `/langganan <keyword>` | Menerima rekap laporan intelijen pasar harian otomatis setiap pukul 08:00 WIB.                       |
| `/berhenti`            | Menghentikan langganan laporan harian.                                                               |
| `/help`                | Menampilkan panduan bantuan lengkap.                                                                 |

---

## ☁️ Panduan Deployment di IBM Cloud (https://cloud.ibm.com/)

### Menggunakan IBM Cloud Virtual Server Instance (Ubuntu Linux):

1. Buat Virtual Server for VPC di portal IBM Cloud dengan OS **Ubuntu 22.04 / 24.04 LTS**.
2. Hubungkan Floating IP dan login via SSH:
   ```bash
   ssh root@<IP_PUBLIK_IBM_CLOUD>
   ```
3. Update sistem dan clone repo:
   ```bash
   apt update && apt install -y python3-venv python3-pip git
   git clone <repo_url> ~/tokopedia-scraper
   cd ~/tokopedia-scraper
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   playwright install-deps
   cp .env.example .env && nano .env
   ```
4. Pasang Daemon `systemd`:
   Buat file `/etc/systemd/system/tokopedia-bot.service`:
   ```ini
   [Unit]
   Description=Bot Telegram Intelijen Pasar Tokopedia
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/tokopedia-scraper
   ExecStart=/root/tokopedia-scraper/venv/bin/python bot.py
   Restart=always
   RestartSec=10
   EnvironmentFile=/root/tokopedia-scraper/.env

   [Install]
   WantedBy=multi-user.target
   ```
5. Aktifkan service:
   ```bash
   systemctl daemon-reload
   systemctl enable tokopedia-bot
   systemctl start tokopedia-bot
   systemctl status tokopedia-bot
   ```
