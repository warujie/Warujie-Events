# warujie-events developer guide

## The parts

| File | What it does |
|---|---|
| [`build_events.py`](../build_events.py) | Reads the shops' event pages and Tonamel's MTG event search, adds the events read by hand from shops' X posts, and writes `events.json` (the next 35 days) |
| [`manual_events.json`](../manual_events.json) | The Magic events read by hand from shops' calendar pictures on X ("X posts" below) |
| [`.github/workflows/events-nightly.yml`](../.github/workflows/events-nightly.yml) | Runs it every night and publishes `events.json` alone to R2; a change to `manual_events.json` on `main` updates only those events at once |

The site (`warujie/Warujie`) reads the file at `warujie.jp/data/events.json` (its Worker serves the
R2 bucket `warujie-price-data` to the site's own pages only) in `loadEventCalendar()`, and shows it
on the 大会 tab (the site's `docs/other-pages.md`, "Tournaments tab").

## When it runs

Every day at **18:30 UTC** (3:30 in Japan), and by hand ("Run workflow" in GitHub Actions). It
takes about 10 minutes: about 90 pages, 4 seconds apart, plus a minute to install the headless
Chromium Tonamel needs. It runs from `main` only, and does nothing
until the repository has the `CLOUDFLARE_R2_TOKEN` secret (the first step checks, before any shop is
read).

A push to `main` that changes `manual_events.json` also runs it, in under a minute: it downloads the
published `events.json`, replaces its X events with the file's (`build_events.py --x-only`) and
publishes that. No shop is read again, so the shops are still read once a night.

## The secret

`CLOUDFLARE_R2_TOKEN` (Settings → Secrets and variables → Actions → New repository secret): a
Cloudflare API token that may only edit R2, made the same way as warujie-prices' secret of the same
name (Cloudflare → My Profile → API Tokens → Create Token → Custom token → Account · Workers R2
Storage · Edit). The workflow turns it into the S3-style key pair `aws s3 cp` needs. Never write it
anywhere else.

## How `build_events.py` reads each shop

We read only what each shop's `robots.txt` allows, one page at a time, `PAGE_GAP` (4) seconds apart
(`fetch()`), with a User-Agent naming warujie.jp and our contact address. **If a shop asks us to
stop, take it out at once.** Never added: Wizards' Store & Event Locator (its `robots.txt` disallows
`/api/`, where its events come from, and its terms forbid scraping) and Facebook (its `robots.txt`
forbids automated collection without written permission, and pages need a login).

- **Hareruya** (`read_hareruya()`): each store's month calendar, `/ja/events/?shop=<n>&date=<YYYYMM>`,
  this month and next (66 pages). `parse_hareruya()` takes each day's events: time, name, the
  event's own page and its format icons (`HARERUYA_ICONS`; Dr/Se → limited). Hareruya's standing
  daily league (names with `[毎日開催]`) is left out (`keep()`). The stores, their prefecture and city
  are kept by hand in `HARERUYA` (calendar shop numbers, not the search's venue numbers).
- **Amenity Dream** (`read_amenity()`): every store's MTG list, `/matches/?type=2&shop=&date=`
  (type 2 = ＭＴＧ), shows only the coming week, so the reader then reads one page per day for each
  day its 開催日 drop-down offers (`amenity_dates()`, about a month: some 32 pages), with further
  pages if a day's list ever has page links (`amenity_pages()`, at most `AMENITY_MAX_PAGES`).
  Amenity's events have no page of their own: each links to its store's list for that day
  (`?type=2&shop=<n>&date=<day>`). Its server sends an out-of-date certificate chain, so `amenity_context()` fetches
  the missing intermediate from the certificate's own AIA link and verifies normally. Stores:
  `AMENITY`.
- **Yellow Submarine** (`read_yellowsub()`): each store's schedule, `/tmt_list/<store>/` (Shift_JIS),
  rows whose game is マジック. Its names are generic (フライデーナイトマジック), so the format from the
  notes column is added to the name. The store's name comes from the page title; prefecture and city
  from `YELLOWSUB`.
- **Tonamel** (`read_tonamel()`, the owner's request of 2026-10-25): KAYAC's tournament site, where
  many smaller stores list their MTG events (Absolute Zero in Okinawa, MINT GAMES, Hobby Station…).
  Its `robots.txt` disallows only `/organize/` and `/settings/`. Its event search
  (`TONAMEL_LIST`, MTG in Japan) is built in the browser, and its API (`TONAMEL_API`) answers only
  the page itself, so the reader opens the page in a headless Chromium (Playwright) as a visitor
  would, without pictures, fonts, ads or other sites, keeps the lists the page loads
  (`getPublicCompetitions`, 32 events each) and scrolls for the next one `PAGE_GAP` seconds apart,
  until the list ends, passes 40 days or `TONAMEL_MAX_PAGES` lists (the whole list was 4 lists on
  2026-10-25). `parse_tonamel()` keeps offline events that aren't cancelled; leaves out events by
  the shops read directly (`TONAMEL_SKIP`); takes the prefecture and city from the venue's address
  (`place_of()`: the prefecture's name, else the postcode's first two digits in `POSTAL_PREF`, else
  a big city in `CITY_PREF`); the store is the organiser's name, the format comes from the title or
  the description's 【フォーマット】 line, and each event links to its own Tonamel page.
- **X posts** (`read_manual()`, the owner's choice of 2026-10-25): many shops post their month's
  events as a calendar picture on X, mixing every game. x.com is never read (its `robots.txt`
  forbids automated reading; the only permitted route is X's paid API). Instead the owner hands
  Claude the picture and the post's link; Claude lists the Magic events (date, start time, format,
  name), the owner checks them, and they go into `manual_events.json` with the post's link, the
  shop's name (spelled as on Tonamel when the shop lists there too), prefecture and city. An entry
  without a date, an `HH:MM` time (or none), a prefecture 1–47 or a link to the X post (or, when
  the post's own link isn't known, to the shop's X account, where its calendars are; `X_POST`) is
  left out, and the log says so. An X event at the same store, day and start time as
  one of its Tonamel events is dropped in favour of Tonamel's (`tidy()`, `store_key()`), whose page
  has the details. The plan for reading the posts automatically later (X's API with a spending cap,
  Claude reading the pictures) is in the project files, `x-twitter/plan.md`.
- Formats from words come from `formats_in()` (`FORMAT_WORDS`, the same words as the site's
  `EVENT_FORMAT_WORDS`; full-width letters folded): every format a name or note names, スタン counting
  as スタンダード, プレモダン not as モダン, and a モダンホライゾン draft as limited only. Dates without a year
  get one from `year_for()`.
- A shop that opens, closes or renumbers a store is a one-line change in its table.

## `events.json`

```
{ "updated": "2026-10-24T18:30:00Z",
  "sources": { "hareruya": 10678, "amenity": 16, "yellowsub": 240, "tonamel": 104, "x": 12 },
  "events": [ { "d": "2026-10-25", "t": "13:00", "p": 13, "c": "千代田区",
                "shop": "hareruya", "store": "秋葉原店", "name": "モダン神挑戦者決定戦トライアル",
                "url": "https://www.hareruyamtg.com/ja/events/620342/detail", "f": ["modern"] } ] }
```

One entry per event from today (Japan time) to 35 days ahead, sorted by day and start time. `t` is
"" when the shop gives no time; `p` is the prefecture's JIS number (1–47), `c` the city or Tokyo
ward; `shop` is `hareruya`, `amenity`, `yellowsub`, `tonamel` or `x` (the site's `EVENT_SHOPS`);
`store` is the store (for Tonamel, the organiser's name); `url` is the event's own page (Hareruya,
Tonamel), the post on X (`x`) or the store's schedule (the others); `f` lists the formats (`standard`,
`pioneer`, `modern`, `legacy`, `vintage`, `pauper`, `commander`, `premodern`, `limited`), left out
when none is known. About 11,000 events, 2.6 MB (much smaller compressed in transit).

## Running it on your computer

```
python3 build_events.py --out out/events.json            # every shop, about 10 minutes
python3 build_events.py --out out/events.json --only amenity
python3 build_events.py --out out/events.json --only x   # manual_events.json alone
python3 build_events.py --out out/events.json --x-only published.json   # its X events replaced
```

It needs Python 3.10+, for Amenity Dream `pip install cryptography`, and for Tonamel
`pip install playwright` then `python3 -m playwright install chromium` (without them Tonamel is
skipped, and the log says so).

## Troubleshooting

| Symptom on warujie.jp | Look at |
|---|---|
| The 大会 tab says the list is coming | `events.json` was never published: is the secret set, and did the last run go green? |
| One shop's events are missing | The run log says how many events each shop gave (`hareruya: 0 events` means its page changed; fix its parser) |
| Events are a day old | Normal: the file is read once a night |
| A new store is missing | Add it to `HARERUYA`, `AMENITY` or `YELLOWSUB`; a store that lists its events on Tonamel appears by itself |
| An X event is missing | Is its day still ahead, and does the entry in `manual_events.json` hold together? The log's `x: left out …` lines say which entries were dropped; an event the store also lists on Tonamel shows Tonamel's entry instead |
| A Tonamel event is missing | Online and cancelled events are left out, and so are events whose address names no prefecture `place_of()` knows; the log's `tonamel: stopped at …` line says why the list ended |
