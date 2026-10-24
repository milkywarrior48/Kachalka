import json
import os
import time

from gi.repository import GLib

from .const import HISTORY_LIMIT

_PATH = os.path.join(GLib.get_user_data_dir(), "kachalka", "history.json")


def load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write(entries):
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(entries[:HISTORY_LIMIT], f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def add(title, url, path, platform, fmt):
    entries = load()
    entries.insert(0, {
        "title": title, "url": url, "path": path,
        "platform": platform, "format": fmt,
        "date": time.strftime("%d.%m.%Y %H:%M"),
    })
    _write(entries)


def remove(index):
    entries = load()
    if 0 <= index < len(entries):
        del entries[index]
        _write(entries)


def clear():
    _write([])
