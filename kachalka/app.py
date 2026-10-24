import os
import threading
from urllib.request import Request, urlopen

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from . import history, settings, urldetect, ytdlp  # noqa: E402
from .const import (APP_ID, APP_NAME, FORMATS, RESOLUTIONS, USER_AGENT,  # noqa: E402
                    VERSION)
from .downloads import DownloadItem, DownloadManager, Status  # noqa: E402
from .platforms import Platform, host_of  # noqa: E402
from .util import fmt_time  # noqa: E402


class PillGroup(Gtk.FlowBox):
    """Ряд кнопок-«таблеток» с единственным выбором."""

    def __init__(self, options, value=None, on_change=None):
        super().__init__(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                         max_children_per_line=12, column_spacing=6, row_spacing=6,
                         valign=Gtk.Align.START)
        self._items = []
        self._on_change = None
        first = None
        for label, val in options:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("k-pill")
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.connect("toggled", self._toggled)
            self._items.append((btn, val))
            self.append(btn)
        self.set_value(value if value is not None else options[0][1])
        self._on_change = on_change          # подключаем после начальной установки

    @property
    def value(self):
        for btn, val in self._items:
            if btn.get_active():
                return val
        return self._items[0][1]

    def set_value(self, value):
        for btn, val in self._items:
            if val == value:
                btn.set_active(True)
                return

    def _toggled(self, btn):
        if btn.get_active() and self._on_change:
            self._on_change(self.value)


def labeled(title, widget):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    label = Gtk.Label(label=title.upper(), xalign=0)
    label.add_css_class("k-section")
    box.append(label)
    box.append(widget)
    return box


class DownloadRow(Gtk.ListBoxRow):
    def __init__(self, item, window):
        super().__init__(activatable=False, selectable=False)
        self.item, self.win = item, window
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                      margin_top=12, margin_bottom=12, margin_start=14, margin_end=14)
        top = Gtk.Box(spacing=8)
        self.title = Gtk.Label(label=item.meta.title, xalign=0, hexpand=True,
                               ellipsize=3)  # Pango.EllipsizeMode.END
        self.title.add_css_class("heading")
        self.button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.button.add_css_class("flat")
        self.button.add_css_class("circular")
        self.button.connect("clicked", self._on_button)
        top.append(self.title)
        top.append(self.button)
        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("k-progress")
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("dim-label")
        self.status.add_css_class("caption")
        for w in (top, self.bar, self.status):
            box.append(w)
        self.set_child(box)
        item.listeners.append(self.refresh)
        self.refresh(item)

    def refresh(self, item):
        st = item.status
        self.bar.set_fraction(item.progress)
        self.bar.set_visible(st in (Status.QUEUED, Status.DOWNLOADING, Status.COMPRESSING))
        if st is Status.DOWNLOADING:
            parts = [f"{item.progress * 100:.0f}%", item.speed, f"осталось {item.eta}" if item.eta else ""]
            text = item.message or " · ".join(p for p in parts if p)
        elif st is Status.COMPRESSING:
            text = f"Сжатие до {item.target_mb} МБ · {item.progress * 100:.0f}%"
        elif st is Status.FAILED:
            text = item.error
        elif st is Status.DONE:
            text = f"Готово · {item.filepath}"
        else:
            text = st.value
        self.status.set_label(text)
        icon, tip = {
            Status.DONE: ("folder-open-symbolic", "Показать в папке"),
            Status.FAILED: ("user-trash-symbolic", "Убрать из списка"),
            Status.CANCELLED: ("user-trash-symbolic", "Убрать из списка"),
        }.get(st, ("window-close-symbolic", "Отменить"))
        self.button.set_icon_name(icon)
        self.button.set_tooltip_text(tip)
        return False

    def _on_button(self, _btn):
        st = self.item.status
        if st is Status.DONE:
            self.win.reveal(self.item.filepath)
        elif self.item.active:
            self.item.cancel()
        else:
            self.item.listeners.remove(self.refresh)
            self.get_parent().remove(self)


class KachalkaWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME, default_width=760, default_height=800)
        self.cfg = settings.load()
        self.manager = DownloadManager()
        self.meta = None
        self._last_clip = None
        self._force_close = False

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        view = Adw.ToolbarView()
        self.toasts.set_child(view)

        header = Adw.HeaderBar()
        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        menu = Gio.Menu()
        menu.append("Очистить историю", "win.clear-history")
        menu.append("О программе", "win.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        view.add_top_bar(header)
        view.set_content(self.stack)

        self.stack.add_titled_with_icon(self._build_new_page(), "new", "Новая", "list-add-symbolic")
        self.stack.add_titled_with_icon(self._build_downloads_page(), "downloads",
                                        "Загрузки", "folder-download-symbolic")
        self.stack.add_titled_with_icon(self._build_history_page(), "history",
                                        "История", "document-open-recent-symbolic")

        for name, cb in (("about", self._about), ("clear-history", self._clear_history)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)

        # drag-and-drop ссылок
        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        self.connect("notify::is-active", self._on_active)
        self.connect("close-request", self._on_close)
        self.refresh_history()

    # ---------- страница «Новая» ----------
    def _build_new_page(self):
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=680, margin_top=20, margin_bottom=20,
                          margin_start=16, margin_end=16)
        scroll.set_child(clamp)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(col)

        # URL
        card = Gtk.Box(spacing=8)
        card.add_css_class("k-card")
        self.entry = Gtk.Entry(hexpand=True, placeholder_text="Вставьте ссылку на видео")
        self.entry.connect("activate", lambda *_: self.analyze())
        paste = Gtk.Button(icon_name="edit-paste-symbolic", tooltip_text="Вставить из буфера")
        paste.add_css_class("k-pill")
        paste.connect("clicked", lambda *_: self.paste_from_clipboard())
        self.analyze_btn = Gtk.Button(label="Анализировать")
        self.analyze_btn.add_css_class("suggested-action")
        self.analyze_btn.add_css_class("k-pill")
        self.analyze_btn.connect("clicked", lambda *_: self.analyze())
        for w in (self.entry, paste, self.analyze_btn):
            card.append(w)
        col.append(card)

        # папка загрузки — всегда на виду, до анализа ссылки
        folder = Gtk.Box(spacing=10)
        folder.add_css_class("k-card")
        folder.append(Gtk.Image(icon_name="folder-symbolic"))
        hint = Gtk.Label(label="Сохранять в")
        hint.add_css_class("dim-label")
        self.folder_lbl = Gtk.Label(xalign=0, hexpand=True, ellipsize=2)
        choose = Gtk.Button(label="Изменить…")
        choose.add_css_class("k-pill")
        choose.connect("clicked", self._choose_folder)
        for w in (hint, self.folder_lbl, choose):
            folder.append(w)
        col.append(folder)
        self._update_folder_label()

        # превью
        self.preview = Gtk.Box(spacing=14, visible=False)
        self.preview.add_css_class("k-card")
        self.thumb = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        self.thumb.set_size_request(160, 90)
        self.thumb.add_css_class("k-thumb")
        self.thumb.set_overflow(Gtk.Overflow.HIDDEN)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER,
                       hexpand=True)
        self.p_title = Gtk.Label(xalign=0, wrap=True, lines=2, ellipsize=3)
        self.p_title.add_css_class("heading")
        meta_row = Gtk.Box(spacing=8)
        self.p_badge = Gtk.Label()
        self.p_badge.add_css_class("k-badge")
        self.p_meta = Gtk.Label(xalign=0)
        self.p_meta.add_css_class("dim-label")
        meta_row.append(self.p_badge)
        meta_row.append(self.p_meta)
        info.append(self.p_title)
        info.append(meta_row)
        self.preview.append(self.thumb)
        self.preview.append(info)
        col.append(self.preview)

        # параметры
        self.options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, visible=False)
        self.options.add_css_class("k-card")
        self.fmt = PillGroup(FORMATS, self.cfg["format"], self._on_format)
        self.res = PillGroup(RESOLUTIONS, self.cfg["resolution"])
        self.res_box = labeled("Разрешение", self.res)
        self.size = PillGroup([("Оригинал", 0), ("Свой размер", 1)], 0, self._on_size_mode)
        self.size_spin = Gtk.SpinButton.new_with_range(1, 20000, 1)
        self.size_spin.set_value(50)
        self.size_spin.set_visible(False)
        size_row = Gtk.Box(spacing=10)
        size_row.append(self.size)
        size_row.append(self.size_spin)
        size_row.append(Gtk.Label(label="МБ", visible=False))
        self.size_unit = size_row.get_last_child()
        for title, w in (("Формат", self.fmt),):
            self.options.append(labeled(title, w))
        self.options.append(self.res_box)
        self.options.append(labeled("Целевой размер", size_row))

        clip_row = Gtk.Box(spacing=10)
        clip_icon = Gtk.Image(icon_name="edit-cut-symbolic")
        clip_label = Gtk.Label(label="Вырезать фрагмент", xalign=0, hexpand=True)
        self.clip_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.clip_switch.connect("notify::active", self._on_clip_toggle)
        for w in (clip_icon, clip_label, self.clip_switch):
            clip_row.append(w)
        self.options.append(clip_row)

        self.clip_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        cbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.start_lbl, self.end_lbl = Gtk.Label(xalign=0), Gtk.Label(xalign=0)
        self.start_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.end_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        for sc in (self.start_scale, self.end_scale):
            sc.set_draw_value(False)
            sc.connect("value-changed", self._on_clip_scale)
        for w in (self.start_lbl, self.start_scale, self.end_lbl, self.end_scale):
            cbox.append(w)
        self.clip_rev.set_child(cbox)
        self.options.append(self.clip_rev)


        self.dl_btn = Gtk.Button(label="Скачать", halign=Gtk.Align.CENTER)
        self.dl_btn.add_css_class("suggested-action")
        self.dl_btn.add_css_class("k-primary")
        self.dl_btn.connect("clicked", lambda *_: self.start_download())
        self.options.append(self.dl_btn)
        col.append(self.options)
        self._on_format(self.fmt.value)
        return scroll

    # ---------- страницы «Загрузки» и «История» ----------
    def _list_page(self, placeholder_title, placeholder_icon):
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=680, margin_top=20, margin_bottom=20,
                          margin_start=16, margin_end=16)
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, valign=Gtk.Align.START)
        lb.add_css_class("boxed-list")
        lb.set_placeholder(Adw.StatusPage(title=placeholder_title, icon_name=placeholder_icon))
        clamp.set_child(lb)
        scroll.set_child(clamp)
        return scroll, lb

    def _build_downloads_page(self):
        page, self.dl_list = self._list_page("Пока ничего не качается", "folder-download-symbolic")
        return page

    def _build_history_page(self):
        page, self.hist_list = self._list_page("История пуста", "document-open-recent-symbolic")
        return page

    def refresh_history(self):
        while (row := self.hist_list.get_first_child()) is not None:
            self.hist_list.remove(row)
        for idx, e in enumerate(history.load()):
            row = Adw.ActionRow(title=e["title"], subtitle=f'{e["platform"]} · {e["format"].upper()} · {e["date"]}',
                                use_markup=False, title_lines=1, subtitle_lines=1)
            play = Gtk.Button(icon_name="media-playback-start-symbolic", valign=Gtk.Align.CENTER,
                              tooltip_text="Открыть файл")
            fold = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER,
                              tooltip_text="Показать в папке")
            rm = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Убрать из истории")
            for b in (play, fold, rm):
                b.add_css_class("flat")
                b.add_css_class("circular")
            play.connect("clicked", lambda _b, p=e["path"]: self.open_file(p))
            fold.connect("clicked", lambda _b, p=e["path"]: self.reveal(p))
            rm.connect("clicked", lambda _b, i=idx: (history.remove(i), self.refresh_history()))
            for b in (play, fold, rm):
                row.add_suffix(b)
            self.hist_list.append(row)
        return False

    # ---------- логика ----------
    def toast(self, text):
        self.toasts.add_toast(Adw.Toast.new(text))

    def set_url(self, url):
        self.entry.set_text(url)
        self.stack.set_visible_child_name("new")

    def paste_from_clipboard(self):
        cb = self.get_display().get_clipboard()
        cb.read_text_async(None, self._paste_done)

    def _paste_done(self, cb, res):
        try:
            url = urldetect.extract(cb.read_text_finish(res))
        except GLib.Error:
            return
        if url:
            self.entry.set_text(url)
            self.analyze()
        else:
            self.toast("В буфере обмена нет ссылки")

    def _on_drop(self, _t, value, _x, _y):
        url = urldetect.extract(value if isinstance(value, str) else "")
        if url:
            self.set_url(url)
            self.analyze()
            return True
        return False

    def _on_active(self, *_):
        """При возвращении в окно предлагаем вставить ссылку из буфера (работает и в Wayland)."""
        if not (self.is_active() and self.cfg.get("watch_clipboard")):
            return
        self.get_display().get_clipboard().read_text_async(None, self._clip_checked)

    def _clip_checked(self, cb, res):
        try:
            url = urldetect.extract(cb.read_text_finish(res))
        except GLib.Error:
            return
        if not url or url == self._last_clip or url == self.entry.get_text().strip():
            return
        self._last_clip = url
        t = Adw.Toast.new("Ссылка в буфере обмена")
        t.set_button_label("Вставить")
        t.connect("button-clicked", lambda *_: (self.entry.set_text(url), self.analyze()))
        self.toasts.add_toast(t)

    def analyze(self):
        url = urldetect.extract(self.entry.get_text())
        if not url:
            self.toast("Введите ссылку, начинающуюся с http:// или https://")
            return
        self.analyze_btn.set_sensitive(False)
        self.analyze_btn.set_label("Анализ…")

        def work():
            try:
                meta = ytdlp.fetch_metadata(url)
                data = self._fetch_thumb(meta.thumbnail)
                GLib.idle_add(self._analyzed, meta, data, None)
            except Exception as e:  # noqa: BLE001
                GLib.idle_add(self._analyzed, None, None, str(e))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _fetch_thumb(url):
        if not url:
            return None
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            return urlopen(req, timeout=10).read(3_000_000)
        except Exception:  # noqa: BLE001
            return None

    def _analyzed(self, meta, thumb_bytes, error):
        self.analyze_btn.set_sensitive(True)
        self.analyze_btn.set_label("Анализировать")
        if error:
            self.toast(error.splitlines()[0][:200])
            return False
        self.meta = meta
        self.p_title.set_label(meta.title)
        self.p_badge.set_label(meta.platform.value if meta.platform is not Platform.UNKNOWN
                               else host_of(meta.source_url))
        bits = [fmt_time(meta.duration) if meta.duration else "", meta.uploader]
        self.p_meta.set_label(" · ".join(b for b in bits if b))
        self.thumb.set_paintable(None)
        if thumb_bytes:
            try:
                self.thumb.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(thumb_bytes)))
            except GLib.Error:
                pass                                   # например, WebP без загрузчика
        dur = max(meta.duration, 1)
        for sc in (self.start_scale, self.end_scale):
            sc.set_range(0, dur)
        self.start_scale.set_value(0)
        self.end_scale.set_value(dur)
        self.clip_switch.set_sensitive(meta.duration > 0)
        self._on_clip_scale()
        self.preview.set_visible(True)
        self.options.set_visible(True)
        return False

    def _on_format(self, value):
        self.res_box.set_visible(value != "mp3")

    def _on_size_mode(self, value):
        self.size_spin.set_visible(bool(value))
        self.size_unit.set_visible(bool(value))

    def _on_clip_toggle(self, *_):
        self.clip_rev.set_reveal_child(self.clip_switch.get_active())

    def _on_clip_scale(self, *_):
        s, e = self.start_scale.get_value(), self.end_scale.get_value()
        if s >= e:
            if self.start_scale.has_focus():
                self.end_scale.set_value(min(s + 1, self.end_scale.get_adjustment().get_upper()))
            else:
                self.start_scale.set_value(max(e - 1, 0))
            return
        self.start_lbl.set_label(f"Начало: {fmt_time(s)}")
        self.end_lbl.set_label(f"Конец: {fmt_time(e)}  (длина {fmt_time(e - s)})")

    def _update_folder_label(self):
        self.folder_lbl.set_label(self.cfg["save_dir"])

    def _choose_folder(self, *_):
        dialog = Gtk.FileDialog(title="Папка для загрузок")
        dialog.set_initial_folder(Gio.File.new_for_path(self.cfg["save_dir"]))

        def done(d, res):
            try:
                folder = d.select_folder_finish(res)
            except GLib.Error:
                return
            self.cfg["save_dir"] = folder.get_path()
            settings.save(self.cfg)
            self._update_folder_label()

        dialog.select_folder(self, None, done)

    def start_download(self):
        if not self.meta:
            return
        clip = None
        if self.clip_switch.get_active():
            clip = (self.start_scale.get_value(), self.end_scale.get_value())
            if clip[1] - clip[0] < 1:
                self.toast("Фрагмент слишком короткий")
                return
        fmt, res = self.fmt.value, self.res.value
        target = int(self.size_spin.get_value()) if self.size.value else 0
        self.cfg.update(format=fmt, resolution=res)
        settings.save(self.cfg)
        item = DownloadItem(self.meta, fmt, res, target, clip, self.cfg["save_dir"])
        item.listeners.append(self._item_changed)
        self.manager.add(item)
        self.dl_list.prepend(DownloadRow(item, self))
        self.stack.set_visible_child_name("downloads")

    def _item_changed(self, item):
        if item.status is Status.DONE:
            self.refresh_history()
            n = Gio.Notification.new("Загрузка завершена")
            n.set_body(item.meta.title)
            self.get_application().send_notification(None, n)
        return False

    # ---------- файлы ----------
    def open_file(self, path):
        if os.path.exists(path):
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self, None, None, None)
        else:
            self.toast("Файл не найден")

    def reveal(self, path):
        if os.path.exists(path):
            Gtk.FileLauncher.new(Gio.File.new_for_path(path)).open_containing_folder(self, None, None, None)
        else:
            self.toast("Файл не найден")

    # ---------- прочее ----------
    def _clear_history(self, *_):
        history.clear()
        self.refresh_history()

    def _about(self, *_):
        kw = dict(application_name=APP_NAME, application_icon=APP_ID, version=VERSION,
                  developer_name="Качалка", comments="Загрузчик видео на базе yt-dlp и ffmpeg",
                  license_type=Gtk.License.MIT_X11)
        if hasattr(Adw, "AboutDialog"):
            Adw.AboutDialog(**kw).present(self)
        else:
            Adw.AboutWindow(transient_for=self, **kw).present()

    def _on_close(self, *_):
        if self._force_close or self.manager.active_count() == 0:
            return False
        dlg = Adw.MessageDialog(transient_for=self, heading="Загрузки ещё идут",
                                body="Если закрыть окно, незавершённые загрузки будут отменены.")
        dlg.add_response("stay", "Остаться")
        dlg.add_response("quit", "Закрыть и отменить")
        dlg.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("stay")

        def answered(_d, response):
            if response == "quit":
                self.manager.cancel_all()
                self._force_close = True
                self.close()

        dlg.connect("response", answered)
        dlg.present()
        return True


class KachalkaApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_path(os.path.join(os.path.dirname(__file__), "style.css"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.props.active_window or KachalkaWindow(self)
        win.present()


def main(argv):
    return KachalkaApp().run(argv)
