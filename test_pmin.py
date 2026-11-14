import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from scraper import parse_html_produk

async def test():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, args=['--window-position=-3000,-3000', '--window-size=1366,768'])
        ctx = await b.new_context(locale='id-ID', timezone_id='Asia/Jakarta', viewport={'width': 1366, 'height': 768})
        page = await ctx.new_page()
        await Stealth().apply_stealth_async(page)
        
        # URL dengan pmin=5000000 (Filter harga minimum Rp 5.000.000)
        url = 'https://www.tokopedia.com/search?st=&q=iphone+15&srp_component_id=02.01.00.00&pmin=5000000&navsource=&page=1'
        print('Navigasi ke:', url)
        await page.goto(url, wait_until='load', timeout=35000)
        await asyncio.sleep(4)
        for _ in range(4):
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(0.5)
        content = await page.content()
        produk = parse_html_produk(content, 'iphone 15')
        print(f'Total produk terekstrak (pmin=5jt): {len(produk)}')
        for p in produk[:15]:
            print(f"Rp {p['harga']:>12,.0f} | {p['nama_produk']}")
        await b.close()

asyncio.run(test())
