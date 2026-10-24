from enum import Enum
from urllib.parse import urlparse


class Platform(Enum):
    YOUTUBE = "YouTube"
    X = "X / Twitter"
    INSTAGRAM = "Instagram"
    TIKTOK = "TikTok"
    REDDIT = "Reddit"
    UNKNOWN = "Другой сайт"


_HOSTS = {
    Platform.YOUTUBE: ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    Platform.X: ("x.com", "twitter.com", "t.co"),
    Platform.INSTAGRAM: ("instagram.com",),
    Platform.TIKTOK: ("tiktok.com",),
    Platform.REDDIT: ("reddit.com", "redd.it"),
}


def host_of(url):
    return (urlparse(url).hostname or "").lower()


def detect(url):
    host = host_of(url)
    for platform, domains in _HOSTS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return Platform.UNKNOWN
