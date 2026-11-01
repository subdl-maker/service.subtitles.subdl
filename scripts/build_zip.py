"""Build dist/service.subtitles.subdl-<version>.zip, installable with Kodi's "Install from zip".

The zip holds exactly the add-on folder, which is also what goes into a repo-scripts
pull request. Entries are sorted and dated 2026-01-01 so the same source always
gives the same zip, byte for byte.

    python3 scripts/build_zip.py
"""

import hashlib
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_ID = "service.subtitles.subdl"
ADDON_DIR = os.path.join(ROOT, ADDON_ID)
DIST = os.path.join(ROOT, "dist")
STAMP = (2026, 1, 1, 0, 0, 0)
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def addon_files():
    for folder, dirs, files in os.walk(ADDON_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or name.endswith(SKIP_SUFFIXES):
                continue
            path = os.path.join(folder, name)
            yield path, os.path.relpath(path, ROOT).replace(os.sep, "/")


def entry(name, mode):
    info = zipfile.ZipInfo(name, STAMP)
    info.create_system = 3  # unix, so the permission bits below are read
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main():
    version = ET.parse(os.path.join(ADDON_DIR, "addon.xml")).getroot().get("version")
    os.makedirs(DIST, exist_ok=True)
    target = os.path.join(DIST, "%s-%s.zip" % (ADDON_ID, version))
    folders = set()
    with zipfile.ZipFile(target, "w") as archive:
        for path, name in addon_files():
            parts = name.split("/")[:-1]
            for depth in range(1, len(parts) + 1):
                folder = "/".join(parts[:depth]) + "/"
                if folder not in folders:
                    folders.add(folder)
                    archive.writestr(entry(folder, 0o40755), b"")
            with open(path, "rb") as handle:
                archive.writestr(entry(name, 0o100644), handle.read())
    with open(target, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    print("%s\nsha256 %s" % (os.path.relpath(target, ROOT), digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
