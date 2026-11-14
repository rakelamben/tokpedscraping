import sqlite3
import pandas as pd

conn = sqlite3.connect(r'D:\bot_tele\tokopedia-scraper\data\tokopedia_pasar.db')
df = pd.read_sql_query('SELECT nama_produk, harga, terjual, rating, toko, badge_toko FROM produk_pasar', conn)
conn.close()

print(f'Total produk: {len(df)}')
print('Statistik Harga:')
print(df['harga'].describe())

print('\n--- Semua 55 Nama Produk dan Harga ---')
for idx, row in df.sort_values(by='harga').iterrows():
    print(f"Rp {row['harga']:>12,.0f} | {row['nama_produk'][:70]}")
