"""A fake of Kodi's xbmcplugin module that records the rows an add-on hands back."""

from kodistate import state


def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
    state.items.append({"handle": handle, "url": url, "listitem": listitem, "folder": isFolder})
    return True


def endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
    state.ended.append(handle)
