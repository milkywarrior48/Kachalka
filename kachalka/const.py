APP_ID = "ru.kachalka.Kachalka"
APP_NAME = "Качалка"
VERSION = "1.0.1"
MAX_CONCURRENT = 3          # одновременных загрузок
HISTORY_LIMIT = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
)

FORMATS = [("MP4", "mp4"), ("MOV", "mov"), ("WebM", "webm"), ("MP3", "mp3")]
RESOLUTIONS = [
    ("Лучшее", 0), ("4K", 2160), ("1440p", 1440), ("1080p", 1080),
    ("720p", 720), ("480p", 480), ("360p", 360),
]
