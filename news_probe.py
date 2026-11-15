# THROWAWAY: tries candidate feeds for the news page; prints whether robots.txt allows each, how many items
# it has, how many are Magic, and the newest Magic headlines. Removed before publishing.
import time, urllib.request
from build_news import allowed, parse_feed, clean, when, MUST, USER_AGENT
CANDIDATES = [
  "https://www.4gamer.net/rss/index.xml", "https://www.4gamer.net/rss/rss.xml",
  "https://www.famitsu.com/rss/famitsu_news.rdf", "https://www.famitsu.com/rss/category/news.rdf",
  "https://gamebiz.jp/feed.rss", "https://gamebiz.jp/rss", "https://gamebiz.jp/feed",
  "https://dengekionline.com/rss/news.rss", "https://dengekionline.com/feed",
  "https://www.gamespark.jp/rss/index.rdf", "https://www.inside-games.jp/rss/index.rdf",
  "https://kyodonewsprwire.jp/rss/all.rdf", "https://prtimes.jp/index.rdf",
  "https://news.google.com/rss/search?q=%E3%83%9E%E3%82%B8%E3%83%83%E3%82%AF%EF%BC%9A%E3%82%B6%E3%83%BB%E3%82%AE%E3%83%A3%E3%82%B6%E3%83%AA%E3%83%B3%E3%82%B0&hl=ja&gl=JP&ceid=JP:ja",
  "https://note.com/hashtag/MTG/rss", "https://note.com/hashtag/mtg?f=new&rss",
  "https://www.youtube.com/@mtgjp", "https://www.youtube.com/@MagicTheGathering", "https://www.youtube.com/@playmtg",
  "https://mtg-arena-japan.com/feed", "https://cardrush.media/mtg/feed", "https://www.cardrush.media/feed",
  "https://www.mtgsalvation.com/articles.rss", "https://www.wargamer.com/mainrss.xml",
  "https://commandersherald.com/feed/", "https://www.hipstersofthecoast.com/feed/", "https://aetherhub.com/Feed/Atom",
  "https://www.tcgplayer.com/content/magic-the-gathering/rss", "https://infinite.tcgplayer.com/magic-the-gathering/rss",
]
for u in CANDIDATES:
    time.sleep(3)
    try:
        if not allowed(u):
            print(f"{u}\n   robots.txt disallows"); continue
        req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(5_000_000)
        if "youtube.com/@" in u:
            import re
            m = re.search(rb'"(?:externalId|channelId)":"(UC[\w-]{22})"', data) or re.search(rb'channel_id=(UC[\w-]{22})', data)
            print(f"{u}\n   channel {m and m.group(1).decode()}"); continue
        items = parse_feed(data)
        mtg = [(when(d) or "")[:10] + " " + clean(t) for t, l, d in items if MUST["MTG"].search(clean(t) or "")]
        print(f"{u}\n   {len(items)} items, {len(mtg)} Magic; newest item {max((when(d) or '' for _,_,d in items), default='')[:10]}")
        for m in sorted(mtg, reverse=True)[:5]: print("     " + m)
    except Exception as e:
        print(f"{u}\n   {type(e).__name__}: {e}")
