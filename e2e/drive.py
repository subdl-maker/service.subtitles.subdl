"""Drive a real Kodi (under Xvfb) through the SubDL add-on, check what happens, take screenshots.

Runs as root inside the container that e2e/run.sh starts, after setup.sh. Kodi runs as
user "viewer" and is controlled through its JSON-RPC web interface. Kodi keeps add-on
settings in memory, so each phase that needs another API key restarts Kodi.

Phases:
  missing_key  no key: the dialog with the panel link, then a short notice
  refused_key  a made-up key against the REAL api.subdl.com: the refused-key dialog,
               whose "Open settings" button must open the add-on's settings
  mock         api.subdl.com and dl.subdl.com answered by mock_subdl.py: film search,
               download and the subtitle loaded in the player; an episode taken out of
               a season pack; the daily-limit dialog; the "Check my API key" button
  live         the REAL api.subdl.com with a real key from $SUBDL_LIVE_KEY (run only when
               asked for by name): film and episode searched by file name, a subtitle
               downloaded and loaded for each. Uses two of the key's daily downloads.

Writes screenshots and report.json to /harness/out and exits 1 if a check failed.
"""

import base64
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

RPC = "http://127.0.0.1:8080/jsonrpc"
AUTH = "Basic " + base64.b64encode(b"kodi:kodi").decode()
OUT = "/harness/out"
KODI = "/home/viewer/.kodi"
MEDIA = "/home/viewer/media"
ADDON = "service.subtitles.subdl"
KEY = "TestKey-not-real-0123456789"
MOVIE = MEDIA + "/The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv"
EPISODE = MEDIA + "/Breaking.Bad.S01E05.720p.BluRay.x264-DEMAND.mkv"
HOME, YESNO, OK, CONTEXT_MENU, ADDON_SETTINGS, SUBTITLES = 10000, 10100, 12002, 10106, 10140, 10153

report = {"checks": {}, "notes": {}}
mock = None


# ---- plumbing -------------------------------------------------------------------


def check(name, passed, detail=None):
    report["checks"][name] = {"passed": bool(passed), "detail": detail}
    print("%s %s %s" % ("PASS" if passed else "FAIL", name, "" if detail is None else json.dumps(detail)[:300]),
          flush=True)


def note(name, value):
    report["notes"][name] = value


def rpc(method, params=None, timeout=30):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    request = urllib.request.Request(RPC, body, {"Content-Type": "application/json", "Authorization": AUTH})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return json.loads(answer.read())


def shot(name):
    subprocess.run(["import", "-display", ":99", "-window", "root", "%s/%s.png" % (OUT, name)], check=False)


def window():
    """(window label, window id, focused control label)."""
    try:
        props = rpc("GUI.GetProperties", {"properties": ["currentwindow", "currentcontrol"]})["result"]
        return props["currentwindow"].get("label", ""), props["currentwindow"].get("id"), \
            props["currentcontrol"].get("label", "")
    except Exception as error:  # noqa: BLE001
        return "error: %s" % error, None, ""


def wait_for(predicate, seconds, step=0.5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def wait_window(ids, seconds=30):
    return wait_for(lambda: window() if window()[1] in ids else None, seconds)


def focus(label_pattern, direction, tries=8):
    """Move focus in one direction until the focused control's label matches."""
    for _ in range(tries):
        if re.match(label_pattern, window()[2] or ""):
            return True
        rpc("Input.ExecuteAction", {"action": direction})
        time.sleep(0.6)
    return bool(re.match(label_pattern, window()[2] or ""))


def click(x, y):
    subprocess.run(["su", "viewer", "-s", "/bin/sh", "-c", "DISPLAY=:99 xdotool mousemove %d %d click 1" % (x, y)])


def set_key(key):
    folder = KODI + "/userdata/addon_data/" + ADDON
    os.makedirs(folder, exist_ok=True)
    with open(folder + "/settings.xml", "w") as handle:
        handle.write('<settings version="2">\n    <setting id="api_key">%s</setting>\n</settings>\n' % key)
    subprocess.run(["chown", "-R", "viewer:viewer", KODI + "/userdata/addon_data"], check=True)


def start_kodi():
    subprocess.Popen(["su", "viewer", "-s", "/bin/sh", "-c",
                      "export DISPLAY=:99 HOME=/home/viewer; exec kodi --standalone >>/tmp/kodi-out.log 2>&1"])

    def ping():
        try:
            return rpc("JSONRPC.Ping", timeout=3).get("result") == "pong"
        except Exception:  # noqa: BLE001
            return False

    if not wait_for(ping, 120, 1):
        raise SystemExit("Kodi's JSON-RPC never answered; see /tmp/kodi-out.log")
    time.sleep(4)
    rpc("Addons.SetAddonEnabled", {"addonid": ADDON, "enabled": True})
    # Kodi asks at start-up whether to enable a hand-copied add-on; that is done above.
    for _ in range(5):
        if window()[1] == HOME:
            break
        rpc("Input.Back")
        time.sleep(1)
    return rpc("Addons.GetAddonDetails", {"addonid": ADDON, "properties": ["enabled", "version"]})["result"]["addon"]


def stop_kodi():
    try:
        rpc("Application.Quit", timeout=5)
    except Exception:  # noqa: BLE001
        pass
    if not wait_for(lambda: subprocess.run(["pgrep", "-x", "kodi.bin"], capture_output=True).returncode, 30, 1):
        subprocess.run(["pkill", "-9", "-x", "kodi.bin"], check=False)
        time.sleep(2)


def play(path):
    rpc("Player.Open", {"item": {"file": path}})
    wait_for(lambda: rpc("Player.GetActivePlayers")["result"], 30)
    time.sleep(2)


def stop_playing():
    for player in rpc("Player.GetActivePlayers")["result"]:
        rpc("Player.Stop", {"playerid": player["playerid"]})
    time.sleep(2)


def subtitle_rows():
    """The rows of Kodi's subtitle dialog (list control 120) as Kodi shows them."""
    count = int(rpc("XBMC.GetInfoLabels", {"labels": ["Container(120).NumItems"]})["result"]
                ["Container(120).NumItems"] or 0)
    parts = ("Label", "Label2", "Property(sync)", "Property(hearing_imp)", "Thumb", "ActualIcon")
    names = ["Container(120).ListItemAbsolute(%d).%s" % (index, part) for index in range(count) for part in parts]
    found = rpc("XBMC.GetInfoLabels", {"labels": names})["result"] if names else {}
    return [{part: found.get("Container(120).ListItemAbsolute(%d).%s" % (index, part)) for part in parts}
            for index in range(count)]


def run_plugin(query):
    """Run the add-on through Kodi the way the subtitle dialog does, in a thread: its
    dialogs block the call until they are answered."""
    result = {}

    def call():
        try:
            result["answer"] = rpc("Files.GetDirectory", {"directory": "plugin://%s/?%s" % (ADDON, query),
                                                          "media": "files"}, timeout=120)
        except Exception as error:  # noqa: BLE001
            result["error"] = str(error)

    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    return thread, result


def point_subdl_at_mock(on):
    with open("/etc/hosts") as handle:
        lines = [line for line in handle.read().splitlines() if "subdl.com" not in line]
    if on:
        lines.append("127.0.0.1 api.subdl.com dl.subdl.com")
    with open("/etc/hosts", "w") as handle:
        handle.write("\n".join(lines) + "\n")


def search_dialog_rows(path):
    play(path)
    rpc("GUI.ActivateWindow", {"window": "subtitlesearch"})
    return wait_for(subtitle_rows, 30) or []


def take_first_row():
    focus(r"^(Persian|English)$", "right")
    rpc("Input.ExecuteAction", {"action": "firstpage"})
    time.sleep(0.5)
    rpc("Input.Select")


# ---- phases ---------------------------------------------------------------------


def phase_missing_key():
    point_subdl_at_mock(False)
    set_key("")
    addon = start_kodi()
    check("addon installed and enabled", addon.get("enabled") and addon.get("version"), addon)
    play(MOVIE)
    rpc("GUI.ActivateWindow", {"window": "subtitlesearch"})
    dialog = wait_window((YESNO,))
    time.sleep(1)
    shot("01-missing-key-dialog")
    check("missing key: dialog with the panel link", dialog, dialog)
    rpc("Input.Back")
    time.sleep(1)
    rpc("Input.Back")
    time.sleep(1)
    rpc("GUI.ActivateWindow", {"window": "subtitlesearch"})
    time.sleep(1.5)
    shot("02-missing-key-second-time-notice")
    check("missing key: no second dialog the same day", window()[1] == SUBTITLES, window())
    rpc("Input.Back")
    stop_playing()
    stop_kodi()


def phase_refused_key():
    point_subdl_at_mock(False)
    set_key("kodi-e2e-not-a-real-key")
    start_kodi()
    thread, _ = run_plugin("action=manualsearch&searchstring=The%20Matrix&languages=English")
    dialog = wait_window((YESNO,))
    time.sleep(1)
    shot("03-refused-key-dialog-real-api")
    check("refused key (real api.subdl.com over real TLS): dialog", dialog, dialog)
    focus(r"^Open settings$", "left")
    rpc("Input.Select")
    opened = wait_window((ADDON_SETTINGS,), 15)
    time.sleep(1)
    shot("04-open-settings-from-dialog")
    check("refused key: 'Open settings' opens the add-on settings", opened, opened)
    rpc("Input.Back")
    thread.join(60)
    stop_kodi()


def phase_mock():
    global mock
    point_subdl_at_mock(True)
    mock = subprocess.Popen([sys.executable, "/harness/mock_subdl.py", "/tmp/mock.crt", "/tmp/mock.key"])
    time.sleep(1)
    set_key(KEY)
    start_kodi()

    rows = search_dialog_rows(MOVIE)
    shot("05-film-results")
    note("film rows", rows)
    check("film: exact release in the preferred language listed first, with sync and 5 stars",
          rows and rows[0]["Label"] == "Persian" and rows[0]["Property(sync)"] == "true"
          and rows[0]["ActualIcon"] == "5" and rows[0]["Thumb"] == "fa", rows[:1])
    check("film: languages outside Kodi's subtitle settings are left out",
          rows and all(row["Label"] in ("Persian", "English") for row in rows), [row["Label"] for row in rows])
    take_first_row()
    saved = MEDIA + "/The.Matrix.1999.1080p.BluRay.x264-GROUP.fa.srt"
    check("film: Kodi saved the subtitle next to the video", wait_for(lambda: os.path.exists(saved), 20), saved)
    time.sleep(2)
    current = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle"]})["result"]
    check("film: Kodi plays with the downloaded subtitle", current["currentsubtitle"].get("language") == "per",
          current)
    rpc("GUI.SetFullscreen", {"fullscreen": True})
    time.sleep(1)
    rpc("Player.Seek", {"playerid": 1, "value": {"time": {"hours": 0, "minutes": 0, "seconds": 1}}})
    time.sleep(1.2)
    shot("06-film-subtitle-on-screen")
    rpc("GUI.SetFullscreen", {"fullscreen": False})
    stop_playing()

    rows = search_dialog_rows(EPISODE)
    shot("07-episode-results")
    note("episode rows", rows)
    check("episode: the episode's file out of a season pack, marked as such",
          rows and rows[0]["Label2"].endswith("[Season pack]") and rows[0]["Property(sync)"] == "true", rows[:1])
    take_first_row()
    saved = MEDIA + "/Breaking.Bad.S01E05.720p.BluRay.x264-DEMAND.en.srt"
    ok = wait_for(lambda: os.path.exists(saved), 20)
    content = open(saved, encoding="utf-8").read() if ok else ""
    check("episode: Kodi saved that episode's subtitle", "Episode five." in content, content)
    stop_playing()

    thread, _ = run_plugin("action=manualsearch&searchstring=limit%20test&languages=English")
    dialog = wait_window((OK,))
    time.sleep(1)
    shot("08-daily-limit-dialog")
    check("daily limit: dialog with the panel link", dialog, dialog)
    rpc("Input.Select")
    thread.join(60)
    thread, _ = run_plugin("action=manualsearch&searchstring=limit%20test&languages=English")
    thread.join(60)
    time.sleep(0.5)
    shot("09-daily-limit-second-time-notice")
    check("daily limit: a notice, not a second dialog", window()[1] not in (OK, YESNO), window())

    # Add-ons > My add-ons > Subtitles > SubDL > Settings: there on every Kodi version.
    rpc("GUI.ActivateWindow", {"window": "addonbrowser", "parameters": ["addons://user/xbmc.subtitle.module"]})
    time.sleep(2)
    focus(r"^SubDL$", "down")
    rpc("Input.ContextMenu")
    wait_window((CONTEXT_MENU,), 10)
    focus(r"^Settings$", "down")
    rpc("Input.Select")
    opened = wait_window((ADDON_SETTINGS,), 10)
    time.sleep(1)
    shot("10-settings-account")
    check("settings: open from the add-on browser", opened, opened)
    click(182, 217)  # the "Search" category
    time.sleep(1.5)
    shot("11-settings-search")
    click(182, 154)  # back to "Account"; focus is now on the category list
    time.sleep(1)
    rpc("Input.ExecuteAction", {"action": "right"})
    time.sleep(0.6)
    focus(r"^Check my API key$", "down")
    rpc("Input.Select")
    dialog = wait_window((OK,), 30)
    time.sleep(1)
    shot("12-check-my-api-key")
    check("settings: 'Check my API key' shows the account", dialog, dialog)
    rpc("Input.Select")
    stop_kodi()


def saved_subtitles(video):
    stem = os.path.splitext(video)[0]
    return [path for path in glob.glob(glob.escape(stem) + ".*") if path != video]


def live_rows_and_download(video, label):
    for path in saved_subtitles(video):  # an earlier phase may have saved one under the same name
        os.remove(path)
    rows = search_dialog_rows(video)
    shot("13-live-%s-results" % label)
    note("live %s rows" % label, rows)
    check("live %s: SubDL lists subtitles in Kodi's languages" % label,
          rows and all(row["Label"] in ("Persian", "English") for row in rows), [row["Label"] for row in rows])
    check("live %s: both of Kodi's languages are listed" % label,
          {row["Label"] for row in rows} == {"Persian", "English"}, sorted({row["Label"] for row in rows}))
    take_first_row()
    new = wait_for(lambda: saved_subtitles(video), 30) or []
    check("live %s: Kodi saved the first row's subtitle next to the video" % label, new,
          [os.path.basename(path) for path in new])
    text = None
    if new:
        with open(new[0], "rb") as handle:
            try:
                text = handle.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                pass
    check("live %s: the saved subtitle is UTF-8" % label, text is not None, os.path.basename(new[0]) if new else None)
    if text is not None and ".fa." in os.path.basename(new[0]):
        letters = re.findall(r"[\u0600-\u06ff]", text)
        check("live %s: the Persian subtitle is in Persian letters" % label, len(letters) > 100,
              len(letters))
    time.sleep(2)
    current = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle"]})["result"]
    check("live %s: Kodi plays with the downloaded subtitle" % label, current["currentsubtitle"].get("language"),
          current)
    # Pause on the first line that falls inside the 5-minute sample video.
    cues = re.findall(r"(\d\d):(\d\d):(\d\d)[,.](\d{3}) -->", text or "")
    starts = [int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000 for h, m, sec, ms in cues]
    start = next((value for value in starts if 3 <= value < 290), None)
    if start is not None:
        rpc("GUI.SetFullscreen", {"fullscreen": True})
        at = int(start + 1)
        rpc("Player.Seek", {"playerid": 1, "value": {"time": {"hours": 0, "minutes": at // 60, "seconds": at % 60}}})
        time.sleep(1)
        rpc("Player.PlayPause", {"playerid": 1, "play": False})
        time.sleep(3)
        shot("14-live-%s-on-screen" % label)
        rpc("GUI.SetFullscreen", {"fullscreen": False})
    stop_playing()


def phase_live():
    key = os.environ.get("SUBDL_LIVE_KEY", "").strip()
    if not key:
        raise SystemExit("the live phase needs a real key in SUBDL_LIVE_KEY")
    point_subdl_at_mock(False)
    set_key(key)
    start_kodi()
    live_rows_and_download(MOVIE, "film")
    live_rows_and_download(EPISODE, "episode")
    stop_kodi()


def requests_and_log_checks():
    requests = []
    if os.path.exists(OUT + "/requests.jsonl"):
        with open(OUT + "/requests.jsonl") as handle:
            requests = [json.loads(line) for line in handle if line.strip()]
    note("mock requests", requests)
    agent = re.compile(r"^SubDL-Kodi/\d+\.\d+\.\d+ \(service\.subtitles\.subdl; Kodi/\d+\.\d+; \w+\)$")
    if requests:
        check("every request names the add-on in its User-Agent",
              all(agent.match(r["ua"] or "") for r in requests), sorted({r["ua"] for r in requests}))
        searches = [r for r in requests if r["path"] == "/api/v1/subtitles"]
        check("every search says client=kodi", all(r["query"].get("client") == "kodi" for r in searches),
              len(searches))
        downloads = [r for r in requests if r["host"] == "dl.subdl.com"]
        check("every download carries the viewer's key", all(r["query"].get("api_key") == KEY for r in downloads),
              len(downloads))
    with open(KODI + "/temp/kodi.log", errors="replace") as handle:
        log = handle.read()
    ours = [line for line in log.splitlines() if "[%s]" % ADDON in line]
    note("add-on log lines", ours)
    live_key = os.environ.get("SUBDL_LIVE_KEY", "").strip() or KEY
    check("the add-on's log lines hold no key, address, title or file name",
          not any(KEY in line or live_key in line or "Matrix" in line or "Breaking" in line or "http" in line for line in ours),
          len(ours))
    check("no Python traceback from the add-on",
          not re.search(r"Traceback[^\n]*\n(?:[^\n]*\n){0,6}[^\n]*%s" % re.escape(ADDON), log), None)


def main():
    subprocess.Popen(["su", "viewer", "-s", "/bin/sh", "-c", "exec Xvfb :99 -screen 0 1280x720x24 -ac -nolisten tcp"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    phases = sys.argv[1:] or ["missing_key", "refused_key", "mock"]
    try:
        if "missing_key" in phases:
            phase_missing_key()
        if "refused_key" in phases:
            phase_refused_key()
        if "mock" in phases:
            phase_mock()
        if "live" in phases:
            phase_live()
        requests_and_log_checks()
    finally:
        stop_kodi()
        if mock:
            mock.terminate()
        with open(OUT + "/report.json", "w") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
    failed = [name for name, result in report["checks"].items() if not result["passed"]]
    print("%d checks, %d failed%s" % (len(report["checks"]), len(failed), (": " + ", ".join(failed)) if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
