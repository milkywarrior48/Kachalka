"""Резолвер Reddit через api.reddit.com (экстрактор yt-dlp для Reddit нестабилен)."""
import json
import re
from urllib.request import Request, urlopen

from .const import USER_AGENT


def _get(url):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=15)


def resolve(url):
    """Возвращает {'url', 'title', 'thumbnail'} либо None, если это не видео-пост."""
    try:
        final = _get(url).geturl()          # раскрываем redd.it и /s/-ссылки
        m = re.search(r"/comments/([a-z0-9]+)", final)
        if not m:
            return None
        data = json.load(_get(f"https://api.reddit.com/comments/{m.group(1)}?raw_json=1"))
        post = data[0]["data"]["children"][0]["data"]
        for p in [post] + post.get("crosspost_parent_list", []):
            media = (p.get("secure_media") or p.get("media") or {}).get("reddit_video")
            if not media:
                media = (p.get("preview") or {}).get("reddit_video_preview")
            if media:
                thumb = post.get("thumbnail")
                return {
                    "url": media.get("hls_url") or media["fallback_url"],
                    "title": post.get("title") or "reddit",
                    "thumbnail": thumb if thumb and thumb.startswith("http") else None,
                }
    except Exception:
        pass
    return None
