import json
import os

from gi.repository import GLib

_PATH = os.path.join(GLib.get_user_config_dir(), "kachalka", "settings.json")


def default_save_dir():
    for kind in (GLib.UserDirectory.DIRECTORY_VIDEOS,
                 GLib.UserDirectory.DIRECTORY_DOWNLOAD):
        path = GLib.get_user_special_dir(kind)
        if path and os.path.isdir(path):
            return path
    return os.path.expanduser("~")


DEFAULTS = {
    "save_dir": None,
    "format": "mp4",
    "resolution": 0,
    "watch_clipboard": True,
}


def load():
    data = dict(DEFAULTS)
    try:
        with open(_PATH, encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    if not data["save_dir"] or not os.path.isdir(data["save_dir"]):
        data["save_dir"] = default_save_dir()
    return data


def save(data):
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
