"""A fake of Kodi's xbmcaddon module."""

import os

from kodistate import ADDON_DIR, state


class Addon:
    def __init__(self, id=None):
        if id is None and not state.in_addon_context:
            # What Kodi does for a script started with RunScript(path).
            raise RuntimeError("No valid addon id could be obtained. None was passed and the script "
                               "wasn't executed in a normal Kodi manner.")
        self.id = id or "service.subtitles.subdl"

    def getSetting(self, key):
        return state.settings.get(key, "")

    def getAddonInfo(self, key):
        return {
            "id": "service.subtitles.subdl",
            "name": "SubDL",
            "version": "1.0.0",
            "path": ADDON_DIR,
            "profile": state.profile,
            "icon": os.path.join(ADDON_DIR, "icon.png"),
        }[key]

    def getLocalizedString(self, string_id):
        # Kodi returns "" for an unknown id; failing loudly catches a missing string.
        return state.strings[string_id]

    def openSettings(self):
        state.opened_settings += 1
