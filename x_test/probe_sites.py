# One-off probe (work branch only): Masters Square's Magic store, and Tokyo MTG's calendar in a browser.
import time, urllib.request, os
UA = "WarujieEvents/1.0 (+https://warujie.jp)"
os.makedirs("x_test/probe", exist_ok=True)
for name, u in {"sq3_robots.txt": "https://www.square-3rd.jp/robots.txt", "sq3.html": "https://www.square-3rd.jp/page/1",
                "sq3_search.html": "https://www.square-3rd.jp/product-list?keyword=%E7%A8%B2%E5%A6%BB"}.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r:
            body = r.read(); print(name, r.geturl(), len(body)); open(f"x_test/probe/{name}", "wb").write(body)
    except Exception as e:
        print(name, e)
    time.sleep(4)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(user_agent=UA)
        r = pg.goto("https://tokyomtg.com/content.html?p=eventcalendar", wait_until="networkidle", timeout=60000)
        print("tokyomtg", r and r.status); pg.wait_for_timeout(3000)
        open("x_test/probe/tokyomtg_cal.html", "w").write(pg.content()); pg.screenshot(path="x_test/probe/tokyomtg_cal.png", full_page=True)
        b.close()
except Exception as e:
    print("tokyomtg", e)
