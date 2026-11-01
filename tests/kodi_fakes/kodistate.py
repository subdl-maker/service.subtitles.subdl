"""State shared by the fake Kodi modules: what the add-on reads, and what it did."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADDON_DIR = os.path.join(ROOT, "service.subtitles.subdl")


def load_strings():
    """msgctxt id -> msgid from the add-on's English strings.po."""
    path = os.path.join(ADDON_DIR, "resources", "language", "resource.language.en_gb", "strings.po")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {int(number): message.replace('\\"', '"')
            for number, message in re.findall(r'msgctxt "#(\d+)"\s*\nmsgid "((?:[^"\\]|\\.)*)"', text)}


class State:
    def __init__(self):
        self.reset()

    def reset(self, profile=""):
        self.labels = {"System.BuildVersion": "21.2 (21.2.0) Git:20250101-test"}
        self.conditions = {"System.Platform.Linux"}
        self.settings = {"api_key": "", "hearing_impaired": "0", "season_packs": "true"}
        self.playing_file = ""
        self.tvshows = {}
        self.profile = profile
        self.strings = load_strings()
        self.logs = []
        self.dialogs = []
        self.items = []
        self.ended = []
        self.window = {}
        self.yesno_answer = False
        self.select_answer = 0
        self.opened_settings = 0
        #: False for a script started with RunScript(path), as the settings button does.
        self.in_addon_context = True

    def jsonrpc(self, request):
        if request.get("method") == "VideoLibrary.GetTVShowDetails":
            show = self.tvshows.get(request["params"]["tvshowid"])
            if show is not None:
                return {"jsonrpc": "2.0", "id": request.get("id"), "result": {"tvshowdetails": show}}
        return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32602}}

    def logged(self):
        return "\n".join(message for _level, message in self.logs)


state = State()
