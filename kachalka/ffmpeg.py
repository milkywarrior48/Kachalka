"""Сжатие под целевой размер через ffmpeg."""
import os
import shutil
import subprocess

from .ytdlp import Cancelled, YtdlpError

AUDIO_KBPS = 128


def _duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def compress(item, path):
    """Пережимает файл так, чтобы он уложился в item.target_mb."""
    if not shutil.which("ffmpeg"):
        raise YtdlpError("Не найден ffmpeg. Установите: su - -c 'apt-get install ffmpeg'")
    target_bytes = item.target_mb * 1024 * 1024
    if os.path.getsize(path) <= target_bytes:
        return path
    duration = _duration(path) or item.meta.duration
    if duration <= 0:
        raise YtdlpError("Не удалось определить длительность для сжатия")

    total_kbps = target_bytes * 8 * 0.95 / duration / 1000
    base, ext = os.path.splitext(path)
    tmp = f"{base}.kachalka-tmp{ext}"

    if item.fmt == "mp3":
        codec = ["-c:a", "libmp3lame", "-b:a", f"{int(total_kbps)}k"]
        if total_kbps < 32:
            raise YtdlpError("Целевой размер слишком мал для такой длительности")
    else:
        video_kbps = int(total_kbps - AUDIO_KBPS)
        if video_kbps < 100:
            raise YtdlpError("Целевой размер слишком мал для такой длительности")
        if item.fmt == "webm":
            codec = ["-c:v", "libvpx-vp9", "-b:v", f"{video_kbps}k", "-row-mt", "1",
                     "-c:a", "libopus", "-b:a", f"{AUDIO_KBPS}k"]
        else:
            codec = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{video_kbps}k",
                     "-maxrate", f"{int(video_kbps * 1.2)}k", "-bufsize", f"{video_kbps * 2}k",
                     "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-movflags", "+faststart"]

    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1", "-i", path, *codec, tmp]
    item.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in item.proc.stdout:
        if line.startswith(("out_time_us=", "out_time_ms=")):
            try:
                done = int(line.split("=")[1]) / 1_000_000
                item.update(progress=min(done / duration, 0.99))
            except ValueError:
                pass
    err = item.proc.stderr.read()
    code = item.proc.wait()
    if item.cancelled:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise Cancelled()
    if code != 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise YtdlpError("ffmpeg: " + (err.strip().splitlines() or ["ошибка"])[-1])
    os.replace(tmp, path)
    return path
