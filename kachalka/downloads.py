"""Очередь загрузок (до MAX_CONCURRENT одновременно)."""
import threading
from enum import Enum

from gi.repository import GLib

from . import ffmpeg, history, ytdlp
from .const import MAX_CONCURRENT


class Status(Enum):
    QUEUED = "В очереди"
    DOWNLOADING = "Загрузка"
    COMPRESSING = "Сжатие"
    DONE = "Готово"
    FAILED = "Ошибка"
    CANCELLED = "Отменено"


class DownloadItem:
    def __init__(self, meta, fmt, resolution, target_mb, clip, save_dir):
        self.meta, self.fmt, self.resolution = meta, fmt, resolution
        self.target_mb, self.clip, self.save_dir = target_mb, clip, save_dir
        self.status = Status.QUEUED
        self.progress = 0.0
        self.speed = self.eta = self.message = self.error = ""
        self.filepath = None
        self.proc = None
        self.cancelled = False
        self.listeners = []

    @property
    def active(self):
        return self.status in (Status.QUEUED, Status.DOWNLOADING, Status.COMPRESSING)

    def update(self, **kw):
        """Потокобезопасно меняет поля и уведомляет UI в главном потоке."""
        for k, v in kw.items():
            setattr(self, k, v)
        for cb in list(self.listeners):
            GLib.idle_add(cb, self)

    def cancel(self):
        self.cancelled = True            # сначала флаг, потом terminate
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        if self.status is Status.QUEUED:
            self.update(status=Status.CANCELLED, message="")


class DownloadManager:
    def __init__(self):
        self.items = []
        self._lock = threading.Lock()

    def add(self, item):
        with self._lock:
            self.items.append(item)
        self._start_next()

    def active_count(self):
        return sum(1 for i in self.items if i.active)

    def cancel_all(self):
        for item in self.items:
            if item.active:
                item.cancel()

    def _start_next(self):
        with self._lock:
            running = sum(1 for i in self.items
                          if i.status in (Status.DOWNLOADING, Status.COMPRESSING))
            for item in self.items:
                if running >= MAX_CONCURRENT:
                    break
                if item.status is Status.QUEUED and not item.cancelled:
                    item.status = Status.DOWNLOADING     # резервируем слот
                    running += 1
                    threading.Thread(target=self._run, args=(item,), daemon=True).start()

    def _run(self, item):
        try:
            item.update(status=Status.DOWNLOADING, message="")
            path = ytdlp.download(item)
            if item.target_mb:
                item.update(status=Status.COMPRESSING, progress=0.0, message="Сжатие…")
                path = ffmpeg.compress(item, path)
            history.add(item.meta.title, item.meta.source_url, path,
                        item.meta.platform.value, item.fmt)
            item.update(status=Status.DONE, filepath=path, message="")
        except ytdlp.Cancelled:
            item.update(status=Status.CANCELLED, message="")
        except Exception as e:                      # noqa: BLE001
            item.update(status=Status.FAILED, error=str(e))
        finally:
            self._start_next()                      # после любого исхода
