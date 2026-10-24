Name: kachalka
Version: 1.0.1
Release: alt1

Summary: Kachalka - video downloader (yt-dlp frontend)
Summary(ru_RU.UTF-8): Качалка - загрузчик видео (графическая оболочка для yt-dlp)
License: MIT
Group: Video
Url: https://example.org/kachalka
BuildArch: noarch

# Приложение не предоставляет Python-модулей другим пакетам;
# зависимости перечислены вручную, автоанализ python3.prov/req отключаем.
AutoReqProv: no

Source0: %name-%version.tar

# Python-приложение на GTK4 + libadwaita
Requires: python3
Requires: python3-module-pygobject3
Requires: libgtk4-gir
Requires: libadwaita-gir
# Движок загрузки и обработка видео
Requires: yt-dlp
Requires: ffmpeg

%description
Kachalka is a simple GNOME-style application for downloading videos from
YouTube, X/Twitter, Instagram, TikTok, Reddit and any other site supported
by yt-dlp. It can pick format (MP4, MOV, WebM, MP3) and resolution, cut
a fragment, and re-encode the result to a target file size.

%description -l ru_RU.UTF-8
Качалка - простое приложение в стиле GNOME для скачивания видео с YouTube,
X/Twitter, Instagram, TikTok, Reddit и любых других сайтов, поддерживаемых
yt-dlp. Позволяет выбрать формат (MP4, MOV, WebM, MP3) и разрешение,
вырезать фрагмент и сжать результат до нужного размера файла.

%prep
%setup

%build

%install
make install DESTDIR=%buildroot PREFIX=%_prefix

%files
%_bindir/kachalka
%_datadir/kachalka/
%_datadir/applications/ru.kachalka.Kachalka.desktop
%_datadir/icons/hicolor/*/apps/ru.kachalka.Kachalka.png
%doc README.md LICENSE

%changelog
* Sat Oct 24 2026 milkywarrior <milkywarrior48@gmail.com> 1.0.1-alt1
- Added application icon
- Download folder selector is now always visible under the URL field

* Sat Oct 24 2026 milkywarrior <milkywarrior48@gmail.com> 1.0.0-alt1
- Initial build
