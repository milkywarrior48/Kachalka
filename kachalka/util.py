import re


def fmt_time(seconds):
    seconds = max(0, int(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def sanitize(name, limit=120):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name or "video").strip(" .")
    return (name or "video")[:limit]
