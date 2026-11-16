#!/usr/bin/env python3
"""The news page of warujie.jp (?view=news): headlines from Magic sites' own RSS/Atom feeds, written
to news.json (docs/README.md, "News page").

Headline, link, date and the site's name only: no article text and no pictures are copied, so every
item sends the reader to the article on its own site. Only feeds a site publishes for others to read,
only where its robots.txt allows our User-Agent, once a night, one feed at a time, PAGE_GAP seconds
apart. Wizards' sites (magic.wizards.com, mtg-jp.com, magic.gg) are never read (their terms forbid
robots; the page links to them instead). A site that asks us to stop comes out of NEWS_SOURCES at once.

The page's shop posts on X come from x_reader.py's x_events.json, which the site reads itself.

  python3 build_news.py --out out/news.json [--only mtggoldfish]
"""
import argparse
import email.utils
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from build_events import USER_AGENT

PAGE_GAP = 4          # seconds between two feeds (as for the shops' event pages)
NEWS_DAYS = 30        # items older than this drop out
NEWS_PER_SOURCE = 15  # newest items kept per site

# The sites read (the owner's choice; add or remove a line). lang: the articles' language (ja/en);
# kind: article (articles and columns) or news (news sites); must: a pattern a headline needs (general
# game news sites: only their Magic headlines); site: the page "more" links to; max: fewer than NEWS_PER_SOURCE
# items for a busy site whose posts would push the others down.
# Official and company sources only (the owner's word, 2026-11-16: no note #MTG, nobody's personal posts).
NEWS_SOURCES = [
    {"id": "4gamer", "name": "4Gamer.net", "lang": "ja", "kind": "news", "site": "https://www.4gamer.net/games/136/G013687/",
     "feed": "https://www.4gamer.net/games/136/G013687/contents.xml", "must": "MTG"},
    {"id": "4gamer-arena", "name": "4Gamer.net（MTGアリーナ）", "lang": "ja", "kind": "news", "site": "https://www.4gamer.net/games/443/G044382/",
     "feed": "https://www.4gamer.net/games/443/G044382/contents.xml"},
    {"id": "automaton", "name": "AUTOMATON", "lang": "ja", "kind": "news", "site": "https://automaton-media.com/",
     "feed": "https://automaton-media.com/feed/", "must": "MTG"},
    {"id": "denfaminico", "name": "電ファミニコゲーマー", "lang": "ja", "kind": "news", "site": "https://news.denfaminicogamer.jp/",
     "feed": "https://news.denfaminicogamer.jp/feed", "must": "MTG"},
    {"id": "gamewatch", "name": "GAME Watch", "lang": "ja", "kind": "news", "site": "https://game.watch.impress.co.jp/",
     "feed": "https://game.watch.impress.co.jp/data/rss/1.0/gmw/feed.rdf", "must": "MTG"},
    {"id": "inside", "name": "インサイド", "lang": "ja", "kind": "news", "site": "https://www.inside-games.jp/",
     "feed": "https://www.inside-games.jp/rss/index.rdf", "must": "MTG"},
    {"id": "mtggoldfish", "name": "MTGGoldfish", "lang": "en", "kind": "article", "site": "https://www.mtggoldfish.com/articles",
     "feed": "https://www.mtggoldfish.com/feed"},
    {"id": "edhrec", "name": "EDHREC", "lang": "en", "kind": "article", "site": "https://edhrec.com/articles",
     "feed": "https://edhrec.com/articles/feed/"},
    {"id": "mtgazone", "name": "MTG Arena Zone", "lang": "en", "kind": "news", "site": "https://mtgazone.com/news/",
     "feed": "https://mtgazone.com/news/feed/"},
    {"id": "draftsim", "name": "Draftsim", "lang": "en", "kind": "article", "site": "https://draftsim.com/blog/",
     "feed": "https://draftsim.com/feed/"},
    {"id": "starcitygames", "name": "Star City Games", "lang": "en", "kind": "article", "site": "https://articles.starcitygames.com/",
     "feed": "https://articles.starcitygames.com/feed/"},
    {"id": "cardkingdom", "name": "Card Kingdom Blog", "lang": "en", "kind": "article", "site": "https://blog.cardkingdom.com/",
     "feed": "https://blog.cardkingdom.com/feed/"},
    {"id": "magicspoiler", "name": "Magic Spoiler", "lang": "en", "kind": "news", "site": "https://www.magicspoiler.com/",
     "feed": "https://www.magicspoiler.com/feed/"},
    {"id": "wargamer", "name": "Wargamer", "lang": "en", "kind": "news", "site": "https://www.wargamer.com/magic-the-gathering",
     "feed": "https://www.wargamer.com/mainrss.xml", "must": "MTG"},
    {"id": "commandersherald", "name": "Commander's Herald", "lang": "en", "kind": "article", "site": "https://commandersherald.com/",
     "feed": "https://commandersherald.com/feed/"},
    {"id": "hipsters", "name": "Hipsters of the Coast", "lang": "en", "kind": "article", "site": "https://www.hipstersofthecoast.com/",
     "feed": "https://www.hipstersofthecoast.com/feed/"},
    {"id": "17lands", "name": "17Lands Blog", "lang": "en", "kind": "article", "site": "https://blog.17lands.com/",
     "feed": "https://blog.17lands.com/feed"},
]
# the words that make a general game site's headline a Magic one (must: "MTG")
MUST = {"MTG": re.compile(r"MTG|マジック[：:・ ]?ザ[・ ]?ギャザリング|Magic: The Gathering|ギャザ", re.I)}
NEVER_HOSTS = ("wizards.com", "mtg-jp.com", "magic.gg")   # Wizards' terms forbid robots: links only

ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def log(s):
    print(s, flush=True)


_robots = {}


def allowed(url):
    """Whether the site's robots.txt lets our User-Agent read the address (no robots.txt: yes)."""
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(root + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                rp.parse(resp.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            rp.parse([] if e.code in (404, 410) else ["User-agent: *", "Disallow: /"])   # unreadable: stay out
        except Exception:
            rp.parse(["User-agent: *", "Disallow: /"])
        _robots[root] = rp
    return _robots[root].can_fetch(USER_AGENT, url)


def clean(s):
    """A headline as plain text: tags and entities out, spaces folded."""
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def when(s):
    """An RSS/Atom date as UTC ISO time, or None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_feed(data):
    """[(title, link, date)] from RSS 2.0, RSS 1.0 (RDF) or Atom; a feed that isn't well-formed XML (a stray &, as
    TCGplayer's) is read item by item with patterns instead."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        text = data.decode("utf-8", "replace")
        out = []
        for it in re.findall(r"<item\b.*?</item>", text, re.S):
            get = lambda tag: (re.search(rf"<{tag}\b[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", it, re.S) or [None, None])[1]
            out.append((get("title"), (get("link") or "").strip(), get("pubDate") or get("dc:date")))
        return out
    out = []
    for it in root.iter("item"):                       # RSS 2.0
        out.append((it.findtext("title"), it.findtext("link"), it.findtext("pubDate") or it.findtext(DC + "date")))
    for it in root.iter(RSS1 + "item"):                # RSS 1.0
        out.append((it.findtext(RSS1 + "title"), it.findtext(RSS1 + "link"), it.findtext(DC + "date")))
    for it in root.iter(ATOM + "entry"):               # Atom
        link = next((l.get("href") for l in it.findall(ATOM + "link") if l.get("rel", "alternate") == "alternate"), None)
        out.append((it.findtext(ATOM + "title"), link, it.findtext(ATOM + "published") or it.findtext(ATOM + "updated")))
    return out


def read_source(src, since):
    feed = src["feed"]
    if any(h in urllib.parse.urlsplit(feed).netloc for h in NEVER_HOSTS):
        raise ValueError("Wizards' sites are never read")
    if not allowed(feed):
        raise PermissionError("robots.txt disallows the feed")
    req = urllib.request.Request(feed, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(5_000_000)
    must = MUST.get(src.get("must"))
    items, seen = [], set()
    for title, link, date in parse_feed(data):
        title, link, d = clean(title)[:160], (link or "").strip(), when(date)
        if not title or not re.match(r"https?://", link) or not d or d < since or link in seen:
            continue
        if must and not must.search(title):
            continue
        seen.add(link)
        items.append({"s": src["id"], "t": title, "u": link.replace("http://", "https://", 1) if link.startswith("http://") else link, "d": d})
    items.sort(key=lambda i: i["d"], reverse=True)
    return items[:src.get("max", NEWS_PER_SOURCE)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="one source id (testing)")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=NEWS_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources, items = [], []
    for i, src in enumerate(s for s in NEWS_SOURCES if not args.only or s["id"] == args.only):
        if i:
            time.sleep(PAGE_GAP)
        info = {k: src[k] for k in ("id", "name", "lang", "kind", "site")}
        try:
            got = read_source(src, since)
            info["n"] = len(got)
            items += got
            log(f"{src['id']}: {len(got)} items" + (f" (newest {got[0]['d'][:10]}: {got[0]['t']})" if got else ""))
        except Exception as e:   # one site's trouble never stops the others
            info["n"] = 0
            info["error"] = True
            log(f"{src['id']}: {type(e).__name__}: {e}")
        sources.append(info)
    if not items:
        log("Nothing read: news.json is not written (yesterday's stays).")
        return 1
    items.sort(key=lambda i: i["d"], reverse=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": sources, "items": items},
                  f, ensure_ascii=False, separators=(",", ":"))
    log(f"Wrote {len(items)} headlines to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
