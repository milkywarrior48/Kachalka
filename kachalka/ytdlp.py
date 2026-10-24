"""Обёртка над yt-dlp: метаданные и загрузка."""
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from . import reddit
from .platforms import Platform, detect
from .util import sanitize

FILE_MARK = "KACHALKA_FILE:"
_PCT = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
_SPEED = re.compile(r"at\s+(\S+/s)")
_ETA = re.compile(r"ETA\s+(\S+)")
_UPDATE_HINT = (
    "\nВозможно, yt-dlp устарел. Обновите: su - -c 'apt-get update && apt-get install yt-dlp'"
)


class YtdlpError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Metadata:
    source_url: str       # что ввёл пользователь
    url: str              # что отдаём yt-dlp (для Reddit — HLS-ссылка)
    title: str
    duration: float
    thumbnail: str
    uploader: str
    platform: Platform


def _binary():
    path = shutil.which("yt-dlp")
    if not path:
        raise YtdlpError("Не найден yt-dlp. Установите: su - -c 'apt-get install yt-dlp'")
    return path


def detect_browser():
    """Браузер, из которого yt-dlp может взять cookies (нужно для Instagram)."""
    home = os.path.expanduser("~")
    candidates = [
        (".mozilla/firefox", "firefox"),
        (".config/chromium", "chromium"),
        (".config/google-chrome", "chrome"),
        (".config/BraveSoftware", "brave"),
        (".config/yandex-browser", "chromium:" + os.path.join(home, ".config/yandex-browser")),
    ]
    for rel, name in candidates:
        if os.path.isdir(os.path.join(home, rel)):
            return name
    return None


def _cookie_args(platform):
    if platform is Platform.INSTAGRAM:
        browser = detect_browser()
        if browser:
            return ["--cookies-from-browser", browser]
    return []


def _last_error(text):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    errors = [l for l in lines if l.startswith("ERROR")]
    msg = errors[-1] if errors else (lines[-1] if lines else "Неизвестная ошибка")
    return msg.replace("ERROR: ", "") + _UPDATE_HINT


def fetch_metadata(source_url):
    platform = detect(source_url)
    url, title, thumb = source_url, None, None
    if platform is Platform.REDDIT:
        resolved = reddit.resolve(source_url)
        if resolved:
            url, title, thumb = resolved["url"], resolved["title"], resolved["thumbnail"]

    cmd = [_binary(), "-J", "--no-playlist", "--no-warnings",
           *_cookie_args(platform), url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise YtdlpError("Сайт не ответил за 90 секунд")
    if proc.returncode != 0:
        raise YtdlpError(_last_error(proc.stderr))
    info = json.loads(proc.stdout)

    if not thumb:
        thumb = info.get("thumbnail") or ""
        for t in reversed(info.get("thumbnails") or []):
            u = t.get("url", "")
            if re.search(r"\.(jpe?g|png)(\?|$)", u):
                thumb = u
                break
    return Metadata(
        source_url=source_url, url=url,
        title=title or info.get("title") or "video",
        duration=float(info.get("duration") or 0),
        thumbnail=thumb or "",
        uploader=info.get("uploader") or info.get("channel") or "",
        platform=platform,
    )


def build_command(item):
    m = item.meta
    name = sanitize(m.title) + (" [фрагмент]" if item.clip else "")
    cmd = [
        _binary(), "--no-playlist", "--no-warnings", "--windows-filenames",
        "--newline", "--progress", "--embed-metadata",
        "--print", f"after_move:{FILE_MARK}%(filepath)s", "--no-quiet",
        "-P", item.save_dir, "-o", name.replace("%", "%%") + ".%(ext)s",
        *_cookie_args(m.platform),
    ]
    res = f"res:{item.resolution}" if item.resolution else "res"
    if item.fmt == "mp3":
        cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    elif item.fmt == "webm":
        cmd += ["-f", "bv*[ext=webm]+ba[ext=webm]/bv*+ba/b", "-S", res,
                "--merge-output-format", "webm"]
    else:  # mp4 / mov
        cmd += ["-f", "bv*+ba/b", "-S", f"{res},vcodec:h264,acodec:m4a",
                "--merge-output-format", "mp4"]
        if item.fmt == "mov":
            cmd += ["--remux-video", "mov"]
    if item.clip:
        start, end = item.clip
        cmd += ["--download-sections", f"*{int(start)}-{int(end)}",
                "--force-keyframes-at-cuts"]
    cmd.append(m.url)
    return cmd


def download(item):
    """Блокирующая загрузка. Возвращает путь к итоговому файлу."""
    cmd = build_command(item)
    audio_only = item.fmt == "mp3"
    phase, tail, path = 0, [], None
    item.proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    for line in item.proc.stdout:
        line = line.rstrip()
        tail = (tail + [line])[-15:]
        if line.startswith(FILE_MARK):
            path = line[len(FILE_MARK):]
        elif "[download] Destination:" in line:
            phase += 1
        m = _PCT.search(line)
        if m:
            pct = float(m.group(1)) / 100
            if audio_only:
                value = pct
            elif phase <= 1:
                value = pct * 0.9
            else:
                value = 0.9 + pct * 0.1
            sp, eta = _SPEED.search(line), _ETA.search(line)
            item.update(progress=max(item.progress, value),
                        speed=sp.group(1) if sp else "", eta=eta.group(1) if eta else "")
        elif line.startswith("[Merger]") or line.startswith("[ExtractAudio]") \
                or line.startswith("[VideoRemuxer]"):
            item.update(message="Обработка…")
    code = item.proc.wait()
    if item.cancelled:
        raise Cancelled()
    if code != 0 or not path:
        raise YtdlpError(_last_error("\n".join(tail)))
    item.update(progress=1.0, speed="", eta="")
    return path
