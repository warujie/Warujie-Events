#!/usr/bin/env python3
"""Magic events from shops' calendar pictures on X, read automatically (the owner's request,
2026-10-25: automatic, but only the accounts listed in x_accounts.json, to keep the cost down).

Each account in x_accounts.json is read once a week, on Sunday (X_WEEKDAY: the nightly run of
3:30 on Sunday morning in Japan; the owner's choice of 2026-10-25). An account not read since the
last Sunday (a new one, or one cut off by the night's limit) is read in the next nightly run:
1. X's API (pay-per-use, the owner's developer account; secret X_BEARER_TOKEN) gives the account's
   own new posts since its last reading (`since_id`), at most X_MAX_POSTS, with any description the
   shop typed for a picture (alt text, free). Reposts and replies are left out. X bills each post
   read ($0.005 in 2026-10).
2. Each picture in those posts is first shown to a small, cheap model (SCREEN_MODEL), which only
   says whether it is a schedule or announcement of Magic events.
3. Only those pictures go to READ_MODEL, which lists the Magic events in them (day, start, name,
   formats, fee). At most X_MAX_READS pictures a night; an account cut off by that limit (or by an
   error) is read again the next night from where it stopped, and its week starts once it is done.

The events are kept in x_events.json (published to R2 beside events.json, with each account's
`since_id`, so nothing is read or paid for twice). build_events.py puts them into events.json as
shop "x" (the site tags them X投稿から), each linking to its post. An event checked by hand in
manual_events.json wins over one read here; a newer post's reading replaces an older one's.

    X_BEARER_TOKEN=… ANTHROPIC_API_KEY=… python3 x_reader.py --state x_events.json
    python3 x_reader.py --state x_events.json --dry-run     # X only: list the new pictures, read none
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from build_events import FORMAT_JA, JST, USER_AGENT, formats_in, same_event

HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS = os.path.join(HERE, "x_accounts.json")
X_API = "https://api.x.com/2"
X_WEEKDAY = 6           # each account is read once a week, on Sunday in Japan (the owner's choice, 2026-10-25)
X_MAX_POSTS = 25        # per account and reading (about a week of a busy shop's posts; X's page is 5-100)
X_MAX_READS = 20        # pictures read by READ_MODEL per night, whatever the accounts post
X_POST_DAYS = 45        # posts older than this are never read (a first night, or an account added later)
SCREEN_MODEL = "claude-haiku-5-5"
READ_MODEL = "claude-opus-5-5"
HANDLE_RE = re.compile(r"[A-Za-z0-9_]{1,15}")

SCREEN_PROMPT = """This picture was posted on X by a Japanese game shop{store}. Is it a schedule, calendar
or announcement that gives the date of at least one Magic: The Gathering event (a tournament,
league, draft, prerelease, store championship…) at the shop? A card, a product, a price list, a
sale or another game's events alone is "no"."""

READ_PROMPT = """This picture was posted on X on {posted} (Japan time) by the Japanese game shop
"{store}" ({place}). The post's text:
---
{text}
---
List every Magic: The Gathering event the picture (and the post's text) gives a date for, at this
shop. Leave out other games' events (Pokémon, Yu-Gi-Oh!, Duel Masters, One Piece, Lorcana…) and
anything that is not an event (sales, store hours, holidays).

For each event:
- d: the date, YYYY-MM-DD. The picture often gives only the month and day: take the year that puts
  the date nearest after the posting day (a calendar posted in late December for January is next
  year).
- t: the start time HH:MM (24-hour), or "" when none is given. When it gives doors (受付) and a start
  (開始), take the start.
- name: the event's name as written, in the picture's language (FNM, スタンダード大会, ドラフト…).
  Don't add the shop's name.
- f: its formats, from: standard, pioneer, modern, legacy, vintage, pauper, commander, premodern,
  limited (any draft, sealed or prerelease). [] when the picture doesn't say.
- fee: the entry fee in yen (0 when free), or null when none is given or a pack must be bought
  instead. fee_to: the higher fee when there are two (e.g. by pack language), else null.

A recurring event shown on several days is one entry per day. Only what the picture shows: never
guess a day, a time or a fee. If you can't read something, leave that event out."""

READ_SCHEMA = {
    "type": "object",
    "properties": {"events": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "d": {"type": "string"}, "t": {"type": "string"}, "name": {"type": "string"},
            "f": {"type": "array", "items": {"type": "string", "enum": list(FORMAT_JA)}},
            "fee": {"type": ["integer", "null"]}, "fee_to": {"type": ["integer", "null"]},
        },
        "required": ["d", "t", "name", "f", "fee", "fee_to"],
        "additionalProperties": False,
    }}},
    "required": ["events"],
    "additionalProperties": False,
}
SCREEN_SCHEMA = {"type": "object", "properties": {"magic_events": {"type": "boolean"}},
                 "required": ["magic_events"], "additionalProperties": False}


def x_get(path, params, token):
    url = f"{X_API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"X API {path}: HTTP {e.code} {body}") from None


def picture(url):
    """A post's picture, as X serves it to anyone (pbs.twimg.com), at its large size."""
    req = urllib.request.Request(url + "?name=large", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        kind = r.headers.get_content_type()
        return r.read(), kind if kind in ("image/jpeg", "image/png", "image/webp", "image/gif") else "image/jpeg"


def ask(client, model, content, schema, effort):
    msg = client.messages.create(model=model, max_tokens=16000, output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                                 messages=[{"role": "user", "content": content}])
    if msg.stop_reason not in ("end_turn", "stop_sequence"):
        raise RuntimeError(f"{model} stopped: {msg.stop_reason}")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text), msg.usage


def valid_events(rows, account, url, posted, read_day):
    """The model's events that hold together: a real date from a week before the post to four months
    after it, a time, a name; the account's store and place."""
    out = []
    for r in rows:
        try:
            d = date.fromisoformat(r.get("d", ""))
        except ValueError:
            continue
        t = r.get("t") or ""
        if not (posted - timedelta(days=7) <= d <= posted + timedelta(days=120)) or not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d|", t) or not str(r.get("name") or "").strip():
            continue
        t = f"{int(t.split(':')[0]):02d}:{t.split(':')[1]}" if t else ""
        fee = r.get("fee") if isinstance(r.get("fee"), int) and 0 <= r["fee"] <= 100000 else None
        fee_to = r.get("fee_to") if fee is not None and isinstance(r.get("fee_to"), int) and fee < r["fee_to"] <= 100000 else None
        fs = [f for f in r.get("f") or [] if f in FORMAT_JA] or formats_in(r["name"])
        e = {"shop": "x", "d": d.isoformat(), "t": t, "p": account["p"], "c": account.get("c", ""), "store": account["store"],
             "name": r["name"].strip()[:80], "f": fs, "url": url, "read": read_day}
        if fee is not None:
            e["fee"] = fee
        if fee_to is not None:
            e["fee_to"] = fee_to
        out.append(e)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="x_events.json: read (when it exists) and updated")
    ap.add_argument("--dry-run", action="store_true", help="read X only; list the new pictures; no model, no state change")
    ap.add_argument("--all", action="store_true", help="read every account now, whatever the day (testing)")
    ap.add_argument("--max-reads", type=int, default=X_MAX_READS, help="pictures read per night at most")
    ap.add_argument("--accounts", default=ACCOUNTS, help="the accounts file (x_accounts.json; another for testing)")
    args = ap.parse_args()
    log = lambda s: print(s, flush=True)
    token = os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        log("No X_BEARER_TOKEN: nothing read.")
        return
    client = None
    if not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("No ANTHROPIC_API_KEY: X is not read either (its posts would be paid for and not read).")
            return
        import anthropic
        client = anthropic.Anthropic()
    with open(args.accounts, encoding="utf-8") as f:
        accounts = [a for a in json.load(f).get("accounts", []) if HANDLE_RE.fullmatch(a.get("handle", "")) and a.get("store")
                    and isinstance(a.get("p"), int) and 1 <= a["p"] <= 47]
    try:
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, ValueError):
        state = {}
    seen = state.get("accounts", {})
    kept = state.get("events", [])
    now = datetime.now(JST)
    today = now.date()
    last_sunday = (today - timedelta(days=(today.weekday() - X_WEEKDAY) % 7)).isoformat()
    posts_read = screened = reads = 0
    cost_note = []
    for a in accounts:
        h = a["handle"].lower()
        s = seen.setdefault(h, {})
        if s.get("read") and not args.all and s["read"] >= last_sunday:
            continue   # read since the last Sunday
        if reads >= args.max_reads:
            log(f"@{a['handle']}: tonight's {args.max_reads} readings are used; read tomorrow")
            continue
        try:
            if not s.get("id"):
                s["id"] = x_get(f"/users/by/username/{a['handle']}", {}, token)["data"]["id"]
            params = {"max_results": X_MAX_POSTS, "exclude": "retweets,replies", "expansions": "attachments.media_keys",
                      "media.fields": "type,url,alt_text", "tweet.fields": "created_at"}
            if s.get("since_id"):
                params["since_id"] = s["since_id"]
            else:
                params["start_time"] = (datetime.now(timezone.utc) - timedelta(days=X_POST_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
            got = x_get(f"/users/{s['id']}/tweets", params, token)
        except Exception as e:  # one account's trouble doesn't stop the others
            log(f"@{a['handle']}: {e}")
            continue
        posts = got.get("data", [])
        if len(posts) >= X_MAX_POSTS and s.get("since_id"):
            log(f"@{a['handle']}: more than {X_MAX_POSTS} posts this week; only the latest are read")
        media = {m["media_key"]: m for m in got.get("includes", {}).get("media", [])}
        posts_read += len(posts)
        log(f"@{a['handle']}: {len(posts)} new posts")
        done = s.get("since_id")   # the newest post whose pictures are all dealt with
        finished = True            # every new post dealt with: the account's week starts again
        for p in sorted(posts, key=lambda p: int(p["id"])):   # oldest first, so a newer reading replaces an older
            pics = [media[k] for k in p.get("attachments", {}).get("media_keys", []) if media.get(k, {}).get("type") == "photo" and media[k].get("url")]
            url = f"https://x.com/{a['handle']}/status/{p['id']}"
            posted = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")).astimezone(JST)
            if not pics:
                done = p["id"]
                continue
            log(f"  {url} ({posted:%Y-%m-%d}): {len(pics)} pictures; {' '.join(m['url'] for m in pics)}")
            if args.dry_run:
                continue
            found, ok = [], True
            for m in pics:
                pic = m["url"]
                alt = f"\nThe shop's description of the picture: {m['alt_text'][:1000]}" if m.get("alt_text") else ""
                try:
                    data, kind = picture(pic)
                    img = {"type": "image", "source": {"type": "base64", "media_type": kind, "data": base64.standard_b64encode(data).decode()}}
                    screened += 1
                    yes, _ = ask(client, SCREEN_MODEL, [img, {"type": "text", "text": SCREEN_PROMPT.format(store=f" ({a['store']})") + alt}], SCREEN_SCHEMA, "low")
                    if not yes["magic_events"]:
                        log(f"    {pic}: not a Magic schedule")
                        continue
                    if reads >= args.max_reads:
                        log(f"    {pic}: a Magic schedule, but tonight's {args.max_reads} readings are used; read tomorrow")
                        ok = False
                        break
                    reads += 1
                    place = " ".join(x for x in (a.get("c", ""),) if x) or f"prefecture {a['p']}"
                    out, usage = ask(client, READ_MODEL, [img, {"type": "text", "text": READ_PROMPT.format(
                        posted=f"{posted:%Y-%m-%d}", store=a["store"], place=place, text=p.get("text", "")[:1500]) + alt}], READ_SCHEMA, "medium")
                    evs = valid_events(out.get("events", []), a, url, posted.date(), today.isoformat())
                    cost_note.append(f"{usage.input_tokens}+{usage.output_tokens}")
                    log(f"    {pic}: {len(evs)} Magic events (of {len(out.get('events', []))} given)")
                    for e in evs:
                        log(f"      {e['d']} {e['t'] or '--:--'} {e['name']} {','.join(e['f'])} {e.get('fee', '')}")
                    # the same event twice in one post (a picture in Japanese and one in English) is kept once
                    found += [e for e in evs if not any(same_event(e, f) for f in found)]
                except Exception as e:   # tried again tomorrow (X bills the post again; the screening is cheap)
                    log(f"    {pic}: {e}")
                    ok = False
                    break
            if not ok:
                finished = False
                break
            # a newer post's reading of the same event replaces the older one
            kept = [k for k in kept if not any(same_event(k, n) for n in found)] + found
            done = p["id"]
        if done and not args.dry_run:
            s["since_id"] = done
        if finished and not args.dry_run:
            s["read"] = today.isoformat()
    log(f"X: {posts_read} posts read (about ${posts_read * 0.005:.3f}); {screened} pictures screened, {reads} read"
        + (f" (tokens in+out: {', '.join(cost_note)})" if cost_note else ""))
    if args.dry_run:
        return
    first = (today - timedelta(days=1)).isoformat()
    kept = [k for k in kept if k["d"] >= first]   # past events go
    with open(args.state, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "accounts": seen,
                   "events": sorted(kept, key=lambda e: (e["d"], e["t"], e["store"]))}, f, ensure_ascii=False, indent=1)
    log(f"Wrote {len(kept)} events to {args.state}")


if __name__ == "__main__":
    sys.exit(main())
