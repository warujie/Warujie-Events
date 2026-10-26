# One-off probe (work branch only): Tokyo MTG's event calendar, and where Masters Square's shop links lead.
import time, urllib.request, os
UA = "WarujieEvents/1.0 (+https://warujie.jp)"
os.makedirs("x_test/probe", exist_ok=True)
for name, u in {"tokyomtg_cal.html": "https://tokyomtg.com/content.html?p=eventcalendar",
                "ms1": "https://t.co/UDoOW5iksq", "ms2": "https://t.co/rLlLGZkCCE", "ms3": "https://t.co/8O6UkqHC7a", "ms4": "https://t.co/nnCE7gZvUC"}.items():
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r:
            body = r.read()
            print(name, r.geturl(), len(body))
            open(f"x_test/probe/{name}" + ("" if "." in name else ".html"), "wb").write(body)
    except Exception as e:
        print(name, e)
    time.sleep(4)
