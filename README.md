# SubDL for Kodi (`service.subtitles.subdl`)

A Kodi subtitle add-on that searches and downloads subtitles from SubDL through
the public API at `https://api.subdl.com`. Each viewer uses their own free SubDL
API key. Not published anywhere yet: see [SUBMISSION.md](SUBMISSION.md) for what
is left before it goes to Kodi's official repository.

- Kodi 19 (Matrix) and newer, every platform. Python standard library only, no
  add-on dependencies.
- The add-on itself is the folder [`service.subtitles.subdl/`](service.subtitles.subdl).
  That folder is what goes into the `xbmc/repo-scripts` pull request.

## What the viewer gets

- Kodi's subtitle dialog lists SubDL subtitles in the languages chosen in Kodi's
  own subtitle settings, the preferred language first.
- The title is found by IMDb id, then TMDB id, then its name, then the name of the
  file being played. For a TV episode the show's ids come from Kodi's library.
- A subtitle made for the exact release being played gets Kodi's "sync" mark and
  five stars and is listed first. If page one has no such match, page two is read.
- For an episode, season packs are listed too. SubDL hands over just that
  episode's file when it has indexed the pack. Otherwise the add-on downloads the
  pack and picks the episode itself.
- Manual search understands `tt0133093`, `Show S02E05`, `Show 2x05` and
  `Film (1999)`.
- Settings: the API key, a **Check my API key** button (shows the account, plan
  and today's usage), hearing-impaired filter, season packs on or off.

When the key is missing or refused, or a daily limit is reached, a dialog says
what happened and gives the link `https://subdl.com/panel/api`. The dialog shows
once a day per key. After that a short notice with the same link appears.

## What it sends to SubDL

- Search: the viewer's API key, `client=kodi`, the language codes, and one way of
  finding the title (an IMDb or TMDB id, a name, or the playing file's name),
  plus season and episode.
- Download: the subtitle's download path with the viewer's key, so it counts
  against that key.
- User-Agent: `SubDL-Kodi/<add-on version> (service.subtitles.subdl; Kodi/<version>; <platform>)`,
  for example `SubDL-Kodi/1.0.0 (service.subtitles.subdl; Kodi/21.2; Android)`.
  Nothing in it identifies the viewer.

`client=kodi` makes SubDL record the key's integration source as `kodi` on its
first search (only when the key has no source yet). The super console's buyer
mix then shows Kodi buyers. The User-Agent tells add-on versions, Kodi versions and
platforms apart in Cloudflare or request logs.

The add-on never writes the API key, an address, a title, a file name or search
text to Kodi's log. Kodi logs often end up pasted into public forum threads. The log
holds only the kind of request, HTTP status codes and counts.

## Develop

Everything runs with the standard library. On this Mac the system `python3`
is unreliable, so use [uv](https://docs.astral.sh/uv/):

```bash
sh scripts/check.sh
```

That runs the unit tests on Python 3.8 (Kodi 19's Python) and 3.12, builds the
zip, and runs Kodi's `kodi-addon-checker` the way the repo-scripts CI does.
Steps one at a time:

```bash
uv run --no-project --python 3.8 python -m unittest discover -s tests -t .
```

```bash
uv run --no-project --python 3.12 python scripts/build_zip.py
```

```bash
uvx --python 3.12 kodi-addon-checker --branch=matrix --PR service.subtitles.subdl
```

The zip lands in `dist/service.subtitles.subdl-<version>.zip`. It installs with
Kodi's **Add-ons → Install from zip file** and is the same byte for byte on every
build.

### Test in a real Kodi

`e2e/run.sh` runs a real Kodi in Docker on a virtual screen (Xvfb), installs the
add-on, and drives it through Kodi's JSON-RPC like a viewer with a remote. It plays
sample videos and opens Kodi's subtitle dialog. It then searches, picks a row, and
checks that Kodi saved and shows the subtitle. It also checks the dialogs, the
settings, the **Check my API key** button, the User-Agent and the log. Screenshots
land in `e2e/out/`.

```bash
colima start
```

```bash
sh e2e/run.sh
```

```bash
sh e2e/run.sh ubuntu:22.04
```

The first run uses Kodi 21 (Debian trixie), the second Kodi 19 (Ubuntu 22.04).
A mock stands in for SubDL's API (`e2e/mock_subdl.py`), behind a test certificate
authority, so the add-on's real HTTPS and host checks still run. The one exception
is a request with a made-up key to the real `api.subdl.com`, which checks the
refused-key dialog.

### Verified on 2026-10-21

- Unit tests: 124 pass on Python 3.8, 3.11, 3.12, 3.13 and 3.14.
- `kodi-addon-checker --branch=matrix`: no problems. Two warnings: the source
  repository does not exist yet, and Cloudflare answers the checker's request to
  subdl.com with 403. See [SUBMISSION.md](SUBMISSION.md).
- Real Kodi: `e2e/run.sh` passes 20 of 20 checks on Kodi 21.2 and on Kodi 19.4.
- Live API (2026-11-01, a real free key): `SUBDL_LIVE_KEY=... sh e2e/run.sh <image> live`
  passes 8 of 8 checks on Kodi 21.2 and Kodi 19.4. A film and an episode found by
  file name, the first row downloaded (the episode out of a season pack), and Kodi
  plays each subtitle. Two findings:
  - **Persian subtitles in Windows-1256 showed as garbled text** ("ÈÇíÏ ÇÒ" for
    "باید از"): Kodi reads a non-UTF-8 file in its own default code page. Fixed
    the same day: `archive.as_utf8` converts a text subtitle that is not UTF-8
    from its language's legacy code page to UTF-8 with a BOM (Persian also gets
    the Persian yeh and keheh). UTF-8 files and binary formats pass unchanged.
    The live step then checks the saved file is UTF-8 and shows a real line on
    screen: 12 of 12 on Kodi 21.2 and 19.4.
  - The Matrix (sd_id 21581) has Persian music-video subtitles filed under it
    (Pitbull, Lady Gaga…). SubDL data, not the add-on: the API returns them for
    the IMDb id too.

### Layout

| Path | What it does |
|---|---|
| `service.py`, `check_key.py` | Kodi entry points, a few lines each (the checker limits entry-point size) |
| `resources/lib/subdl/api.py` | HTTP client: retries, `Retry-After`, redirects only to `*.subdl.com`, size caps, one error type |
| `resources/lib/subdl/query.py` | Turns what Kodi knows about the video into ordered search attempts |
| `resources/lib/subdl/results.py` | Language filter, season-pack episode picking, release matching, order |
| `resources/lib/subdl/releases.py` | Release-name parsing and scoring |
| `resources/lib/subdl/archive.py` | Safe zip reading and choosing the file(s) to give Kodi |
| `resources/lib/subdl/languages.py` | Kodi ISO 639 codes ↔ SubDL language codes |
| `resources/lib/subdl/addon.py` | The Kodi side: player info, list rows, messages, temp files |
| `tests/` | Unit tests, plus end-to-end tests that run `addon.run()` against fake Kodi modules in `tests/kodi_fakes/` |
| `e2e/` | The real-Kodi test: Dockerfile, setup, mock API and the JSON-RPC driver |
| `scripts/` | `check.sh` (tests, zip, checker) and `build_zip.py` |

### API facts the add-on relies on

Checked against the deployed API code (`api/src/app/api/subtitleSearch.ts`,
`subtitleSearchCore.ts`, `titleResolver.ts`, `getSubtitlesList.ts`,
`subtitle/downloadSubtitle.ts`) on 2026-10-21:

- `GET /api/v1/subtitles` needs `api_key` in the query. A missing or unknown key
  answers HTTP 403 `not_authorized`. The daily quota answers 429 `daily_limit`.
  The per-minute limit (120 a minute) and overload answer 429 `rate_limit` or
  `service_busy` with `Retry-After`.
- "No title found" is HTTP 200 with `status: false` and `can't find movie or tv`.
- When an id is sent, the name and file name are ignored, and two ids that point at
  different titles fail the request. So the add-on sends one id per request.
  `tmdb_id` needs `type`. `year` is not used for matching, so the add-on checks the
  year of a title found by name itself.
- Unknown language codes are dropped, and a request left with none returns every
  language. So only known codes are sent, and results are filtered again.
- `hi=1` and `hi=0` filter the results. They do not just add a flag.
- In the deployed API `full_season=0` means *true* (any non-empty value did).
  It is fixed in `api/` but not deployed. The add-on never sends the parameter.
- Results come newest first, 30 a page at most.
- `unpack=1` lists each season pack's files, with an episode number once SubDL has
  indexed the pack. Indexed files download from `/subtitle/<n_id>/<file_id>`,
  older ones from `/mobile/<n_id>?hash=…`.
- Download URLs come back with `?api_key=` on them. The add-on strips it before
  the URL goes into Kodi's plugin URL, which Kodi logs, and puts it back at
  download time. A free key gets 50 key-counted downloads a day. Over that, the
  answer is 429 `api_download_limit_exceeded`. Cloudflare does not cache downloads
  (`cf-cache-status: BYPASS`), so every download reaches the server and counts.
- `GET /api/v1/me` does not use up a search. The deployed API reports a download
  limit of 0 for free keys, so the key check then shows only the download count.
  A fix coded in `api/` on 2026-10-21 (not yet deployed) reports 50, and the key
  check then shows "Downloads today: X of 50" with no add-on change.
