"""A fake of Kodi's xbmcgui module that records every dialog."""

from kodistate import state

NOTIFICATION_INFO, NOTIFICATION_WARNING, NOTIFICATION_ERROR = "info", "warning", "error"


class ListItem:
    def __init__(self, label="", label2="", path="", offscreen=False):
        self.label = label
        self.label2 = label2
        self.art = {}
        self.properties = {}

    def getLabel(self):
        return self.label

    def setArt(self, values):
        self.art.update(values)

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, "")


class Dialog:
    def ok(self, heading, message):
        state.dialogs.append(("ok", heading, message))
        return True

    def yesno(self, heading, message, nolabel="", yeslabel="", autoclose=0, defaultbutton=0):
        state.dialogs.append(("yesno", heading, message, nolabel, yeslabel))
        return state.yesno_answer

    def notification(self, heading, message, icon="", time=5000, sound=True):
        state.dialogs.append(("notification", heading, message))

    def select(self, heading, options, autoclose=0, preselect=-1, useDetails=False):
        state.dialogs.append(("select", heading, list(options)))
        return state.select_answer


class Window:
    def __init__(self, window_id):
        self.window_id = window_id

    def getProperty(self, key):
        return state.window.get((self.window_id, key), "")

    def setProperty(self, key, value):
        state.window[(self.window_id, key)] = value
