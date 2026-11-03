import sys, json
from datetime import date
sys.path.insert(0, '.')
import build_events as B
seen = {}
orig = B.town_area
def spy(address, city):
    a = orig(address, city)
    seen.setdefault((address, city, a), 0); seen[(address, city, a)] += 1
    return a
B.town_area = spy
B.read_tonamel(date.today(), print)
for (addr, city, a), n in sorted(seen.items(), key=lambda x: x[0][1]):
    print('ADDR', json.dumps([city, a, addr, n], ensure_ascii=False))
