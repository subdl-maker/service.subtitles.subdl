# Submitting `service.subtitles.subdl` to Kodi's official repository

**Status:** ready to submit, **not submitted**. The single-commit branch is prepared locally in `~/dev/subdl/repo-scripts-kodi` (branch `service.subtitles.subdl`) and the PR text is in `dist/PR_BODY.md`. No pull request, issue or forum post
has been made. The add-on goes to [`xbmc/repo-scripts`](https://github.com/xbmc/repo-scripts),
branch **`matrix`**.

## Checklist

- [x] Decide the version: **1.0.0** (decided 2026-11-01) (§1.1)
- [x] Licence: **keep MIT** (decided 2026-11-01) (§1.2)
- [x] Public source repository: **`subdl-maker/service.subtitles.subdl`** (2026-11-01; `<source>` changed from `subdlcom`, which `subdl-maker` cannot create repos in) (§1.3)
- [ ] Test once in Kodi with a real free key (§2)
- [x] `sh scripts/check.sh`: tests green, zip built, checker "no problems" (2026-11-01)
- [ ] Fork `xbmc/repo-scripts`, one commit `[service.subtitles.subdl] 1.0.0` on branch `matrix`, open the PR with the text in §3
- [ ] Answer the automated (Greptile) and human review on the PR (§4)
- [ ] Optional: a Kodi forum thread for support, then add `<forum>` to `addon.xml` (§1.6)

## 1. Decide before submitting

1. **Add-on id and version.** An unofficial add-on by "Duy"
   ([duytim/subdl_kodi](https://github.com/duytim/subdl_kodi), last updated 2026-04-25)
   already uses the id `service.subtitles.subdl`, at version **2.0.1**. It is not in
   Kodi's repository (`kodi-addon-checker` reports "This is a new addon"), so the
   repository will accept the id. But on a viewer's device Kodi treats both as one
   add-on:
   - **Keep 1.0.0 (as built):** people who installed Duy's zip keep his add-on.
     Kodi never offers them the official one as an update.
   - **Bump to 3.0.0:** Kodi's automatic updates replace Duy's add-on with this one
     for those people. They then have to enter their own key, because his setting is
     called `APIKey` and this one `api_key`.

   Either way, it is polite to tell Duy first.
2. **Licence.** Built as **MIT** (`LICENSE.txt`, `<license>` in `addon.xml`). Kodi's
   [add-on rules](https://kodi.wiki/view/Add-on_rules) recommend GPL v2 or later,
   but accept others: SubtitleDB, an MIT add-on, was merged to `matrix` on
   2026-09-25. To change it, edit both places.
3. **Public source repository.** `<source>` in `addon.xml` points at
   `https://github.com/subdl-maker/service.subtitles.subdl` (created 2026-11-01).
   It is a public repository holding this folder (`kodi-addon/`), owned by the
   `subdl-maker` account that opens the pull request. The add-on folder alone is
   what goes into the pull request.
4. **Checker warning for `https://subdl.com`.** Cloudflare answers the checker's
   request (`python-requests`, `HEAD /`) with 403. It is a warning, not a problem,
   so CI still passes. Either explain it in the pull request (draft below does), or
   let that request through Cloudflare (owner-only setting).
5. **The "no monetization" rule.** Kodi's rules say: *"Monetization of add-ons (for
   instance advertising or paid subscriptions) will not be allowed."* This add-on
   shows no adverts and sells nothing. When a daily limit is reached it says when
   the limit resets and where the account page is ("To raise it, visit
   https://subdl.com/panel/api"). That is milder than the accepted OpenSubtitles.com
   add-on, which says "Get a VIP subscription or try again tomorrow". Be ready to
   say so if a reviewer asks. Do not add price or plan names to the add-on's text.
6. **Support channel (optional).** Reviewers and users look for a place to report
   problems: a thread in the Kodi forum's subtitle add-ons section (`<forum>`) or
   an address (`<email>`). Neither exists yet.
7. **Maintainer.** The rules say the submitter is the maintainer. The GitHub account
   that opens the pull request will be asked to answer the review.

## 2. Test once with a real free key

What is already verified:

- 124 unit tests on Python 3.8 (Kodi 19), 3.11, 3.12, 3.13 and 3.14.
- `e2e/run.sh` runs a real Kodi **19.4** and **21.2**. Each run installs the add-on,
  plays sample videos, searches and downloads through Kodi's own subtitle dialog,
  and checks the result: 20 of 20 checks pass on both. For these runs a mock stood
  in for SubDL's API, except one request with a made-up key to the real
  `api.subdl.com`, which checked the refused-key path over real HTTPS.

What is **not** verified: a search and download against the live API with a real
key. This session had no key and could not create an account. Before submitting:

1. In Kodi: **Settings → System → Add-ons → Unknown sources** on.
2. **Add-ons → Install from zip file** → `dist/service.subtitles.subdl-1.0.0.zip`
   (build it with `sh scripts/check.sh`).
3. Add-on settings → paste a free key from https://subdl.com/panel/api →
   **Check my API key**.
4. Play a library film, a library episode and a file that is not in the library.
   Open the subtitle dialog, download one subtitle for each, and check the row order
   and that the subtitle shows. For the episode, also try a "Season pack" row.
5. In the SubDL panel, the key should now show **Kodi** as its integration.

## 3. Make the pull request

The repository wants one add-on per pull request and **one commit** named
`[service.subtitles.subdl] 1.0.0`, from a branch of your fork (not `master`).
Use the built zip, so no caches or hidden files slip in:

```bash
gh repo fork xbmc/repo-scripts --clone=false
git clone --branch matrix --depth 1 https://github.com/<your-account>/repo-scripts.git
cd repo-scripts
git checkout -b service.subtitles.subdl
unzip /Users/ben/dev/subdl/subdl-v3/kodi-addon/dist/service.subtitles.subdl-1.0.0.zip -d .
git add service.subtitles.subdl
git commit -m "[service.subtitles.subdl] 1.0.0"
git push origin service.subtitles.subdl
gh pr create --repo xbmc/repo-scripts --base matrix --title "[service.subtitles.subdl] 1.0.0"
```

`matrix` is the right branch: Kodi's `targets.cfg` publishes `matrix` add-ons to
Kodi 19, 20, 21 and 22. `xbmc.python` 3.0.0 is correct for it. The checker suggests
3.0.1 only when targeting `nexus` or `omega`. If reviewers ask for a newer branch
instead, change that line.

Pull-request text to paste (edit the tested versions if you test more):

```markdown
### Description
SubDL, a new subtitle service for SubDL (https://subdl.com). It finds the title by its IMDb or TMDB id, by name, or by the name of the file being played; for an episode it takes that episode's file out of a season pack; the subtitle made for the playing release is listed first. Each viewer uses their own free SubDL API key, and the add-on says where to get one when it is missing or refused.

- Python 3 standard library only, `xbmc.python` 3.0.0, MIT licence, no other add-ons needed.
- Logs at debug level only, and never logs the key, an address, a title or a file name.
- No analytics inside the add-on: SubDL counts use on its server from the User-Agent.
- Tested on Kodi 19.4 and 21.2 by an automated run that installs the add-on, plays sample files and searches and downloads through Kodi's subtitle dialog; unit tests on Python 3.8 to 3.14.
- `kodi-addon-checker --branch matrix` reports no problems. Its warning about https://subdl.com is Cloudflare's bot protection answering the checker's HEAD request with 403; the site works in a browser.

Source: https://github.com/subdl-maker/service.subtitles.subdl

### Checklist:
- [x] My code follows the [add-on rules](http://kodi.wiki/view/Add-on_rules) and [piracy stance](http://kodi.wiki/view/Official:Forum_rules#Piracy_Policy) of this project.
- [x] I have read the [CONTRIBUTING](https://github.com/xbmc/repo-scripts/blob/master/CONTRIBUTING.md) document
- [x] Each add-on submission should be a single commit with using the following style: [script.foo.bar] 1.0.0
```

## 4. What the review checks, and where the add-on stands

| Check | Status |
|---|---|
| `kodi-addon-checker --branch=matrix --PR` (CI) | No problems; 2 warnings (items 3 and 4 above) |
| Python 3, `LICENSE.txt`, en_GB metadata, valid XML with declarations | Done |
| `icon.png` 512×512 without transparency, `fanart.jpg` 1920×1080 | Done (fanart drawn for this add-on from the SubDL mark) |
| No binaries, compiled or obfuscated files; Unix line endings; no BOM; nothing executable | Done (the zip is built from source only) |
| Every user-facing string in `strings.po` | Done |
| `xbmc.log` at debug level only | Done |
| Files only under the add-on's profile folder | Done (`addon_data/service.subtitles.subdl/temp`) |
| No analytics inside the add-on; use counted server-side from the User-Agent | Done |
| Entry point kept small (checker counts its lines) | `service.py` and `check_key.py` are a few lines each |
| Automated review (Greptile) findings on recent subtitle add-ons: failed downloads ending in a traceback; redirects checked after they were followed; `Retry-After` dates ignored; playback details in the log; downloads deleting each other's files; downloading without the viewer asking | All handled and tested: every error ends in a message and Kodi always gets its answer; redirects away from `*.subdl.com` are refused before they are sent; `Retry-After` seconds and dates are read; logs carry only request kinds, status codes and counts; each download gets its own folder; nothing downloads unless the viewer picks a row (or Kodi's own "download first subtitle" setting is on) |

## 5. After it is merged

- Kodi's repository serves the add-on to Kodi 19 and newer. Search for "SubDL" under
  **Add-ons → Install from repository → Subtitles**.
- Updates: raise `version` in `addon.xml`, add the change to `changelog.txt` and
  `<news>`, rebuild, and open a new single-commit pull request
  (`[service.subtitles.subdl] 1.0.1`). The rules ask for stable updates, at most
  about once or twice a month.
- Measuring: keys whose integration source is `kodi` (set by `client=kodi` on the
  first search) and requests with a User-Agent starting `SubDL-Kodi/`.
