# Качалка

Загрузчик видео для ALT Workstation (GNOME): оболочка GTK4 + libadwaita над `yt-dlp` и `ffmpeg`.
Работает с YouTube, X/Twitter, Instagram, TikTok, Reddit и любыми сайтами, которые знает yt-dlp.

## Возможности
- вставка ссылки кнопкой, перетаскиванием в окно и подсказкой «Вставить» при возвращении в окно, если в буфере ссылка;
- превью: миниатюра, название, площадка, длительность;
- формат MP4 / MOV / WebM / MP3, разрешение 4K–360p;
- целевой размер файла (сжатие ffmpeg под заданное число МБ);
- вырезание фрагмента по таймкодам;
- очередь (до 3 загрузок одновременно), отмена, история загрузок;
- Reddit — через api.reddit.com; Instagram — автоподхват cookies из установленного браузера.

## Зависимости (ALT Linux 11 / p11)
| Пакет | Зачем |
|---|---|
| `python3`, `python3-module-pygobject3` | запуск приложения |
| `libgtk4-gir`, `libadwaita-gir` | интерфейс (GTK ≥ 4.10, libadwaita ≥ 1.4) |
| `yt-dlp` | загрузка |
| `ffmpeg` | склейка, конвертация, сжатие (нужны libx264, libmp3lame) |

В spec-файле они прописаны как `Requires:`, так что `apt-get install ./kachalka-*.rpm` подтянет всё сам.

## Сборка .rpm
```bash
su -
apt-get install rpm-build make
exit

tar xzf kachalka-1.0.1.tar.gz
cd kachalka-1.0.1
make rpm
# готовый пакет: rpmbuild/RPMS/noarch/kachalka-1.0.1-alt1.noarch.rpm
```

## Установка
```bash
su -
apt-get install ./kachalka-1.0.1-alt1.noarch.rpm
```
Запуск: «Качалка» в меню приложений или команда `kachalka`.

## Запуск из исходников без установки
```bash
make run
```

## Если что-то не скачивается
Сайты часто меняют разметку, и yt-dlp приходится обновлять:
```bash
su - -c 'apt-get update && apt-get install yt-dlp'
```

## Другие RPM-дистрибутивы
Исходники не привязаны к ALT, меняются только имена в `Requires:` в `kachalka.spec`
(Fedora: `python3-gobject`, `gtk4`, `libadwaita`, `yt-dlp`, `ffmpeg`; ffmpeg из RPM Fusion).
