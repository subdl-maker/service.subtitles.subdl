"""A fake of Kodi's xbmc module, enough for the subtitle add-on."""

import json

from kodistate import state

LOGDEBUG, LOGINFO, LOGWARNING, LOGERROR, LOGFATAL = 0, 1, 2, 3, 4
ISO_639_1, ISO_639_2, ENGLISH_NAME = 0, 1, 2

# name, ISO 639-1, ISO 639-2 as Kodi's LangCodeExpander has them.
_LANGUAGES = [
    ("Arabic", "ar", "ara"),
    ("Chinese", "zh", "chi"),
    ("English", "en", "eng"),
    ("French", "fr", "fre"),
    ("German", "de", "ger"),
    ("Manipuri", "", "mni"),
    ("Persian", "fa", "per"),
    ("Portuguese", "pt", "por"),
    ("Portuguese (Brazil)", "pb", "pob"),
    ("Serbian", "sr", "scc"),
    ("Spanish", "es", "spa"),
    ("Welsh", "cy", "wel"),
]


def log(message, level=LOGDEBUG):
    state.logs.append((level, message))


def getInfoLabel(name):
    return state.labels.get(name, "")


def getCondVisibility(condition):
    return condition in state.conditions


def convertLanguage(value, format):
    key = (value or "").strip().lower()
    for name, iso1, iso2 in _LANGUAGES:
        if key in (name.lower(), iso1, iso2):
            return (iso1, iso2, name)[format]
    return ""


def executeJSONRPC(request):
    return json.dumps(state.jsonrpc(json.loads(request)))


class Player:
    def getPlayingFile(self):
        if not state.playing_file:
            raise RuntimeError("Kodi is not playing any file")
        return state.playing_file
