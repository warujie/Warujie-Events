# One-off probe (work branch only): saves the raw pages of CANTRIP's and CARDWINGS' event listings.
import time, urllib.request, os
UA = "WarujieEvents/1.0 (+https://warujie.jp)"
Q = "search_element_1=156&search_element_2=&search_element_3=&search_element_4=&csp=search_add&feadvns_max_line_0=5&fe_form_no=0"
urls = {
 "cw_mtg.html": "https://card-wings.com/?" + Q,
 "cw_mtg_p2.html": "https://card-wings.com/page/2/?" + Q,
 "cw_detail.html": "https://card-wings.com/tournament/tournament-3953/",
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
