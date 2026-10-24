import re

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def extract(text):
    """Первая http(s)-ссылка из текста или None."""
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(").,;") if m else None
