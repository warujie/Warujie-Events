# One-off probe (work branch only): saves the raw pages of CANTRIP's and CARDWINGS' event listings.
import time, urllib.request, os
UA = "WarujieEvents/1.0 (+https://warujie.jp)"
urls = {
 "cantrip_robots.txt": "https://cantripmtg.com/robots.txt",
 "cantrip_store.html": "https://cantripmtg.com/pages/hachiojistore",
 "cw_tournament.html": "https://card-wings.com/tournament/",
}
os.makedirs("x_test/probe", exist_ok=True)
for name, u in urls.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r:
            open(f"x_test/probe/{name}", "wb").write(r.read())
        print(name, "ok")
    except Exception as e:
        print(name, e)
    time.sleep(4)
