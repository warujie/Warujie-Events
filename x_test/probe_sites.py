# Probe (work branch only): why some Hareruya events have no fee
import json, re, sys, time, collections
sys.path.insert(0, ".")
import build_events as b
fees = json.load(open("/tmp/r2/hareruya_fees.json"))
cache = fees["fees"]
ev = json.load(open("/tmp/r2/events.json"))
print("fees updated", fees.get("updated"), "events updated", ev.get("updated"))
print("cache entries", len(cache), "with fee", sum(1 for v in cache.values() if v.get("fee") is not None),
      "read dates", collections.Counter(v.get("read") for v in cache.values()))
har = [e for e in ev["events"] if e.get("shop") == "hareruya"]
pairs = {f"{e['store']}|{e['name']}" for e in har}
print("hareruya events", len(har), "with fee", sum(1 for e in har if e.get("fee") is not None), "pairs", len(pairs),
      "pairs in cache", sum(1 for k in pairs if k in cache), "cached with None fee", sum(1 for k in pairs if k in cache and cache[k].get("fee") is None))
mach = [e for e in har if "町田" in e["store"]]
seen = set()
for e in sorted(mach, key=lambda e: e["d"]):
    k = f"{e['store']}|{e['name']}"
    if k in seen: continue
    seen.add(k)
    print(e["d"], e.get("fee"), "cache:", json.dumps(cache.get(k), ensure_ascii=False)[:120] if k in cache else "NOT IN CACHE", "|", e["name"][:50])
# read a few pages cached with None fee, show the text around 参加費
nones = [(k, v) for k, v in cache.items() if v.get("fee") is None][:5]
for k, v in nones:
    time.sleep(4)
    try:
        html = b.fetch(v["url"])
    except Exception as x:
        print("ERR", v["url"], x); continue
    i = html.find("参加費")
    print("\n====", k, v["url"], "found 参加費 at", i)
    for m in re.finditer("参加費", html):
        print("  ...", re.sub(r"\s+", " ", html[max(0, m.start()-200):m.start()+300]))
        break
    print("  parsed:", b.hareruya_fee(html))
