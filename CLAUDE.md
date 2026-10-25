# warujie-events — working notes

The tournament calendar data for warujie.jp's 大会 tab. The site is in `warujie/Warujie` (private;
its `CLAUDE.md` has the owner's full rules), the price data in `warujie/warujie-prices`. This
repository was split off from warujie-prices on 2026-10-25 (the owner's request) so the event
reader can never touch the price history, has its own switch, and can be turned off alone.
It is public (unlimited Actions minutes on the free plan), so it holds no private details.

Start with [`docs/README.md`](docs/README.md).

## Rules (the owner's, keep them)

1. **`main` is live.** The nightly workflow runs from `main` and publishes to R2, which warujie.jp
   reads at once. Work on a branch and merge to `main` only when the owner says "publish".
2. **Which sites, and how** (the owner's decision, 2026-10-24): Hareruya, Amenity Dream and Yellow
   Submarine, read without asking them first. Only pages their robots.txt allows; one page at a
   time, `PAGE_GAP` (4) seconds apart; once a night; a User-Agent naming warujie.jp and the contact
   address; every event links back to the shop's page. **If a shop asks us to stop, take it out at
   once.** Never read Wizards' Store & Event Locator (robots.txt disallows its `/api/`; its terms
   forbid scraping; the site depends on Wizards' Fan Content Policy) or Facebook (robots.txt forbids
   automated collection; pages need a login). Any new source needs the owner's yes first.
   **Tonamel** (the owner's request, 2026-10-25): its public MTG event search for Japan, opened in a
   headless browser once a night under the same rules (its robots.txt disallows only `/organize/`
   and `/settings/`); every event links to its Tonamel page. **X (Twitter)** is not read: x.com's
   robots.txt forbids it, and the only permitted route is the paid X API (the owner chose "not now"
   for X, 2026-10-18). **Shops' calendar pictures on X** (the owner's choice, 2026-10-25: by hand
   first, automatic later): the owner hands over the picture and the post's link, Claude lists the
   Magic events, the owner checks them, and they go into `manual_events.json`, each linking to its post.
   Reading X automatically needs X's paid API and the owner's own keys (never pasted in chat).
3. **No secrets in the repo or in chat.** The R2 token is the GitHub secret `CLOUDFLARE_R2_TOKEN`;
   never print it, and never ask the owner to paste a token.
4. **Never publish an empty file.** `build_events.py` exits without writing when every source fails,
   so yesterday's file stays; keep it that way.

## Documentation (keep it true)

Every commit that changes the reader's behaviour, a source, the published file or the schedule also
updates `docs/README.md` in the same commit. A change to the file's shape also needs the site's
reader (`loadEventCalendar()` in `index.html`) and the site's `docs/data.md` changed. Name code by
function or constant, never by line number.
