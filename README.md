# warujie-events

The local Magic tournaments behind [warujie.jp](https://warujie.jp/)'s 大会 calendar.

- `build_events.py` reads Hareruya's, Amenity Dream's and Yellow Submarine's own event pages once a
  night (only what their robots.txt allows, one page every 4 seconds, with a User-Agent naming
  warujie.jp) and writes `events.json`: the next 35 days of events, each linking back to the shop's
  own page.
- `.github/workflows/events-nightly.yml` runs it at 3:30 in Japan and publishes `events.json` to the
  private Cloudflare R2 bucket the site reads through its Worker. Nothing is committed.

Shop owners: if you would like your store's events left out, write to the address in the reader's
User-Agent and we will remove them at once.

**Developers:** start with [`docs/README.md`](docs/README.md).
