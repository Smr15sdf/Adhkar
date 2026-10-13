# -*- coding: utf-8 -*-
"""
تطبيق الأذكار لسطح مكتب ويندوز (PySide6)
- واجهة إعدادات عربية RTL بخط ثمانية، مع التحكم بحجم خط التطبيق وحجم خط الإشعار بشكل منفصل
- يعمل في الخلفية (System Tray)
- إشعار كبسولة بنمط الزجاج (Frosted Glass) مثل iOS، بحواف دائرية ناعمة
"""

import copy
import ctypes
import json
import os
import random
import sys
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPointF,
    QPropertyAnimation, QRect, QRectF, QRunnable, QSequentialAnimationGroup, Qt, QThreadPool,
    QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontDatabase, QFontMetrics, QGuiApplication,
    QIcon, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QPushButton, QRadioButton, QScrollArea, QSpinBox,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

import prayer_times as pt

APP_NAME = "Adhkar"
AUTOSTART_VALUE = "AdhkarApp"
DURATION_RANGE = (2, 120)    # مدة بقاء الإشعار بالثواني

UI_FONT_RANGE = (9, 26)
NOTIF_FONT_RANGE = (10, 48)

# أذكار قصيرة ثابتة في الصحيحين وغيرهما (مع التخريج)
SUGGESTED_ADHKAR = [
    "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ",                      # البخاري 6406 / مسلم 2694
    "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ",                                        # البخاري 6409 / مسلم 2704
    "سُبْحَانَ اللَّهِ، وَالْحَمْدُ لِلَّهِ، وَلَا إِلَهَ إِلَّا اللَّهُ، وَاللَّهُ أَكْبَرُ",  # مسلم 2137
    "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ",                            # مسلم 408
    "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ رَسُولًا",            # أبو داود 1529 / مسلم 1884
    "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ",             # مسلم 484
    "أَسْتَغْفِرُ اللَّهَ وَأَتُوبُ إِلَيْهِ",                                          # البخاري 6307
    "لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ",  # البخاري 3293 / مسلم 2691
    "حَسْبِيَ اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ",  # التوبة: 129
]

DEFAULT_DATA = {
    "adhkar": list(SUGGESTED_ADHKAR),
    "interval_minutes": 10,
    "autostart": False,
    "ui_font_size": 11,
    "notif_font_size": 16,
    "display_seconds": 7,
    "click_to_dismiss": True,
    "prayer": copy.deepcopy(pt.DEFAULT_PRAYER_CONFIG),
}


# ----------------------------------------------------------------------------
# مسارات وأدوات مساعدة
# ----------------------------------------------------------------------------
def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def data_dir() -> Path:
    override = os.environ.get("ADHKAR_DATA_DIR")   # للاختبار اليدوي المعزول
    if override:
        folder = Path(override)
    else:
        base = os.environ.get("APPDATA") or str(Path.home())
        folder = Path(base) / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def data_file() -> Path:
    return data_dir() / "data.json"


def prayer_state_file() -> Path:
    return data_dir() / "prayer_state.json"


def _clamp(value, lo, hi, default):
    try:
        return max(lo, min(hi, int(value)))
    except Exception:
        return default


def load_data() -> dict:
    path = data_file()
    data = copy.deepcopy(DEFAULT_DATA)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw.get("adhkar"), list):
                data["adhkar"] = [str(x).strip() for x in raw["adhkar"] if str(x).strip()]
            data["interval_minutes"] = _clamp(raw.get("interval_minutes"), 1, 1440,
                                              DEFAULT_DATA["interval_minutes"])
            data["autostart"] = bool(raw.get("autostart", False))
            data["ui_font_size"] = _clamp(raw.get("ui_font_size"), *UI_FONT_RANGE,
                                          DEFAULT_DATA["ui_font_size"])
            data["notif_font_size"] = _clamp(raw.get("notif_font_size"), *NOTIF_FONT_RANGE,
                                             DEFAULT_DATA["notif_font_size"])
            data["display_seconds"] = _clamp(raw.get("display_seconds"), *DURATION_RANGE,
                                             DEFAULT_DATA["display_seconds"])
            data["click_to_dismiss"] = bool(raw.get("click_to_dismiss", True))
            data["prayer"] = pt.sanitize_config(raw.get("prayer"))
        except Exception:
            pass
    else:
        save_data(data)
    return data


def save_data(data: dict) -> None:
    path = data_file()
    if "prayer" not in data:   # لا نفقد إعدادات الصلاة إن لم يمرّرها المستدعي
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old, dict) and "prayer" in old:
                data = dict(data, prayer=old["prayer"])
        except Exception:
            pass
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_fonts() -> str:
    """يحمّل خطوط ثمانية من مجلد fonts ويرجع اسم العائلة المناسبة."""
    families = []
    fonts_dir = resource_path("fonts")
    if fonts_dir.is_dir():
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in (".ttf", ".otf"):
                fid = QFontDatabase.addApplicationFont(str(f))
                if fid != -1:
                    for fam in QFontDatabase.applicationFontFamilies(fid):
                        if fam not in families:
                            families.append(fam)
    for fam in families:
        if "sans" in fam.lower():
            return fam
    for fam in families:
        if "thmanyah" in fam.lower() or "ثمانية" in fam:
            return fam
    if families:
        return families[0]
    return "Segoe UI"


def read_text_file(path) -> str:
    """يقرأ ملف txt بأكثر من ترميز (UTF-8 أو UTF-16 أو ويندوز العربي)."""
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "cp1256"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#1f9d6b"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 60, 60)
    p.setPen(QColor("white"))
    f = QFont()
    f.setPixelSize(38)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "ذ")
    p.end()
    return QIcon(pm)


def set_autostart(enabled: bool) -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --background'
            else:
                pyw = sys.executable.replace("python.exe", "pythonw.exe")
                cmd = f'"{pyw}" "{Path(__file__).resolve()}" --background'
            winreg.SetValueEx(key, AUTOSTART_VALUE, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_VALUE)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def make_no_activate(hwnd: int) -> None:
    """يمنع النافذة من سحب التركيز (WS_EX_NOACTIVATE)."""
    if sys.platform != "win32":
        return
    try:
        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
        user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE,
                              style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except Exception:
        pass


def blur_pixmap(pm: QPixmap) -> QPixmap:
    """تمويه ناعم: تصغير متكرر ثم تكبير (سريع وبدون حواف مشوّهة)."""
    if pm.isNull():
        return pm
    dpr = pm.devicePixelRatio()
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    sizes = [(w, h)]
    small = img
    for _ in range(5):
        nw, nh = max(1, small.width() // 2), max(1, small.height() // 2)
        small = small.scaled(nw, nh, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        sizes.append((nw, nh))
    for (tw, th) in reversed(sizes[:-1]):
        small = small.scaled(tw, th, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    out = QPixmap.fromImage(small)
    out.setDevicePixelRatio(dpr)
    return out


# ----------------------------------------------------------------------------
# نافذة الكبسولة العائمة (زجاج iOS)
# ----------------------------------------------------------------------------
class CapsuleNotification(QWidget):
    MARGIN = 24      # مساحة الظل حول الكبسولة
    PAD_X = 40
    PAD_Y = 20

    def __init__(self, font_family: str, font_size: int, duration: int = 7,
                 click_dismiss: bool = True):
        super().__init__(None)
        self._base_flags = (
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(self._base_flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setLayoutDirection(Qt.RightToLeft)

        self._family = font_family
        self._font = QFont(font_family, font_size)
        self._size = font_size
        self._text = ""
        self._radius = 30.0
        self._backdrop = None
        self._backdrop_top = 0
        self._native_done = False
        self._seq = None
        self._duration = duration
        self._click_dismiss = click_dismiss
        self._dismissing = False
        self._applied_click = True   # الحالة التي أُنشئت بها النافذة (تقبل الفأرة)
        self._y_hide = 0

        # --- مواقيت الصلاة داخل الكبسولة ---
        self._mode_cfg = "none"      # الوضع المطلوب من الإعدادات: none | hover | stack | side
        self._countdown_fmt = "seconds"   # صيغة الوقت المتبقي: seconds | minutes
        self._eff_mode = "none"      # الوضع الفعلي للإشعار الحالي
        self._info_fn = None         # دالة ترجع pt.Status
        self._info = None            # آخر نصوص جاهزة للعرض (pt.status_texts)
        self._kind = "dhikr"         # dhikr | prayer
        self._mix = 0.0              # 0 = الذكر، 1 = معلومات الصلاة (وضع التمرير)
        self._hover_paused = False
        self._layout = {"mode": "none", "dhikr": QRect()}
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(500)
        self._info_timer.timeout.connect(self._refresh_info)
        self._mix_anim = QVariantAnimation(self)
        self._mix_anim.setDuration(220)
        self._mix_anim.valueChanged.connect(self._on_mix)

    def set_font_size(self, size: int):
        self._size = size
        self._font = QFont(self._family, size)

    def set_duration(self, seconds: int):
        self._duration = max(1, int(seconds))

    def set_click_dismiss(self, enabled: bool):
        self._click_dismiss = bool(enabled)

    # --- معلومات الصلاة ---
    def set_prayer_view(self, mode: str, info_fn, countdown_format: str = "seconds"):
        """mode: none | hover | stack | side. info_fn() يرجع pt.Status (أو None)."""
        self._mode_cfg = mode if mode in (pt.MODE_HOVER, pt.MODE_STACK, pt.MODE_SIDE) else "none"
        self._info_fn = info_fn
        self._countdown_fmt = countdown_format if countdown_format in pt.COUNTDOWN_FORMATS else "seconds"

    def is_prayer_showing(self) -> bool:
        return self.isVisible() and self._kind == "prayer" and not self._dismissing

    def _compute_info(self):
        if self._mode_cfg == "none" or self._info_fn is None:
            return None
        try:
            return pt.status_texts(self._info_fn(), self._countdown_fmt)
        except Exception:
            return None

    def _effective_mode(self, kind: str, info) -> str:
        if kind != "dhikr" or info is None:
            return "none"
        if self._mode_cfg == pt.MODE_HOVER:
            return "hover"
        if not info.get("countdown"):
            return "none"   # لا نعرض «غير متاح» داخل وضعي العرض الدائم
        return self._mode_cfg

    def _refresh_info(self):
        info = self._compute_info()
        if info != self._info:
            self._info = info
            self.update()

    def _animate_mix(self, target: float):
        self._mix_anim.stop()
        self._mix_anim.setStartValue(float(self._mix))
        self._mix_anim.setEndValue(float(target))
        self._mix_anim.start()

    def _on_mix(self, value):
        self._mix = float(value)
        self.update()

    def _samples(self) -> list:
        """أطول صيغ العدّاد المحتملة (للقياس فقط) حسب الصيغة المختارة."""
        return [pt.LESS_THAN_MINUTE, "8:88"] if self._countdown_fmt == "minutes" else ["8:88:88"]

    def _worst_lines(self, include_reasons: bool) -> list:
        """أطول الصيغ المحتملة (للقياس فقط) حتى لا يتغير حجم الكبسولة مع تغيّر الأرقام."""
        names = [pt.PRAYER_AR[x] for x in pt.PRAYERS]
        lines = []
        for cd in self._samples():
            lines += [f"{n} بعد {cd}" for n in names] + [f"إقامة {n} بعد {cd}" for n in names]
        if include_reasons:
            lines += list(pt.REASON_TEXT.values())
        return lines

    # --- تمرير الماوس (وضع «الذكر فقط») ---
    def enterEvent(self, e):
        super().enterEvent(e)
        if self._eff_mode == "hover" and self._kind == "dhikr" and not self._dismissing:
            self._animate_mix(1.0)
            if self._seq is not None and self._seq.state() == QAbstractAnimation.Running:
                self._seq.pause()          # لا يختفي الإشعار أثناء قراءة الصلاة القادمة
                self._hover_paused = True

    def leaveEvent(self, e):
        super().leaveEvent(e)
        if self._eff_mode == "hover":
            self._animate_mix(0.0)
        if self._hover_paused:
            self._hover_paused = False
            if self._seq is not None and self._seq.state() == QAbstractAnimation.Paused:
                self._seq.resume()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._info_timer.stop()

    # --- الإغلاق بالنقر ---
    def mousePressEvent(self, e):
        if self._click_dismiss and e.button() == Qt.LeftButton:
            self.dismiss()
            e.accept()
        else:
            super().mousePressEvent(e)

    def dismiss(self):
        """يُخفي الإشعار فوراً (حركة صعود سريعة) عند النقر عليه."""
        if not self.isVisible() or self._dismissing:
            return
        self._dismissing = True
        self._hover_paused = False
        if self._seq is not None:
            self._seq.stop()
        move = QPropertyAnimation(self, b"pos", self)
        move.setDuration(320)
        move.setStartValue(self.pos())
        move.setEndValue(QPoint(self.x(), int(self._y_hide)))
        move.setEasingCurve(QEasingCurve(QEasingCurve.InCubic))
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(320)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        grp = QParallelAnimationGroup(self)
        grp.addAnimation(move)
        grp.addAnimation(fade)
        grp.finished.connect(self.hide)
        self._seq = grp
        grp.start()

    # --- الرسم ---
    def _capsule_rect(self) -> QRectF:
        m = self.MARGIN
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setLayoutDirection(Qt.RightToLeft)

        cap = self._capsule_rect()
        r = self._radius
        cap_path = QPainterPath()
        cap_path.addRoundedRect(cap, r, r)

        # 1) ظل ناعم خارج الكبسولة فقط
        outer = QPainterPath()
        outer.addRect(QRectF(self.rect()))
        outer.addPath(cap_path)
        outer.setFillRule(Qt.OddEvenFill)
        p.save()
        p.setClipPath(outer)
        p.setPen(Qt.NoPen)
        layers = 12
        for i in range(layers):
            g = self.MARGIN * (layers - i) / layers
            sp = QPainterPath()
            rr = cap.adjusted(-g, -g, g, g).translated(0, 4)
            sp.addRoundedRect(rr, r + g, r + g)
            p.setBrush(QColor(0, 0, 0, 3))
            p.drawPath(sp)
        p.restore()

        # 2) الزجاج: خلفية ممولهة + طبقة داكنة
        p.save()
        p.setClipPath(cap_path)
        if self._backdrop is not None and not self._backdrop.isNull():
            p.drawPixmap(int(cap.x()), int(self._backdrop_top - self.y()), self._backdrop)
            p.fillPath(cap_path, QColor(22, 22, 26, 135))
        else:
            p.fillPath(cap_path, QColor(26, 26, 30, 225))

        # لمعة علوية خفيفة
        shine = QLinearGradient(QPointF(0, cap.top()), QPointF(0, cap.bottom()))
        shine.setColorAt(0.0, QColor(255, 255, 255, 40))
        shine.setColorAt(0.5, QColor(255, 255, 255, 8))
        shine.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(cap_path, QBrush(shine))
        p.restore()

        # 3) حد زجاجي رفيع متدرج
        rim = QLinearGradient(QPointF(0, cap.top()), QPointF(0, cap.bottom()))
        rr, rg, rb = (61, 220, 151) if self._kind == "prayer" else (255, 255, 255)
        rim.setColorAt(0.0, QColor(rr, rg, rb, 130 if self._kind == "prayer" else 110))
        rim.setColorAt(1.0, QColor(rr, rg, rb, 45 if self._kind == "prayer" else 30))
        pen = QPen(QBrush(rim), 1.2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(cap_path)

        # 4) المحتوى (الذكر + معلومات الصلاة حسب الوضع)
        self._paint_content(p, cap)

    def _paint_content(self, p, cap):
        L = self._layout
        mode = L.get("mode", "none")
        ox, oy = int(cap.x()), int(cap.y())
        flags = Qt.AlignCenter | Qt.TextWordWrap
        white = QColor(255, 255, 255, 245)
        info = self._info

        def R(rect):
            return rect.translated(ox, oy)

        p.setFont(self._font)
        if mode == "hover":
            mix = self._mix
            p.setPen(white)
            p.setOpacity(max(0.0, 1.0 - mix))
            p.drawText(R(L["dhikr"]), flags, self._text)
            if info:
                p.setOpacity(mix)
                p.drawText(R(L["info"]), flags, info["line"])
            p.setOpacity(1.0)
            return
        p.setPen(white)
        p.drawText(R(L["dhikr"]), flags, self._text)
        if mode == "stack" and info:
            p.setFont(L["info_font"])
            p.setPen(QColor(255, 255, 255, 190))
            p.drawText(R(L["info"]), Qt.AlignCenter, info["line"])
        elif mode == "side":
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            x = ox + L["divider_x"]
            p.drawLine(x, int(cap.y() + 14), x, int(cap.bottom() - 14))
            if info:
                r = R(L["info"])
                total = L["name_h"] + 2 + L["cd_h"]
                top = r.y() + (r.height() - total) // 2
                p.setFont(L["name_font"])
                p.setPen(QColor(255, 255, 255, 170))
                p.drawText(QRect(r.x(), top, r.width(), L["name_h"]), Qt.AlignCenter, info["label"])
                p.setFont(L["cd_font"])
                p.setPen(white)
                p.drawText(QRect(r.x(), top + L["name_h"] + 2, r.width(), L["cd_h"]),
                           Qt.AlignCenter, info["countdown"])

    def moveEvent(self, e):
        super().moveEvent(e)
        self.update()  # لتتوافق الخلفية الزجاجية مع موضع النافذة أثناء الحركة

    def showEvent(self, e):
        super().showEvent(e)
        if not self._native_done:
            self._native_done = True
            make_no_activate(int(self.winId()))

    # --- العرض والحركة ---
    def _measure(self, text: str, mode: str, geo) -> tuple:
        """يحسب حجم الكبسولة وأماكن المحتوى حسب الوضع الفعلي. يرجع (العرض، الارتفاع)."""
        pad_x, pad_y = self.PAD_X, self.PAD_Y
        fm = QFontMetrics(self._font)
        max_text_w = min(int(600 * max(1.0, self._size / 16)), int(geo.width() * 0.8) - 2 * pad_x)
        one_line = fm.horizontalAdvance(text)
        flags = Qt.AlignCenter | Qt.TextWordWrap
        layout = {"mode": mode}

        if mode == "side":
            name_font = QFont(self._family, max(8, round(self._size * 0.6)))
            cd_font = QFont(self._family, max(10, round(self._size * 0.95)))
            nfm, cfm = QFontMetrics(name_font), QFontMetrics(cd_font)
            names = [pt.PRAYER_AR[x] for x in pt.PRAYERS]
            labels = names + [f"إقامة {n}" for n in names]
            info_w = max(max(nfm.horizontalAdvance(x) for x in labels),
                         max(cfm.horizontalAdvance(x) for x in self._samples())) + 10
            info_h = nfm.height() + 2 + cfm.height()
            gap = 22
            avail = max(200, max_text_w - info_w - 2 * gap)
            text_w = min(one_line + 8, avail)
            bound = fm.boundingRect(QRect(0, 0, text_w, 10000), flags, text)
            cap_w = max(2 * pad_x + text_w + info_w + 2 * gap + 1, 380)
            cap_h = max(max(bound.height(), info_h) + 2 * pad_y, 64)
            inner_h = cap_h - 2 * pad_y
            region_w = cap_w - 2 * pad_x - info_w - 2 * gap - 1
            # RTL: الذكر على اليمين، ومعلومات الصلاة على اليسار يفصلهما خط رفيع
            layout["dhikr"] = QRect(cap_w - pad_x - region_w, pad_y, region_w, inner_h)
            layout["info"] = QRect(pad_x, pad_y, info_w, inner_h)
            layout["divider_x"] = pad_x + info_w + gap
            layout["name_font"], layout["cd_font"] = name_font, cd_font
            layout["name_h"], layout["cd_h"] = nfm.height(), cfm.height()
        elif mode in ("stack", "hover"):
            info_font = QFont(self._family, max(9, round(self._size * 0.66))) if mode == "stack" \
                else self._font
            ifm = QFontMetrics(info_font)
            info_w = max(ifm.horizontalAdvance(x) for x in self._worst_lines(mode == "hover"))
            text_w = min(max(one_line + 8, info_w + 8), max_text_w)
            bound = fm.boundingRect(QRect(0, 0, text_w, 10000), flags, text)
            cap_w = max(text_w + 2 * pad_x, 260)
            inner_w = cap_w - 2 * pad_x
            if mode == "stack":
                gap = 6
                content_h = bound.height() + gap + ifm.height()
                cap_h = max(content_h + 2 * pad_y, 64)
                top = (cap_h - content_h) // 2
                layout["dhikr"] = QRect(pad_x, top, inner_w, bound.height())
                layout["info"] = QRect(pad_x, top + bound.height() + gap, inner_w, ifm.height())
                layout["info_font"] = info_font
            else:
                cap_h = max(max(bound.height(), ifm.height()) + 2 * pad_y, 64)
                full = QRect(pad_x, pad_y, inner_w, cap_h - 2 * pad_y)
                layout["dhikr"], layout["info"] = full, full
        else:
            text_w = min(one_line + 8, max_text_w)
            bound = fm.boundingRect(QRect(0, 0, text_w, 10000), flags, text)
            cap_w = max(text_w + 2 * pad_x, 260)
            cap_h = max(bound.height() + 2 * pad_y, 64)
            layout["dhikr"] = QRect(pad_x, pad_y, cap_w - 2 * pad_x, cap_h - 2 * pad_y)

        self._layout = layout
        self._radius = cap_h / 2 if cap_h <= 100 else 36.0
        return cap_w, cap_h

    def show_message(self, text: str, kind: str = "dhikr") -> bool:
        """يعرض الكبسولة. kind: dhikr (ذكر + معلومات الصلاة حسب الوضع) | prayer (إشعار صلاة فقط)."""
        if self._seq is not None:
            self._seq.stop()
        self._info_timer.stop()
        self._mix_anim.stop()
        self.hide()
        self._text = text
        self._kind = kind
        self._dismissing = False
        self._hover_paused = False
        self._mix = 0.0

        # الوضع الفعلي: قد يختلف عن المطلوب إذا لم تتوفر المواقيت
        info = self._compute_info() if kind == "dhikr" else None
        mode = self._effective_mode(kind, info)
        self._info = info
        self._eff_mode = mode

        # تقبل الكبسولة الفأرة عند تفعيل النقر أو وضع «التمرير»، وإلا تمرّر النقرات (Click-through حقيقي)
        need_input = self._click_dismiss or mode == "hover"
        if self._applied_click != need_input:
            flags = self._base_flags
            if not need_input:
                flags |= Qt.WindowTransparentForInput
            self.setWindowFlags(flags)
            self._applied_click = need_input
            self._native_done = False   # أُعيد إنشاء النافذة، نعيد تطبيق NOACTIVATE
        if self._click_dismiss:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        m = self.MARGIN

        cap_w, cap_h = self._measure(text, mode, geo)

        win_w, win_h = int(cap_w + 2 * m), int(cap_h + 2 * m)
        self.setFixedSize(win_w, win_h)

        x_cap = geo.x() + (geo.width() - cap_w) // 2
        y_cap_show = geo.y() + 18
        x_win = int(x_cap - m)
        y_show = int(y_cap_show - m)
        y_hide = int(geo.y() - win_h - 12)

        # التقاط الخلفية خلف الكبسولة (قبل إظهارها) وتمويهها
        self._backdrop = None
        try:
            sg = screen.geometry()
            gx = int(x_cap - sg.x())
            gy = int(geo.y() - sg.y())
            gw = int(cap_w)
            gh = int((y_cap_show - geo.y()) + cap_h)
            pm = screen.grabWindow(0, gx, gy, gw, gh)
            if not pm.isNull():
                self._backdrop = blur_pixmap(pm)
                self._backdrop_top = geo.y()
        except Exception:
            self._backdrop = None

        self._y_hide = y_hide
        self.move(x_win, y_hide)
        self.setWindowOpacity(0.0)
        self.show()

        def pos_anim(a, b, ms, curve):
            an = QPropertyAnimation(self, b"pos", self)
            an.setDuration(ms)
            an.setStartValue(QPoint(x_win, int(a)))
            an.setEndValue(QPoint(x_win, int(b)))
            an.setEasingCurve(curve)
            return an

        def fade_anim(a, b, ms):
            an = QPropertyAnimation(self, b"windowOpacity", self)
            an.setDuration(ms)
            an.setStartValue(a)
            an.setEndValue(b)
            return an

        slide_in = QParallelAnimationGroup(self)
        slide_in.addAnimation(pos_anim(y_hide, y_show, 650, QEasingCurve(QEasingCurve.OutBack)))
        slide_in.addAnimation(fade_anim(0.0, 1.0, 400))

        slide_out = QParallelAnimationGroup(self)
        slide_out.addAnimation(pos_anim(y_show, y_hide, 500, QEasingCurve(QEasingCurve.InCubic)))
        slide_out.addAnimation(fade_anim(1.0, 0.0, 500))

        self._seq = QSequentialAnimationGroup(self)
        self._seq.addAnimation(slide_in)
        self._seq.addPause(self._duration * 1000)
        self._seq.addAnimation(slide_out)
        self._seq.finished.connect(self.hide)
        self._seq.start()
        if mode != "none":
            self._info_timer.start()
        return True


# ----------------------------------------------------------------------------
# تنسيق الواجهة (يتغير حسب حجم الخط)
# ----------------------------------------------------------------------------
STYLE_TEMPLATE = """
QWidget { font-family: "@FAMILY@"; font-size: @BASE@pt; }
QMainWindow, QWidget#root, QScrollArea { background: #121214; border: none; }
QLabel { color: #e9e9ec; }
QLabel#title { font-size: @TITLE@pt; font-weight: bold; color: #ffffff; }
QLabel#subtitle { color: #8d8d96; font-size: @SMALL@pt; }
QLabel#section { font-size: @SECTION@pt; font-weight: bold; color: #ffffff; }
QLabel#status { color: #3ddc97; font-size: @SMALL@pt; }
QLabel#hint { color: #8d8d96; font-size: @SMALL@pt; }
QFrame#card { background: #1b1b1f; border: 1px solid #2a2a30; border-radius: 16px; }
QLineEdit, QSpinBox {
    background: #121214; color: #ffffff; border: 1px solid #33333a;
    border-radius: 12px; padding: 9px 12px;
    selection-background-color: #1f9d6b;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid #1f9d6b; }
QListWidget {
    background: #121214; color: #f2f2f2; border: 1px solid #33333a;
    border-radius: 12px; padding: 6px; outline: none;
}
QListWidget::item { padding: 10px 8px; border-radius: 8px; }
QListWidget::item:selected { background: #1f9d6b; color: white; }
QListWidget::item:hover:!selected { background: #26262c; }
QPushButton {
    background: #2a2a30; color: #ffffff; border: none; border-radius: 12px;
    padding: 10px 18px;
}
QPushButton:hover { background: #34343c; }
QPushButton#primary { background: #1f9d6b; font-weight: bold; }
QPushButton#primary:hover { background: #25b07a; }
QPushButton#danger { background: #3a2226; color: #ff8a8a; }
QPushButton#danger:hover { background: #4a2a2f; }
QPushButton#chip { padding: 8px 14px; background: #24242a; }
QPushButton#chip:hover { background: #1f9d6b; }
QCheckBox { color: #e9e9ec; spacing: 8px; }
QRadioButton { color: #e9e9ec; spacing: 8px; }
QDialog, QWidget#dlgroot { background: #121214; }
QComboBox {
    background: #121214; color: #ffffff; border: 1px solid #33333a;
    border-radius: 12px; padding: 7px 12px;
}
QComboBox:focus { border: 1px solid #1f9d6b; }
QComboBox QAbstractItemView {
    background: #1b1b1f; color: #ffffff; border: 1px solid #33333a;
    selection-background-color: #1f9d6b; outline: none;
}
QLabel#warn { color: #ffb86b; font-size: @SMALL@pt; }
QFrame#tabbar { background: #1b1b1f; border: 1px solid #2a2a30; border-radius: 20px; }
QPushButton#tab {
    background: transparent; color: #9a9aa4; border: none; border-radius: 15px;
    padding: 9px 24px; font-size: @TABS@pt; font-weight: bold;
}
QPushButton#tab:hover { color: #ffffff; background: #26262c; }
QPushButton#tab:checked { background: #1f9d6b; color: #ffffff; }
QFrame#ptime { background: #121214; border: 1px solid #2a2a30; border-radius: 14px; }
QFrame#ptime[active="true"] { background: #14382b; border: 1px solid #1f9d6b; }
QLabel#ptname { color: #8d8d96; font-size: @SMALL@pt; }
QLabel#pttime { color: #ffffff; font-size: @SECTION@pt; font-weight: bold; }
QFrame#ptime[active="true"] QLabel#ptname { color: #7fe3b8; }
QLabel#nextline { color: #ffffff; font-size: @SECTION@pt; font-weight: bold; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #3a3a42; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def build_style(family: str, base_pt: int) -> str:
    return (STYLE_TEMPLATE
            .replace("@FAMILY@", family)
            .replace("@BASE@", str(base_pt))
            .replace("@TITLE@", f"{base_pt * 2:.1f}")
            .replace("@SECTION@", f"{base_pt * 1.15:.1f}")
            .replace("@SMALL@", f"{base_pt * 0.9:.1f}")
            .replace("@TABS@", f"{base_pt * 1.25:.1f}"))


def card() -> tuple:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)
    return frame, lay


# ----------------------------------------------------------------------------
# خانات لا تتفاعل مع عجلة الماوس (العجلة تُمرّر الصفحة فقط ولا تغيّر القيمة)
# ----------------------------------------------------------------------------
class NoWheelSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)   # لا تأخذ التركيز بالعجلة

    def wheelEvent(self, event):
        event.ignore()   # يمرّ الحدث إلى الصفحة (QScrollArea) لتتمرر بدل تغيير الرقم


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


# ----------------------------------------------------------------------------
# مساعدات مواقيت الصلاة: الصوت + الخدمات الشبكية (في خيوط خلفية)
# ----------------------------------------------------------------------------
class SoundPlayer:
    """تشغيل غير حاجب لملف صوت اختاره المستخدم (ويندوز: WAV عبر winsound، وMP3/WMA عبر MCI)."""
    ALIAS = "adhkar_adhan"

    @staticmethod
    def _mci(cmd: str):
        buf = ctypes.create_unicode_buffer(256)
        rc = ctypes.windll.winmm.mciSendStringW(cmd, buf, 255, 0)
        return rc, buf.value

    def play(self, path: str):
        """يرجع (نجح؟، رسالة). لا يرفع استثناءات."""
        if sys.platform != "win32":
            return False, "تشغيل الصوت مدعوم على ويندوز فقط"
        p = Path(path) if path else None
        if p is None or not p.is_file():
            return False, "ملف الصوت غير موجود"
        ext = p.suffix.lower()
        try:
            self.stop()
            if ext == ".wav":
                import winsound
                winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC
                                   | winsound.SND_NODEFAULT)
                return True, ""
            if ext in (".mp3", ".wma"):
                rc, _ = self._mci(f'open "{p}" type mpegvideo alias {self.ALIAS}')
                if rc != 0:
                    return False, "تعذّر فتح ملف الصوت"
                rc, _ = self._mci(f"play {self.ALIAS}")
                if rc != 0:
                    self._mci(f"close {self.ALIAS}")
                    return False, "تعذّر تشغيل ملف الصوت"
                return True, ""
            return False, "صيغة غير مدعومة (استخدم WAV أو MP3 أو WMA)"
        except Exception as ex:
            return False, f"تعذّر تشغيل الصوت: {ex}"

    def stop(self):
        if sys.platform != "win32":
            return
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
            ctypes.windll.winmm.mciSendStringW(f"close {self.ALIAS}", None, 0, 0)
        except Exception:
            pass


class _WorkerSignals(QObject):
    done = Signal(object, str)      # (النتيجة، رسالة خطأ غير فارغة عند الاستثناء)


class _Worker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = _WorkerSignals()
        self.is_done = False
        self.setAutoDelete(False)   # نحتفظ بالكائن حتى تصل الإشارة

    def run(self):
        try:
            result = self.fn(*self.args)
            self.signals.done.emit(result, "")
        except Exception as ex:
            self.signals.done.emit(None, str(ex))
        finally:
            self.is_done = True


# مراجع قوية للعمّال الجارين: حتى لو أُغلقت النافذة أثناء البحث لا يُتلف الكائن قبل انتهاء الخيط
_ACTIVE_WORKERS: list = []


class GeoService(QObject):
    """تحديد الموقع والبحث عن المدن بدون تجميد الواجهة. الإشارات تصل دائماً في الخيط الرئيسي."""
    detected = Signal(object, str)   # (موقع أو None، رسالة)
    searched = Signal(object, str)   # (قائمة مدن، رسالة خطأ)
    resolved = Signal(object, str)   # ({name, tz, lat, lon} أو None، رسالة خطأ)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detecting = False
        self._search_id = 0

    def _launch(self, fn, args, slot):
        _ACTIVE_WORKERS[:] = [w for w in _ACTIVE_WORKERS if not w.is_done]
        w = _Worker(fn, *args)
        w.signals.done.connect(slot)   # slot دالة في QObject => تسليم مؤجَّل للخيط الرئيسي
        _ACTIVE_WORKERS.append(w)
        QThreadPool.globalInstance().start(w)

    def detect(self) -> bool:
        if self._detecting:
            return False
        self._detecting = True
        self._launch(pt.detect_location_precise, (), self._on_detect_done)   # ويندوز أولاً ثم IP تقريبي
        return True

    def _on_detect_done(self, result, err):
        self._detecting = False
        if err or not result:
            self.detected.emit(None, err or "تعذّر تحديد الموقع")
            return
        loc, msg = result
        self.detected.emit(loc, msg)

    def resolve(self, lat: float, lon: float):
        """يُكمل نقطة بالإحداثيات فقط: اسم المدينة والمنطقة الزمنية."""
        self._launch(lambda: dict(pt.resolve_point(lat, lon), lat=lat, lon=lon), (), self._on_resolve_done)

    def _on_resolve_done(self, result, err):
        self.resolved.emit(None if err else result, err)

    def search(self, query: str):
        q = (query or "").strip()
        if len(q) < 2:
            self.searched.emit([], "اكتب حرفين على الأقل للبحث")
            return
        self._search_id += 1
        sid = self._search_id
        self._launch(lambda: (sid, pt.search_cities(q)), (), self._on_search_done)

    def _on_search_done(self, result, err):
        if err or not result:
            self.searched.emit([], err or "حدث خطأ أثناء البحث")
            return
        sid, (cities, msg) = result
        if sid != self._search_id:
            return   # نتيجة بحث قديم
        self.searched.emit(cities, msg)


# ----------------------------------------------------------------------------
# تبويب مواقيت الصلاة والتنبيهات (داخل النافذة الرئيسية)
# ----------------------------------------------------------------------------
class PrayerContext:
    """ما يحتاجه التبويب من التطبيق (بدون ربطه بالصنف الرئيسي مباشرة)."""

    def __init__(self, cfg, on_apply, on_test, now_fn, sound):
        self.cfg, self.on_apply, self.on_test = cfg, on_apply, on_test
        self.now_fn, self.sound = now_fn, sound


class PrayerTab(QWidget):
    WIDE = 820   # عرض يبدأ منه تخطيط العمودين

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self._ctx = ctx
        self._cfg = pt.sanitize_config(ctx.cfg)          # حالة النموذج
        self._applied = copy.deepcopy(self._cfg)         # آخر إعدادات حُفظت وطُبّقت
        self._loading = True
        self._pending_estimate = None
        self._tf, self._cf = self._cfg["time_format"], self._cfg["countdown_format"]
        self._preview = pt.PrayerEngine(dict(self._cfg, enabled=True), None, ctx.now_fn)

        self.geo = GeoService(self)
        self.geo.detected.connect(self._on_detected)
        self.geo.searched.connect(self._on_searched)
        self.geo.resolved.connect(self._on_resolved)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)
        content = QWidget()
        content.setObjectName("root")
        scroll.setWidget(content)
        main = QVBoxLayout(content)
        main.setContentsMargins(0, 0, 0, 10)
        main.setSpacing(14)

        main.addWidget(self._build_strip())

        self.body = QBoxLayout(QBoxLayout.LeftToRight)
        self.body.setSpacing(14)
        main.addLayout(self.body, 1)
        col_a, col_b = QVBoxLayout(), QVBoxLayout()
        col_a.setSpacing(14)
        col_b.setSpacing(14)
        col_a.addWidget(self._build_general_card())
        col_a.addWidget(self._build_location_card())
        col_a.addStretch(1)
        col_b.addWidget(self._build_calc_card())
        col_b.addWidget(self._build_notify_card())
        col_b.addWidget(self._build_iqama_card())
        col_b.addStretch(1)
        self.body.addLayout(col_a, 1)
        self.body.addLayout(col_b, 1)

        bar = QWidget()
        bar.setObjectName("root")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 10, 0, 0)
        self.save_btn = QPushButton("حفظ إعدادات الصلاة")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.save_status = QLabel("")
        self.save_status.setObjectName("status")
        bl.addWidget(self.save_btn, 1)
        bl.addWidget(self.save_status)
        outer.addWidget(bar)

        self._populate(self._cfg)
        self._loading = False
        self._connect_form_signals()
        self._on_form_changed()

        # مؤقت واحد فقط (يعمل أثناء ظهور التبويب فقط) لتحديث العدّاد الحي
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._refresh_strip)

    # ---------- البناء ----------
    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    @staticmethod
    def _center_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    @staticmethod
    def _hint(text: str, name: str = "hint") -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName(name)
        lbl.setWordWrap(True)
        return lbl

    @staticmethod
    def _spin(lo: int, hi: int, suffix: str = "", width: int = 0) -> "NoWheelSpinBox":
        sp = NoWheelSpinBox()
        sp.setRange(lo, hi)
        if suffix:
            sp.setSuffix(suffix)
        sp.setAlignment(Qt.AlignCenter)
        sp.setButtonSymbols(QSpinBox.NoButtons)
        if width:
            sp.setMinimumWidth(width)
        return sp

    def _build_strip(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)
        top = QHBoxLayout()
        self.next_label = QLabel("")
        self.next_label.setObjectName("nextline")
        self.dirty_label = QLabel("")
        self.dirty_label.setObjectName("warn")
        top.addWidget(self.next_label)
        top.addStretch(1)
        top.addWidget(self.dirty_label)
        v.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.time_boxes = {}
        for name in pt.PRAYERS:
            box = QFrame()
            box.setObjectName("ptime")
            box.setProperty("active", False)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(8, 8, 8, 8)
            bl.setSpacing(2)
            n = self._center_label(pt.PRAYER_AR[name])
            n.setObjectName("ptname")
            t = self._center_label("--:--")
            t.setObjectName("pttime")
            bl.addWidget(n)
            bl.addWidget(t)
            row.addWidget(box, 1)
            self.time_boxes[name] = (box, t)
        v.addLayout(row)
        self.loc_line = self._hint("")
        v.addWidget(self.loc_line)
        return frame

    def _build_general_card(self):
        c, l = card()
        self.enabled_chk = QCheckBox("تفعيل مواقيت الصلاة والتنبيهات والإقامة")
        l.addWidget(self.enabled_chk)
        l.addWidget(self._section("طريقة العرض في الكبسولة"))
        self.mode_rbs = self._radio_group(l, (
            (pt.MODE_HOVER, "الذكر فقط (تظهر الصلاة القادمة والوقت المتبقي عند تمرير الماوس)"),
            (pt.MODE_STACK, "الذكر مع الوقت المتبقي للصلاة"),
            (pt.MODE_SIDE, "الذكر والوقت بجانب بعضهما"),
        ))
        l.addWidget(self._section("نظام الساعة"))
        self.tf_rbs = self._radio_group(l, (
            ("24", "24 ساعة (مثال: 15:29)"),
            ("12", "12 ساعة (مثال: 3:29 م)"),
        ))
        l.addWidget(self._section("صيغة الوقت المتبقي"))
        self.cd_rbs = self._radio_group(l, (
            ("seconds", "بالثواني (مثال: 2:20:31)"),
            ("minutes", "بالدقائق (مثال: 2:20)"),
        ))
        return c

    def _radio_group(self, layout, items) -> dict:
        """مجموعة أزرار راديو مستقلة (QButtonGroup صريح حتى لا تتداخل المجموعات في البطاقة نفسها)."""
        group = QButtonGroup(self)
        group.setExclusive(True)
        out = {}
        for key, text in items:
            rb = QRadioButton(text)
            group.addButton(rb)
            layout.addWidget(rb)
            out[key] = rb
        return out

    def _build_location_card(self):
        c, l = card()
        l.addWidget(self._section("الموقع"))
        self.auto_rb = QRadioButton("تلقائي (الأدق: خدمة الموقع في ويندوز)")
        l.addWidget(self.auto_rb)
        auto_row = QHBoxLayout()
        self.detect_btn = QPushButton("تحديث الموقع الآن")
        self.detect_btn.clicked.connect(self._start_detect)
        self.use_est_btn = QPushButton("استخدام التقدير التقريبي")
        self.use_est_btn.clicked.connect(self._use_estimate)
        self.use_est_btn.setVisible(False)
        auto_row.addWidget(self.detect_btn)
        auto_row.addWidget(self.use_est_btn)
        auto_row.addStretch(1)
        l.addLayout(auto_row)
        l.addWidget(self._hint(
            "يتطلب تفعيل «الموقع» في إعدادات ويندوز > الخصوصية والأمان. وإن لم تتوفر الخدمة "
            "يُعرض تقدير تقريبي من الإنترنت قد يكون في مدينة أخرى، فاختر مدينتك يدوياً."))

        self.manual_rb = QRadioButton("يدوي (مدينة أو إحداثيات)")
        l.addWidget(self.manual_rb)
        search_row = QHBoxLayout()
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("ابحث عن مدينتك… مثال: الخبر")
        self.city_input.returnPressed.connect(self._search)
        self.search_btn = QPushButton("بحث")
        self.search_btn.clicked.connect(self._search)
        search_row.addWidget(self.city_input, 1)
        search_row.addWidget(self.search_btn)
        l.addLayout(search_row)
        self.results = QListWidget()
        self.results.setMaximumHeight(130)
        self.results.itemClicked.connect(self._choose_city)
        l.addWidget(self.results)

        coord_row = QHBoxLayout()
        self.lat_spin = NoWheelDoubleSpinBox()
        self.lon_spin = NoWheelDoubleSpinBox()
        for sp, lo, hi in ((self.lat_spin, -90.0, 90.0), (self.lon_spin, -180.0, 180.0)):
            sp.setRange(lo, hi)
            sp.setDecimals(4)
            sp.setAlignment(Qt.AlignCenter)
            sp.setButtonSymbols(QSpinBox.NoButtons)
            sp.setMinimumWidth(110)
        self.coord_btn = QPushButton("اعتماد الإحداثيات")
        self.coord_btn.clicked.connect(self._apply_coords)
        coord_row.addWidget(QLabel("خط العرض"))
        coord_row.addWidget(self.lat_spin)
        coord_row.addWidget(QLabel("خط الطول"))
        coord_row.addWidget(self.lon_spin)
        coord_row.addWidget(self.coord_btn)
        coord_row.addStretch(1)
        l.addLayout(coord_row)

        self.geo_status = QLabel("")
        self.geo_status.setWordWrap(True)
        l.addWidget(self.geo_status)
        l.addWidget(self._hint(
            "تحديد الموقع والبحث يتصلان بخدمات خارجية (خدمة الموقع في ويندوز التابعة لمايكروسوفت، "
            "وipwho.is، وOpen-Meteo، وOpenStreetMap). بعد تحديد الموقع تُحسب المواقيت محلياً بدون إنترنت."))
        return c

    def _build_calc_card(self):
        c, l = card()
        l.addWidget(self._section("طريقة الحساب"))
        self.method_cb = NoWheelComboBox()
        for key, (name, _, _) in pt.METHODS.items():
            self.method_cb.addItem(name, key)
        l.addWidget(self.method_cb)
        self.asr_cb = NoWheelComboBox()
        for key, label in pt.ASR_LABELS.items():
            self.asr_cb.addItem("العصر: " + label, key)
        l.addWidget(self.asr_cb)
        l.addWidget(QLabel("تعديل المواقيت بالدقائق (لمطابقة تقويم محلي موثوق):"))
        self.adjust_spins = {}
        grid = QGridLayout()
        for col, name in enumerate(pt.PRAYERS):
            grid.addWidget(self._center_label(pt.PRAYER_AR[name]), 0, col)
            sp = self._spin(-60, 60)
            self.adjust_spins[name] = sp
            grid.addWidget(sp, 1, col)
        l.addLayout(grid)
        l.addWidget(self._hint(
            "ملاحظة: يضيف تقويم أم القرى 30 دقيقة للعشاء في رمضان، وهذا لا يُطبَّق تلقائياً هنا؛ "
            "استخدم خانة تعديل العشاء (+30) خلال رمضان.", "warn"))
        return c

    def _build_notify_card(self):
        c, l = card()
        l.addWidget(self._section("التنبيهات"))
        row = QHBoxLayout()
        self.pre_chk = QCheckBox("تنبيه قبل الأذان بـ")
        self.pre_spin = self._spin(1, 120, " دقيقة", 120)
        row.addWidget(self.pre_chk)
        row.addWidget(self.pre_spin)
        row.addStretch(1)
        l.addLayout(row)
        self.adhan_chk = QCheckBox("إشعار عند دخول وقت الصلاة")
        l.addWidget(self.adhan_chk)
        self.sound_chk = QCheckBox("تشغيل صوت عند دخول وقت الأذان")
        l.addWidget(self.sound_chk)
        srow = QHBoxLayout()
        self.sound_path = QLineEdit()
        self.sound_path.setPlaceholderText("لم يُختر ملف صوت")
        self.sound_path.setReadOnly(True)
        pick = QPushButton("اختيار ملف…")
        pick.clicked.connect(self._pick_sound)
        test_snd = QPushButton("تجربة الصوت")
        test_snd.clicked.connect(self._test_sound)
        srow.addWidget(self.sound_path, 1)
        srow.addWidget(pick)
        srow.addWidget(test_snd)
        l.addLayout(srow)
        l.addWidget(self._hint("يدعم WAV وMP3 وWMA. لا يوجد صوت افتراضي؛ اختر ملفك بنفسك."))
        trow = QHBoxLayout()
        t1 = QPushButton("تجربة التنبيه المسبق")
        t1.clicked.connect(lambda: self._ctx.on_test(pt.pre_text("asr", self.pre_spin.value()), None))
        t2 = QPushButton("تجربة إشعار الأذان")
        t2.clicked.connect(lambda: self._ctx.on_test(pt.adhan_text("asr"), self._sound_cfg()))
        trow.addWidget(t1)
        trow.addWidget(t2)
        trow.addStretch(1)
        l.addLayout(trow)
        return c

    def _build_iqama_card(self):
        c, l = card()
        l.addWidget(self._section("مدة الإقامة بعد الأذان (دقائق)"))
        self.iqama_spins = {}
        grid = QGridLayout()
        for col, name in enumerate(pt.PRAYERS):
            grid.addWidget(self._center_label(pt.PRAYER_AR[name]), 0, col)
            sp = self._spin(0, 120)
            self.iqama_spins[name] = sp
            grid.addWidget(sp, 1, col)
        l.addLayout(grid)
        l.addWidget(self._hint(
            "0 = بدون عدّاد إقامة. القيم الافتراضية تقريبية وقابلة للتعديل، وليست مواقيت إقامة رسمية؛ "
            "اضبطها حسب مسجدك."))
        return c

    # ---------- تعبئة النموذج وجمعه ----------
    def _populate(self, cfg: dict):
        was, self._loading = self._loading, True
        self.enabled_chk.setChecked(cfg["enabled"])
        self.mode_rbs[cfg["display_mode"]].setChecked(True)
        self.tf_rbs[cfg["time_format"]].setChecked(True)
        self.cd_rbs[cfg["countdown_format"]].setChecked(True)
        (self.auto_rb if cfg["location"]["mode"] == "auto" else self.manual_rb).setChecked(True)
        self.method_cb.setCurrentIndex(max(0, self.method_cb.findData(cfg["method"])))
        self.asr_cb.setCurrentIndex(max(0, self.asr_cb.findData(cfg["asr"])))
        for p in pt.PRAYERS:
            self.adjust_spins[p].setValue(cfg["adjust"][p])
            self.iqama_spins[p].setValue(cfg["iqama_minutes"][p])
        self.pre_chk.setChecked(cfg["notify_pre"])
        self.pre_spin.setValue(cfg["pre_minutes"])
        self.adhan_chk.setChecked(cfg["notify_adhan"])
        self.sound_chk.setChecked(cfg["sound"]["enabled"])
        self.sound_path.setText(cfg["sound"]["path"])
        self._sync_coord_spins()
        self._loading = was

    def _sync_coord_spins(self):
        loc = self._cfg["location"]
        if loc["lat"] is not None:
            self.lat_spin.setValue(loc["lat"])
            self.lon_spin.setValue(loc["lon"])

    def _collect(self) -> dict:
        cfg = copy.deepcopy(self._cfg)
        cfg["enabled"] = self.enabled_chk.isChecked()
        for key, rb in self.mode_rbs.items():
            if rb.isChecked():
                cfg["display_mode"] = key
        for key, rb in self.tf_rbs.items():
            if rb.isChecked():
                cfg["time_format"] = key
        for key, rb in self.cd_rbs.items():
            if rb.isChecked():
                cfg["countdown_format"] = key
        cfg["location"]["mode"] = "auto" if self.auto_rb.isChecked() else "manual"
        cfg["method"] = self.method_cb.currentData()
        cfg["asr"] = self.asr_cb.currentData()
        cfg["adjust"] = {p: self.adjust_spins[p].value() for p in pt.PRAYERS}
        cfg["notify_pre"] = self.pre_chk.isChecked()
        cfg["pre_minutes"] = self.pre_spin.value()
        cfg["notify_adhan"] = self.adhan_chk.isChecked()
        cfg["iqama_minutes"] = {p: self.iqama_spins[p].value() for p in pt.PRAYERS}
        cfg["sound"] = self._sound_cfg()
        return pt.sanitize_config(cfg)

    def _connect_form_signals(self):
        for chk in (self.enabled_chk, self.pre_chk, self.adhan_chk, self.sound_chk,
                    *self.mode_rbs.values(), *self.tf_rbs.values(), *self.cd_rbs.values()):
            chk.toggled.connect(self._on_form_changed)
        for cb in (self.method_cb, self.asr_cb):
            cb.currentIndexChanged.connect(self._on_form_changed)
        for sp in (self.pre_spin, *self.adjust_spins.values(), *self.iqama_spins.values()):
            sp.valueChanged.connect(self._on_form_changed)
        self.auto_rb.toggled.connect(self._on_mode_toggled)

    # ---------- العرض الحي ----------
    def _on_form_changed(self, *_):
        if self._loading:
            return
        cfg = self._collect()
        self._tf, self._cf = cfg["time_format"], cfg["countdown_format"]
        self._preview.set_config(dict(cfg, enabled=True))
        self._update_location_ui()
        self._update_dirty(cfg)
        self._refresh_strip()

    def _update_dirty(self, cfg: dict):
        self.dirty_label.setText("● تغييرات غير محفوظة" if cfg != self._applied else "")

    def _update_location_ui(self):
        self.loc_line.setText(pt.describe_location(self._cfg["location"]))
        manual = self.manual_rb.isChecked()
        for w in (self.city_input, self.search_btn, self.results, self.lat_spin, self.lon_spin,
                  self.coord_btn):
            w.setEnabled(manual)
        self.detect_btn.setEnabled(not manual)
        # زر التقدير التقريبي يظهر فقط ما دام هناك تقدير معلّق ونحن في الوضع التلقائي
        self.use_est_btn.setVisible(self._pending_estimate is not None and not manual)

    def _refresh_strip(self):
        if self._loading:
            return
        if not pt.location_ready(self._cfg):
            self.next_label.setText("حدّد موقعك لعرض المواقيت")
            for box, label in self.time_boxes.values():
                label.setText("--:--")
                self._set_active(box, False)
            return
        now = self._ctx.now_fn()
        eng = self._preview
        st = eng.status(now)
        texts = pt.status_texts(st, self._cf)
        self.next_label.setText(texts["line"] if texts else "")
        times = eng.times_for(now)
        for p, (box, label) in self.time_boxes.items():
            active = st.kind in ("next", "iqama") and st.prayer == p
            shown = st.target if (active and st.kind == "next" and st.target is not None) else \
                (times[p] if times else None)
            label.setText(pt.format_clock(shown, self._tf) if shown is not None else "--:--")
            self._set_active(box, active)

    @staticmethod
    def _set_active(box, active: bool):
        if bool(box.property("active")) != active:
            box.setProperty("active", active)
            box.style().unpolish(box)
            box.style().polish(box)

    def showEvent(self, e):
        super().showEvent(e)
        self._tick.start()
        self._refresh_strip()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._tick.stop()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, "body"):
            return
        d = QBoxLayout.LeftToRight if self.width() >= self.WIDE else QBoxLayout.TopToBottom
        if self.body.direction() != d:
            self.body.setDirection(d)

    # ---------- الموقع ----------
    def _set_status(self, text: str, ok):
        color = {True: "#3ddc97", False: "#ffb86b", None: "#8d8d96"}[ok]
        self.geo_status.setStyleSheet(f"color: {color};")
        self.geo_status.setText(text)

    def _apply_location(self, loc: dict):
        self._cfg["location"].update(
            name=loc.get("name", ""), lat=loc["lat"], lon=loc["lon"], tz=loc.get("tz", ""),
            source=loc.get("source", ""), accuracy_m=loc.get("accuracy_m"))
        self._sync_coord_spins()
        self._on_form_changed()

    def _on_mode_toggled(self, _checked):
        if self._loading:
            return
        if self.manual_rb.isChecked():
            self._pending_estimate = None   # تقدير قديم لا يجوز تطبيقه بعد اختيار الوضع اليدوي
        self._on_form_changed()
        if self.auto_rb.isChecked():
            self._start_detect()   # عند العودة للتلقائي نحدّث الموقع (ولا نستبدله إلا عند النجاح)

    def _start_detect(self):
        self._pending_estimate = None
        self._update_location_ui()
        if self.geo.detect():
            self.detect_btn.setEnabled(False)
            self._set_status("جارٍ تحديد موقعك…", None)
        else:
            self._set_status("ما زال تحديد الموقع جارياً…", None)

    def _on_detected(self, loc, msg):
        self.detect_btn.setEnabled(self.auto_rb.isChecked())
        if not self.auto_rb.isChecked():
            return   # المستخدم انتقل لاختيار يدوي أثناء التحديد: نتجاهل النتيجة
        if loc is None:
            self._set_status(f"{msg}. اختر مدينتك يدوياً.", False)
            self.manual_rb.setChecked(True)
            return
        if loc.get("approx"):
            self._pending_estimate = loc
            name = loc.get("name") or "موقع غير معروف"
            self._set_status(
                f"تعذّر تحديد موقعك بدقة. التقدير التقريبي: {name}. قد لا يطابق مدينتك؛ "
                "اختر مدينتك يدوياً أو اضغط «استخدام التقدير التقريبي».", False)
            self._update_location_ui()
            return
        self._pending_estimate = None
        self._apply_location(loc)
        acc = loc.get("accuracy_m")
        suffix = f" (الدقة {pt.format_accuracy(acc)})" if acc is not None else ""
        self._set_status(f"تم تحديد موقعك: {loc['name']}{suffix}", True)

    def _use_estimate(self):
        est, self._pending_estimate = self._pending_estimate, None
        if est and self.auto_rb.isChecked():
            self._apply_location(est)
            self._set_status(f"تم اعتماد التقدير التقريبي: {est['name']}", None)
        else:
            self._update_location_ui()

    def _search(self):
        if not self.manual_rb.isChecked():
            return
        self.results.clear()
        self._set_status("جارٍ البحث…", None)
        self.geo.search(self.city_input.text())

    def _on_searched(self, cities, err):
        self.results.clear()
        if err:
            self._set_status(err, False)
            return
        for loc in cities:
            item = QListWidgetItem(loc["name"])
            item.setData(Qt.UserRole, loc)
            self.results.addItem(item)
        self._set_status("اختر مدينتك من النتائج", None)

    def _choose_city(self, item):
        loc = item.data(Qt.UserRole)
        if not isinstance(loc, dict):
            return
        self._apply_location(dict(loc, source="search", accuracy_m=None))
        self._set_status(f"تم اختيار: {loc['name']}", True)

    def _apply_coords(self):
        lat, lon = self.lat_spin.value(), self.lon_spin.value()
        if lat == 0.0 and lon == 0.0:
            self._set_status("أدخل خط العرض وخط الطول أولاً", False)
            return
        self._apply_location({"name": f"{lat:.3f}, {lon:.3f}", "lat": lat, "lon": lon, "tz": "",
                              "source": "coords", "accuracy_m": None})
        self._set_status("تم اعتماد الإحداثيات. جارٍ معرفة المدينة والمنطقة الزمنية…", None)
        self.geo.resolve(lat, lon)

    def _on_resolved(self, info, err):
        loc = self._cfg["location"]
        if err or not info or loc.get("source") != "coords":
            return
        if abs(info["lat"] - (loc["lat"] or 0)) > 1e-6 or abs(info["lon"] - (loc["lon"] or 0)) > 1e-6:
            return   # نتيجة لنقطة قديمة
        if info.get("tz"):
            loc["tz"] = info["tz"]
        if info.get("name"):
            loc["name"] = info["name"]
        self._on_form_changed()
        self._set_status("تم اعتماد الإحداثيات", True)

    # ---------- الصوت ----------
    def _sound_cfg(self) -> dict:
        return {"enabled": self.sound_chk.isChecked(), "path": self.sound_path.text().strip()}

    def _pick_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف الصوت", "", "ملفات صوت (*.wav *.mp3 *.wma);;كل الملفات (*)")
        if path:
            self.sound_path.setText(path)

    def _test_sound(self):
        ok, msg = self._ctx.sound.play(self.sound_path.text().strip())
        self._set_status("يتم تشغيل الصوت…" if ok else msg, True if ok else False)

    # ---------- الحفظ والتحديث الخارجي ----------
    def _save(self):
        cfg = self._collect()
        self._ctx.on_apply(cfg)
        self._applied = copy.deepcopy(cfg)
        self._update_dirty(cfg)
        self.save_status.setText("تم الحفظ ✓")
        QTimer.singleShot(3000, lambda: self.save_status.setText(""))

    def reload(self, cfg: dict):
        """يُستدعى عند تغيّر الإعدادات من خارج التبويب (مثل تحديد الموقع تلقائياً في الخلفية)."""
        new = pt.sanitize_config(cfg)
        dirty = self._collect() != self._applied
        if dirty:
            # لدى المستخدم تعديلات غير محفوظة: نحدّث الموقع فقط ولا نمسّ بقية ما كتبه
            self._cfg["location"] = copy.deepcopy(new["location"])
            self._applied["location"] = copy.deepcopy(new["location"])
            self._sync_coord_spins()
        else:
            self._cfg = new
            self._applied = copy.deepcopy(new)
            self._populate(new)
        self._on_form_changed()


# ----------------------------------------------------------------------------
# نافذة الإعدادات
# ----------------------------------------------------------------------------
class SettingsWindow(QMainWindow):
    SUBTITLES = ("اضبط الأذكار ووقت ظهورها، وسيعمل البرنامج بهدوء في الخلفية.",
                 "اضبط الموقع وطريقة العرض وتنبيهات الأذان والإقامة.")

    def __init__(self, data, on_saved, on_test, on_ui_font, tray_hint, prayer=None):
        super().__init__()
        self._on_saved = on_saved
        self._on_test = on_test
        self._on_ui_font = on_ui_font
        self._tray_hint = tray_hint
        self._hint_shown = False

        self.setWindowTitle("الأذكار — الإعدادات")
        self.setWindowIcon(make_icon())
        self.setLayoutDirection(Qt.RightToLeft)
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(1040, int(scr.width() * 0.9)), min(700, int(scr.height() * 0.9)))
        self.setAcceptDrops(True)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 18, 24, 18)
        main.setSpacing(12)

        # --- رأس النافذة: تبويبان («الأذكار» و«مواقيت الصلاة والتنبيهات») ---
        tabbar = QFrame()
        tabbar.setObjectName("tabbar")
        tl = QHBoxLayout(tabbar)
        tl.setContentsMargins(5, 5, 5, 5)
        tl.setSpacing(4)
        self.tab_buttons = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for i, text in enumerate(("الأذكار", "مواقيت الصلاة والتنبيهات")):
            b = QPushButton(text)
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self._tab_group.addButton(b, i)
            tl.addWidget(b)
            self.tab_buttons.append(b)
        self.tab_buttons[0].setChecked(True)
        self._tab_group.idClicked.connect(self._switch_tab)
        head = QHBoxLayout()
        head.addWidget(tabbar)
        head.addStretch(1)
        main.addLayout(head)
        self.sub = QLabel(self.SUBTITLES[0])
        self.sub.setObjectName("subtitle")
        self.sub.setWordWrap(True)
        main.addWidget(self.sub)

        self.pages = QStackedWidget()
        main.addWidget(self.pages, 1)

        # الصفحة الأولى: الأذكار (قابلة للتمرير عند ضيق النافذة)
        page = QWidget()
        page.setObjectName("root")
        self.body = QBoxLayout(QBoxLayout.LeftToRight, page)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        side = QVBoxLayout()
        side.setSpacing(14)

        # --- بطاقة الأذكار ---
        c1, l1 = card()
        self.list_title = self._section("قائمة الأذكار")
        l1.addWidget(self.list_title)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("اكتب الذكر هنا…")
        self.input.returnPressed.connect(self.add_dhikr)
        add_btn = QPushButton("إضافة")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.add_dhikr)
        row.addWidget(self.input, 1)
        row.addWidget(add_btn)
        l1.addLayout(row)

        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSpacing(2)
        self.list.setMinimumHeight(170)
        for t in data["adhkar"]:
            self._add_item(t)
        l1.addWidget(self.list, 1)

        imp_btn = QPushButton("استيراد أذكار من ملف نصي (txt)")
        imp_btn.setToolTip("كل سطر في الملف يُضاف كذكر مستقل. يمكنك أيضاً سحب الملف وإفلاته على النافذة.")
        imp_btn.clicked.connect(self.import_txt)
        l1.addWidget(imp_btn)
        imp_hint = QLabel("كل سطر في الملف = ذكر واحد (ويمكنك سحب الملف وإفلاته هنا)")
        imp_hint.setObjectName("hint")
        imp_hint.setWordWrap(True)
        l1.addWidget(imp_hint)

        sug_btn = QPushButton("إضافة الأذكار الصحيحة المقترحة")
        sug_btn.clicked.connect(self.add_suggested)
        l1.addWidget(sug_btn)

        del_btn = QPushButton("حذف الذكر المحدد")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self.delete_selected)
        l1.addWidget(del_btn)
        QShortcut(QKeySequence.Delete, self.list, self.delete_selected,
                  context=Qt.WidgetShortcut)
        self.body.addWidget(c1, 5)
        self._update_count()

        # --- بطاقة الوقت ---
        c2, l2 = card()
        l2.addWidget(self._section("وقت الظهور"))
        trow = QHBoxLayout()
        trow.addWidget(QLabel("إظهار ذكر كل"))
        self.spin = NoWheelSpinBox()
        self.spin.setRange(1, 1440)
        self.spin.setValue(data["interval_minutes"])
        self.spin.setSuffix(" دقيقة")
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setButtonSymbols(QSpinBox.NoButtons)
        self.spin.setMinimumWidth(130)
        trow.addWidget(self.spin)
        trow.addStretch(1)
        l2.addLayout(trow)

        chips = QHBoxLayout()
        for m in (5, 10, 15, 30, 60):
            b = QPushButton(f"{m}")
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, v=m: self.spin.setValue(v))
            chips.addWidget(b)
        chips.addStretch(1)
        l2.addLayout(chips)

        l2.addSpacing(4)
        drow = QHBoxLayout()
        drow.addWidget(QLabel("مدة بقاء الإشعار"))
        self.dur_spin = NoWheelSpinBox()
        self.dur_spin.setRange(*DURATION_RANGE)
        self.dur_spin.setValue(data["display_seconds"])
        self.dur_spin.setSuffix(" ثانية")
        self.dur_spin.setAlignment(Qt.AlignCenter)
        self.dur_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.dur_spin.setMinimumWidth(130)
        drow.addWidget(self.dur_spin)
        drow.addStretch(1)
        l2.addLayout(drow)

        dchips = QHBoxLayout()
        for sec in (5, 7, 10, 15, 30):
            b = QPushButton(f"{sec}")
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, v=sec: self.dur_spin.setValue(v))
            dchips.addWidget(b)
        dchips.addStretch(1)
        l2.addLayout(dchips)

        self.click_check = QCheckBox("إغلاق الإشعار بالضغط عليه")
        self.click_check.setChecked(data.get("click_to_dismiss", True))
        self.click_check.setToolTip("عند التعطيل تمرّ نقراتك من خلال الإشعار إلى النوافذ خلفه.")
        l2.addWidget(self.click_check)

        self.autostart = QCheckBox("تشغيل البرنامج تلقائياً مع ويندوز")
        self.autostart.setChecked(data.get("autostart", False))
        l2.addWidget(self.autostart)
        side.addWidget(c2)

        # --- بطاقة حجم الخط ---
        c3, l3 = card()
        l3.addWidget(self._section("حجم الخط"))

        self.ui_spin = NoWheelSpinBox()
        self.ui_spin.setRange(*UI_FONT_RANGE)
        self.ui_spin.setValue(data["ui_font_size"])
        l3.addLayout(self._size_row("حجم خط التطبيق", self.ui_spin))
        self.ui_spin.valueChanged.connect(self._on_ui_font)

        self.notif_spin = NoWheelSpinBox()
        self.notif_spin.setRange(*NOTIF_FONT_RANGE)
        self.notif_spin.setValue(data["notif_font_size"])
        l3.addLayout(self._size_row("حجم خط الإشعار", self.notif_spin))

        hint = QLabel("حجم خط التطبيق يتغير فوراً. جرّب حجم الإشعار بزر «تجربة الإشعار».")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        l3.addWidget(hint)
        side.addWidget(c3)

        # --- الأزرار ---
        brow = QHBoxLayout()
        save_btn = QPushButton("حفظ التغييرات")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save)
        test_btn = QPushButton("تجربة الإشعار")
        test_btn.clicked.connect(self.test_notification)
        brow.addWidget(save_btn, 1)
        brow.addWidget(test_btn)
        side.addLayout(brow)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignCenter)
        side.addWidget(self.status)
        side.addStretch(1)
        self.body.addLayout(side, 4)

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.status.setText(""))

        # الصفحة الثانية: مواقيت الصلاة والتنبيهات
        self.prayer_tab = PrayerTab(prayer, self) if prayer is not None else None
        if self.prayer_tab is not None:
            self.pages.addWidget(self.prayer_tab)
        else:
            self.tab_buttons[1].setEnabled(False)

    def _switch_tab(self, index: int):
        if index == 1 and self.prayer_tab is None:
            return
        self.pages.setCurrentIndex(index)
        self.sub.setText(self.SUBTITLES[index])

    # --- عناصر مساعدة ---
    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def _size_row(self, label: str, spin: QSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addStretch(1)
        spin.setAlignment(Qt.AlignCenter)
        spin.setButtonSymbols(QSpinBox.NoButtons)
        spin.setMinimumWidth(90)
        minus = QPushButton("−")
        plus = QPushButton("+")
        for b, step in ((minus, -1), (plus, 1)):
            b.setObjectName("chip")
            b.setMinimumWidth(46)
            b.clicked.connect(lambda _=False, s=spin, d=step: s.setValue(s.value() + d))
        row.addWidget(plus)
        row.addWidget(spin)
        row.addWidget(minus)
        return row

    def _add_item(self, text: str):
        item = QListWidgetItem(text)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.list.addItem(item)
        self._update_count()

    def _update_count(self):
        self.list_title.setText(f"قائمة الأذكار ({self.list.count()})")

    # --- التجاوب مع حجم النافذة ---
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, "body"):
            return
        direction = QBoxLayout.LeftToRight if self.width() >= 860 else QBoxLayout.TopToBottom
        if self.body.direction() != direction:
            self.body.setDirection(direction)

    # --- السحب والإفلات لملفات txt ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith(".txt") for u in e.mimeData().urls()
        ):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if path.lower().endswith(".txt"):
                self.import_file(path)

    # --- استيراد ملف txt ---
    def import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف الأذكار", "", "ملفات نصية (*.txt);;كل الملفات (*)"
        )
        if path:
            self.import_file(path)

    def import_file(self, path: str):
        try:
            text = read_text_file(path)
        except Exception as ex:
            self._flash(f"تعذّر قراءة الملف: {ex}")
            return
        existing = set(self.current_adhkar())
        added = dup = 0
        self.list.setUpdatesEnabled(False)
        for line in text.splitlines():
            t = line.strip().lstrip("\ufeff")
            if not t:
                continue
            if t in existing:
                dup += 1
                continue
            self._add_item(t)
            existing.add(t)
            added += 1
        self.list.setUpdatesEnabled(True)
        if added:
            self.list.scrollToBottom()
            msg = f"تمت إضافة {added} ذكر"
            if dup:
                msg += f" (تم تجاهل {dup} مكرر)"
            self._flash(msg + " — اضغط «حفظ التغييرات» لتثبيتها")
        elif dup:
            self._flash("كل أذكار الملف موجودة مسبقاً")
        else:
            self._flash("الملف فارغ ولا يحتوي على أسطر")

    def _flash(self, msg: str):
        self.status.setText(msg)
        self._status_timer.start(3000)

    def current_adhkar(self) -> list:
        return [self.list.item(i).text() for i in range(self.list.count())]

    # --- الإجراءات ---
    def add_dhikr(self):
        text = self.input.text().strip()
        if not text:
            return
        if text in self.current_adhkar():
            self._flash("هذا الذكر موجود مسبقاً")
            return
        self._add_item(text)
        self.input.clear()
        self.list.scrollToBottom()
        self._flash("تمت الإضافة — اضغط «حفظ التغييرات» لتثبيتها")

    def add_suggested(self):
        existing = set(self.current_adhkar())
        added = 0
        for t in SUGGESTED_ADHKAR:
            if t not in existing:
                self._add_item(t)
                added += 1
        if added:
            self.list.scrollToBottom()
            self._flash(f"تمت إضافة {added} من الأذكار — اضغط «حفظ التغييرات» لتثبيتها")
        else:
            self._flash("كل الأذكار المقترحة موجودة مسبقاً")

    def delete_selected(self):
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)
            self._update_count()
            self._flash("تم الحذف — اضغط «حفظ التغييرات» لتثبيته")

    def save(self):
        data = {
            "adhkar": self.current_adhkar(),
            "interval_minutes": self.spin.value(),
            "autostart": self.autostart.isChecked(),
            "ui_font_size": self.ui_spin.value(),
            "notif_font_size": self.notif_spin.value(),
            "display_seconds": self.dur_spin.value(),
            "click_to_dismiss": self.click_check.isChecked(),
        }
        try:
            save_data(data)
        except Exception as e:
            self._flash(f"تعذّر الحفظ: {e}")
            return
        if not set_autostart(data["autostart"]) and data["autostart"]:
            self._flash("تم الحفظ، لكن تعذّر ضبط التشغيل مع ويندوز")
        else:
            self._flash("تم الحفظ ✓")
        self._on_saved(data)

    def test_notification(self):
        items = self.current_adhkar()
        if items:
            self._on_test(random.choice(items), self.notif_spin.value(),
                          self.dur_spin.value(), self.click_check.isChecked())
        else:
            self._flash("أضف ذكراً أولاً")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if not self._hint_shown:
            self._hint_shown = True
            self._tray_hint()


# ----------------------------------------------------------------------------
# المتحكم الرئيسي
# ----------------------------------------------------------------------------
class AdhkarApp:
    def __init__(self, app: QApplication, start_hidden: bool):
        self.app = app
        self.data = load_data()
        self.last = None

        self.font_family = load_fonts()
        self.apply_ui_font(self.data["ui_font_size"])
        app.setLayoutDirection(Qt.RightToLeft)
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(make_icon())

        self.capsule = CapsuleNotification(
            self.font_family, self.data["notif_font_size"],
            self.data["display_seconds"], self.data["click_to_dismiss"],
        )

        # --- مواقيت الصلاة (محرّك واحد + مؤقت واحد فقط طوال عمر التطبيق) ---
        self.prayer_cfg = self.data["prayer"]
        self.clock = pt.make_clock()
        self.engine = pt.PrayerEngine(self.prayer_cfg, pt.StateStore(prayer_state_file()), self.clock)
        self.sound = SoundPlayer()
        self.geo = GeoService()
        self.geo.detected.connect(self._on_auto_location)
        self._tray_tip = None
        self._refresh_capsule_prayer_view()
        self.prayer_timer = QTimer()
        self.prayer_timer.setInterval(1000)
        self.prayer_timer.timeout.connect(self.prayer_tick)
        prayer_ctx = PrayerContext(self.prayer_cfg, self.apply_prayer_config,
                                   self.test_prayer_notice, self.clock, self.sound)

        self.window = SettingsWindow(
            self.data, self.on_saved, self.test_notification,
            self.apply_ui_font, self.tray_hint, prayer_ctx,
        )

        # System Tray
        self.tray = QSystemTrayIcon(make_icon(), app)
        self.tray.setToolTip("الأذكار")
        menu = QMenu()
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.addAction("فتح الإعدادات", self.show_window)
        menu.addAction("إظهار ذكر الآن", self.show_random)
        menu.addAction("الصلاة القادمة", self.show_prayer_status)
        menu.addSeparator()
        menu.addAction("إغلاق نهائي", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger,
                                                  QSystemTrayIcon.DoubleClick) else None
        )
        self.tray.show()
        self._menu = menu

        self.prayer_timer.start()
        if self.prayer_cfg["enabled"] and self.prayer_cfg["location"]["mode"] == "auto":
            self.geo.detect()   # تحديث الموقع في الخلفية؛ عند الفشل نبقي آخر موقع محفوظ

        # المؤقت
        self.timer = QTimer()
        self.timer.timeout.connect(self.show_random)
        self.apply_schedule()

        if not start_hidden:
            self.show_window()

    def apply_ui_font(self, size: int):
        self.app.setFont(QFont(self.font_family, size))
        self.app.setStyleSheet(build_style(self.font_family, size))

    def apply_schedule(self):
        self.timer.stop()
        self.timer.start(self.data["interval_minutes"] * 60 * 1000)

    def on_saved(self, data: dict):
        data["prayer"] = self.prayer_cfg
        self.data = data
        self.capsule.set_font_size(data["notif_font_size"])
        self.capsule.set_duration(data["display_seconds"])
        self.capsule.set_click_dismiss(data["click_to_dismiss"])
        self.apply_schedule()

    def test_notification(self, text: str, size: int, seconds: int, click: bool):
        self.capsule.set_font_size(size)
        self.capsule.set_duration(seconds)
        self.capsule.set_click_dismiss(click)
        self.capsule.show_message(text)

    def show_random(self):
        if self.capsule.is_prayer_showing():
            return   # إشعار الصلاة له الأولوية؛ الذكر التالي في موعده القادم
        items = self.data["adhkar"]
        if not items:
            return
        choices = [x for x in items if x != self.last] or items
        self.last = random.choice(choices)
        self.capsule.set_font_size(self.data["notif_font_size"])
        self.capsule.set_duration(self.data["display_seconds"])
        self.capsule.set_click_dismiss(self.data["click_to_dismiss"])
        self.capsule.show_message(self.last)

    # ===== مواقيت الصلاة =====
    def _refresh_capsule_prayer_view(self):
        if self.prayer_cfg["enabled"]:
            self.capsule.set_prayer_view(self.prayer_cfg["display_mode"], self.engine.status,
                                         self.prayer_cfg["countdown_format"])
        else:
            self.capsule.set_prayer_view("none", None)

    def _apply_capsule_options(self):
        self.capsule.set_font_size(self.data["notif_font_size"])
        self.capsule.set_duration(self.data["display_seconds"])
        self.capsule.set_click_dismiss(self.data["click_to_dismiss"])

    def apply_prayer_config(self, cfg: dict):
        """تطبيق إعدادات الصلاة فوراً (بدون إعادة تشغيل) وحفظها."""
        cfg = pt.sanitize_config(cfg)
        self.prayer_cfg = cfg
        self.data["prayer"] = cfg
        self.engine.set_config(cfg)
        self._refresh_capsule_prayer_view()
        try:
            save_data(self.data)
        except Exception:
            pass
        self._tray_tip = None
        self._update_tray_tip()
        if cfg["enabled"] and cfg["location"]["mode"] == "auto" and not pt.location_ready(cfg):
            self.geo.detect()

    def _adopt_location(self, loc: dict):
        """يعتمد موقعاً مُكتشفاً: يحفظه ويطبّقه ويحدّث التبويب إن تغيّر فعلاً."""
        cfg = self.prayer_cfg
        old = cfg["location"]
        new = copy.deepcopy(cfg)
        tz = loc.get("tz") or ""
        if (not tz and old.get("tz") and pt.location_ready(cfg)
                and pt.distance_km(old["lat"], old["lon"], loc["lat"], loc["lon"]) < 100):
            tz = old["tz"]   # فشل تحديد المنطقة الزمنية (بلا إنترنت) والمكان لم يتغير: نبقي المعروفة
        new["location"].update(name=loc.get("name", ""), lat=loc["lat"], lon=loc["lon"], tz=tz,
                               source=loc.get("source", ""), accuracy_m=loc.get("accuracy_m"))
        new = pt.sanitize_config(new)
        if new["location"] == old:
            return
        self.apply_prayer_config(new)
        tab = getattr(self.window, "prayer_tab", None)
        if tab is not None:
            tab.reload(self.prayer_cfg)

    def _on_auto_location(self, loc, err):
        cfg = self.prayer_cfg
        if cfg["location"]["mode"] != "auto":
            return   # المستخدم اختار يدوياً: لا نغيّر موقعه أبداً
        have = pt.location_ready(cfg)
        if loc and not loc.get("approx"):
            self._adopt_location(loc)               # موقع دقيق (خدمة الموقع في ويندوز)
        elif loc:
            # تقدير تقريبي (IP أو دقة منخفضة): لا نستبدل به موقعاً محفوظاً، ونستخدمه فقط إن لم يوجد غيره
            if not have:
                self._adopt_location(loc)
                self.tray.showMessage(
                    "الأذكار",
                    "تعذّر تحديد موقعك بدقة، فاستُخدم تقدير تقريبي من الإنترنت وقد يكون في مدينة أخرى. "
                    "اختر مدينتك يدوياً من تبويب مواقيت الصلاة.",
                    QSystemTrayIcon.Warning, 8000)
        elif not have and cfg["enabled"]:
            self.tray.showMessage(
                "الأذكار",
                "تعذّر تحديد موقعك تلقائياً. اختر مدينتك يدوياً من تبويب مواقيت الصلاة.",
                QSystemTrayIcon.Warning, 6000)

    def prayer_tick(self):
        """يعمل كل ثانية: إشعارات الصلاة المستحقة + نص أيقونة الـ Tray."""
        try:
            if self.engine.enabled:
                for notice in self.engine.due_notices():
                    if self._deliver_notice(notice):
                        self.engine.mark_delivered(notice)   # لا نسجّل النجاح إلا بعد العرض فعلاً
            self._update_tray_tip()
        except Exception:
            pass   # خطأ عارض لا يجوز أن يوقف المؤقت

    def _deliver_notice(self, notice) -> bool:
        try:
            self._apply_capsule_options()
            self.capsule.show_message(notice.text, kind="prayer")
        except Exception:
            return False
        snd = self.prayer_cfg["sound"]
        if notice.kind == "adhan" and snd["enabled"] and snd["path"]:
            self.sound.play(snd["path"])
        return True

    def test_prayer_notice(self, text: str, sound_cfg=None):
        self._apply_capsule_options()
        self.capsule.show_message(text, kind="prayer")
        if sound_cfg and sound_cfg.get("enabled") and sound_cfg.get("path"):
            self.sound.play(sound_cfg["path"])

    def show_prayer_status(self):
        texts = pt.status_texts(self.engine.status(), self.prayer_cfg["countdown_format"])
        line = texts["line"] if texts else "مواقيت الصلاة غير مفعّلة. فعّلها من الإعدادات."
        self._apply_capsule_options()
        self.capsule.show_message(line, kind="prayer")

    def _tray_line(self, st) -> str:
        if st.kind not in ("next", "iqama"):
            return ""
        mins = (st.remaining + 59) // 60
        h, m = divmod(mins, 60)
        when = f"{h} س {m:02d} د" if h else f"{m} د"
        name = pt.PRAYER_AR[st.prayer]
        return f"{name if st.kind == 'next' else 'إقامة ' + name} بعد {when}"

    def _update_tray_tip(self):
        line = self._tray_line(self.engine.status()) if self.prayer_cfg["enabled"] else ""
        tip = "الأذكار" + (f"\n{line}" if line else "")
        if tip != self._tray_tip:   # لا نلمس أيقونة الـ Tray إلا عند تغيّر النص (كل دقيقة)
            self._tray_tip = tip
            self.tray.setToolTip(tip)

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def tray_hint(self):
        self.tray.showMessage("الأذكار", "البرنامج يعمل في الخلفية. للإغلاق النهائي استخدم أيقونة الـ Tray.",
                              QSystemTrayIcon.Information, 4000)

    def quit(self):
        self.prayer_timer.stop()
        self.sound.stop()
        self.tray.hide()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    start_hidden = "--background" in sys.argv
    controller = AdhkarApp(app, start_hidden)  # noqa: F841 (يُبقي الكائنات حيّة)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
