# warujie-events developer guide

## The parts

| File | What it does |
|---|---|
| [`build_events.py`](../build_events.py) | Reads the shops' event pages and Tonamel's MTG event search, adds the events read by hand from shops' calendar pictures, and writes `events.json` (the next 35 days) |
| [`manual_events.json`](../manual_events.json) | The Magic events read by hand from shops' calendar pictures: posts on X and MINT's schedule pages ("Calendar pictures" below) |
| [`x_reader.py`](../x_reader.py), [`x_accounts.json`](../x_accounts.json) | Reads the calendar pictures of the shops' X accounts listed in `x_accounts.json` automatically, each night, into `x_events.json` (kept in R2): "Calendar pictures on X, read automatically" below |
| [`.github/workflows/events-nightly.yml`](../.github/workflows/events-nightly.yml) | Runs it every night and publishes `events.json` (and Hareruya's fee cache, `hareruya_fees.json`) to R2; a change to `manual_events.json` on `main` updates only those events at once |

The site (`warujie/Warujie`) reads the file at `warujie.jp/data/events.json` (its Worker serves the
R2 bucket `warujie-price-data` to the site's own pages only) in `loadEventCalendar()`, and shows it
on the 大会 tab (the site's `docs/other-pages.md`, "Tournaments tab").

## When it runs

Every day at **18:30 UTC** (3:30 in Japan), and by hand ("Run workflow" in GitHub Actions). It
takes about 10 minutes: about 90 pages, 4 seconds apart, plus a minute to install the headless
Chromium Tonamel needs, and up to about 17 more for Hareruya's event pages, while its fee cache
is filling in (a few minutes a night after that). It runs from `main` only, and does nothing
until the repository has the `CLOUDFLARE_R2_TOKEN` secret (the first step checks, before any shop is
read).

A push to `main` that changes `manual_events.json` also runs it, in under a minute: it downloads the
published `events.json`, replaces its hand-kept events with the file's (`build_events.py --manual-only`) and
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
`/api/`, where its events come from, and its terms forbid scraping), the event pages of mtg-jp.com
(Wizards' Japanese site, e.g. its Store Championship list; checked 2026-10-25: Wizards' terms, 2.2(i),
forbid robots, scripts and spiders, and Wizards gave no permission beyond the Fan Content Policy) and Facebook (its `robots.txt`
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
- **Calendar pictures** (`read_manual()`, the owner's choice of 2026-10-25: by hand first,
  automatic later): many shops post their month's events as one calendar picture, mixing every
  game. Claude reads the picture, lists the Magic events (date, start time, format, name) for the
  owner to check, and they go into `manual_events.json` with the shop's name, prefecture and city
  and a link back. Two kinds (`shop`, checked against `MANUAL_LINKS`):
  - `x`: posts on X, from a picture the owner hands over. x.com is never read (its `robots.txt`
    forbids automated reading; the only permitted route is X's paid API). The link is the post, or
    the shop's X account (where its calendars are) when the post's own link isn't known.
  - `mint`: MINT's monthly TCGイベントスケジュール pages (mint-web.jp, the owner's request; its
    `robots.txt` disallows only `/secure/` and `/cart/`): one page per store, linked from
    `?mode=cate&cbid=2870672`, each with a picture per month (the next month's appears near the
    month's end). The link is the store's page. MINT GAMES MTG (東日本橋) takes every entry
    through Tonamel, so its events come from there.
  An entry without a date, an `HH:MM` time (or none), a prefecture 1–47 or a link of its kind is
  left out, and the log's `manual: left out …` lines say so. **Duplicates merge** (the owner's
  request, 2026-10-25): a hand-kept event at the same store and day as an event read from Tonamel
  (or a shop's page), starting at the same time, or within 30 minutes with a format in common, is
  dropped in favour of the read one, whose page has the details (`tidy()`, `same_event()`;
  `store_key()` matches names across sources, `MINTGAMESMTG店` and `GAMES MTG店` alike). MINT's
  stores that list on Tonamel join MINT's own entry (`TONAMEL_MINT`), and Tonamel's play-room
  bookings (【ルーム予約】貸切プレイルーム) are not events (`TONAMEL_NOT_EVENT`).
- **CARDWINGS** (`read_cardwings()`, the owner's request of 2026-10-26, in place of reading its X
  posts; robots.txt allows the site): its tournament list's own search for Magic (`CARDWINGS_LIST`,
  game 156), both stores (`CARDWINGS_STORES`: 秋葉原駅前店, 八王子駅前店), newest entries first, up to
  `CARDWINGS_MAX_PAGES` pages until a page holds no coming event. Each links to its event page; the
  fee is the 参加料 column (a pack to buy instead is no fee). `shop` `cardwings`.
- **CANTRIP** (the owner's request of 2026-10-26, in place of its X posts): the monthly schedule
  picture on its 八王子 store page, listed under `pages` in `x_accounts.json` and read by
  `x_reader.py` (below) in each nightly run: one page a night, and the picture is read only when it
  has changed; its events replace the previous picture's. `shop` `cantrip`, linking to the page.
- **Calendar pictures on X, read automatically** (`x_reader.py`, the owner's request of
  2026-10-25: automatic, but only for the accounts they choose, and each **once a week, on
  Sunday**, to keep the cost down). In the nightly run, before the shops are read, for every
  account in `x_accounts.json` (`handle`, and the `store`, `p` and `c` its events get) not read
  since the last Sunday in Japan (`X_WEEKDAY`; so on Sunday morning's run, and the first run after
  an account is added or was cut off):
  1. X's API (the owner's pay-per-use developer account, secret `X_BEARER_TOKEN`) gives the
     account's own posts since its last reading's newest (`since_id`), at most `X_MAX_POSTS` (25;
     a busier week loses its oldest posts, and the log says so), no reposts or replies, with the
     description a shop typed for a picture (alt text), which goes to the models too; the first
     time, the latest posts of the last `X_POST_DAYS` days. X bills
     each post read ($0.005 in 2026-10) and each account's first lookup ($0.01).
  2. Each picture goes first to a small model (`SCREEN_MODEL`, a fraction of a cent), which only
     says whether it gives the dates of Magic events.
  3. Those pictures go to `READ_MODEL` (secret `ANTHROPIC_API_KEY`), which lists the Magic events:
     day, start, name, formats, fee (`READ_PROMPT`, a fixed JSON shape, `READ_SCHEMA`), at most
     `X_MAX_READS` (20) pictures a night (an account cut off by it is read on from where it stopped the next night, and its week starts once it is done); `valid_events()` keeps those that hold together (a date from a
     week before the post to four months after it). Each event links to its post.
  The result, with each account's `since_id` and last reading (`read`), is `x_events.json` in R2 (shop `x`, so the site tags
  it X投稿から); events before yesterday drop out, and a newer post's reading of the same event
  replaces the older one, and the same event in two pictures of one post (Japanese and English) is
  kept once. A post whose pictures failed (or met the night's limit) is tried again
  the next night. `build_events.py --x-events` adds them as hand-kept events (the same merging
  with Tonamel), and **an event checked by hand in `manual_events.json` wins** over the same one
  read automatically. Without both secrets the step does nothing (X isn't read, so nothing is paid
  for). **To add a shop:** a line in `x_accounts.json`; to drop one, remove its line (its events go
  when they have passed). A spending limit is set in X's Developer Console and Anthropic's Console.
  The test workflow `x-test.yml` runs the reader once on a `claude/…` work branch and commits its
  log to `x_test/` there (`--all` reads every account whatever its week).
- Formats from words come from `formats_in()` (`FORMAT_WORDS`, the same words as the site's
  `EVENT_FORMAT_WORDS`; full-width letters folded): every format a name or note names, スタン counting
  as スタンダード, プレモダン not as モダン, and a モダンホライゾン draft as limited only. Dates without a year
  get one from `year_for()`.
- **Entry fees** (the owner's request, 2026-10-25: yen only, where the source gives one): `yen_of()`
  takes the first sum in yen (¥1,000, 1000円; 無料 is 0) and ignores a pack or purchase asked for
  instead (1パック購入, 200円以上購入, 3,000円分). Sources: Yellow Submarine's 費用 column, a fee
  column on Amenity Dream's table should it have one, the 参加費 line of a Tonamel description
  (`tonamel_fee()`), `fee` / `fee_to` in `manual_events.json` (read off the picture; `fee_to`
  when the fee depends on the language of the packs, as at prereleases), and Hareruya's event
  pages (the owner's request, 2026-10-25; its `robots.txt` allows them). Hareruya's calendar gives
  no fee, and its 33 stores hold about 10,000 events a month, too many pages to read each night,
  but a store's recurring event (the same name) costs the same each time: `hareruya_fees()` reads
  one page per store and name (its 参加費 row, `hareruya_fee()`), soonest event first, at most
  `HARERUYA_FEE_PAGES` (750, about 50 minutes; raised from 250 on 2026-10-26 so the first nights
  catch up faster) a night and never past `--fee-minutes` (65) from
  the start, and keeps the fees in `hareruya_fees.json` (`--fees`; downloaded from and published
  to R2 beside events.json), re-reading each after `HARERUYA_FEE_DAYS` (30). The first nights
  fill it in (about 1,600 store-and-name pairs, two or three nights); until then some Hareruya events have no
  fee. After that a night reads only new names and the month-old ones (about 100), a few minutes. A hand-kept event that merges
  into a Tonamel event without a fee hands its fee over (`tidy()`).
- A shop that opens, closes or renumbers a store is a one-line change in its table.

## `events.json`

```
{ "updated": "2026-10-24T18:30:00Z",
  "sources": { "hareruya": 10678, "amenity": 16, "yellowsub": 240, "tonamel": 104, "manual": 89 },
  "events": [ { "d": "2026-10-25", "t": "13:00", "p": 13, "c": "千代田区",
                "shop": "hareruya", "store": "秋葉原店", "name": "モダン神挑戦者決定戦トライアル",
                "url": "https://www.hareruyamtg.com/ja/events/620342/detail", "f": ["modern"], "fee": 1000 } ] }
```

One entry per event from today (Japan time) to 35 days ahead, sorted by day and start time. `t` is
"" when the shop gives no time; `p` is the prefecture's JIS number (1–47), `c` the city or Tokyo
ward; `shop` is `hareruya`, `amenity`, `yellowsub`, `tonamel`, `mint` or `x` (the site's
`EVENT_SHOPS`); `store` is the store (for Tonamel, the organiser's name); `url` is the event's own
page (Hareruya, Tonamel, MINT's Tonamel events), the post on X (`x`) or the store's schedule (the
others); `sources` counts each reader's events (`manual`: the calendar pictures); `f` lists the formats (`standard`,
`pioneer`, `modern`, `legacy`, `vintage`, `pauper`, `commander`, `premodern`, `limited`), left out
when none is known; `fee` is the entry fee in yen (0 when free) and `fee_to` the higher fee when
there are two (Japanese or English packs), both left out when unknown. About 11,000 events, 2.6 MB (much smaller compressed in transit).

## Running it on your computer

```
python3 build_events.py --out out/events.json            # every shop, about 10 minutes
python3 build_events.py --out out/events.json --only amenity
python3 build_events.py --out out/events.json --only hareruya --fees out/hareruya_fees.json   # with fees
python3 build_events.py --out out/events.json --only manual   # manual_events.json alone
python3 build_events.py --out out/events.json --manual-only published.json   # its hand-kept events replaced
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
| An event from a calendar picture is missing | Is its day still ahead, and does the entry in `manual_events.json` hold together? The log's `manual: left out …` lines say which entries were dropped; an event the store also lists on Tonamel shows Tonamel's entry instead |
| MINT's events stop after a month | MINT posts each month's picture near the month's end; read the new pictures into `manual_events.json` |
| A Tonamel event is missing | Online and cancelled events are left out, and so are events whose address names no prefecture `place_of()` knows; the log's `tonamel: stopped at …` line says why the list ended |
