#!/usr/bin/env python3
"""A one-off helper on the work branch (not published): looks up X accounts (name, place, profile)
and searches the last 7 days of posts for shops announcing Magic tournaments with pictures, to
find shops that post their events only on X. Costs: $0.01 per account looked up, $0.005 per post
the search returns (at most --max posts)."""
import argparse, json, os, urllib.parse
from x_reader import x_get

USER_FIELDS = "name,username,location,description,url"
QUERY = "(MTG OR マジックザギャザリング OR \"マジック:ザ・ギャザリング\" OR ギャザ) (大会 OR 店舗大会 OR イベントスケジュール OR 大会スケジュール OR 大会日程) has:images -is:retweet -is:reply lang:ja"

ap = argparse.ArgumentParser()
ap.add_argument("--users", default="")
ap.add_argument("--max", type=int, default=100)
args = ap.parse_args()
token = os.environ["X_BEARER_TOKEN"]
out = {"users": [], "authors": {}}
for h in [u for u in args.users.split(",") if u]:
    out["users"].append(x_get(f"/users/by/username/{h}", {"user.fields": USER_FIELDS}, token).get("data"))
got, nxt = 0, None
while got < args.max:
    p = {"query": QUERY, "max_results": min(100, args.max - got), "expansions": "author_id", "user.fields": USER_FIELDS, "tweet.fields": "created_at"}
    if nxt: p["next_token"] = nxt
    r = x_get("/tweets/search/recent", p, token)
    posts = r.get("data", [])
    got += len(posts)
    users = {u["id"]: u for u in r.get("includes", {}).get("users", [])}
    for t in posts:
        u = users.get(t["author_id"], {})
        a = out["authors"].setdefault(u.get("username", t["author_id"]), dict(u, posts=[]))
        a["posts"].append({"id": t["id"], "text": t["text"][:200]})
    nxt = r.get("meta", {}).get("next_token")
    if not nxt or not posts: break
print(f"{got} posts, {len(out['authors'])} accounts")
json.dump(out, open("x_test/find.json", "w"), ensure_ascii=False, indent=1)
