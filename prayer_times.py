# -*- coding: utf-8 -*-
"""
مواقيت الصلاة والتنبيهات والإقامة - منطق خالص بدون Qt (قابل للاختبار بدون واجهة).

المحتويات:
  1) الإعدادات الافتراضية والتحقق منها
  2) حساب المواقيت محلياً (خوارزمية PrayTimes.org الفلكية المعروفة)
  3) محرّك الحالة: الصلاة القادمة / عداد الإقامة / الإشعارات بدون تكرار
  4) تخزين حالة الإشعارات على القرص
  5) تحديد الموقع (بالـ IP) والبحث عن المدن (Open-Meteo)

كل الأزمنة داخل المحرّك aware datetimes، والساعة تُحقن من الخارج (clock) لتسهيل الاختبار.
"""

from __future__ import annotations

import base64
import copy
import json
import math
import os
import subprocess
import threading
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:  # zoneinfo غير متوفر في إصدارات قديمة جداً
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# ----------------------------------------------------------------------------
# ثوابت
# ----------------------------------------------------------------------------
PRAYERS = ("fajr", "dhuhr", "asr", "maghrib", "isha")
PRAYER_AR = {
    "fajr": "الفجر",
    "dhuhr": "الظهر",
    "asr": "العصر",
    "maghrib": "المغرب",
    "isha": "العشاء",
}

# أوضاع عرض الكبسولة
MODE_HOVER = "hover"   # الذكر فقط، وعند تمرير الماوس تظهر الصلاة القادمة
MODE_STACK = "stack"   # الذكر مع الوقت المتبقي (فوق وتحت)
MODE_SIDE = "side"     # الذكر والوقت بجانب بعضهما
DISPLAY_MODES = (MODE_HOVER, MODE_STACK, MODE_SIDE)

# صيغ العرض: نظام الساعة (24 أو 12 ص/م) وصيغة الوقت المتبقي (بالثواني 2:20:31 أو بالدقائق 2:20)
TIME_FORMATS = ("24", "12")
COUNTDOWN_FORMATS = ("seconds", "minutes")

# طرق الحساب: (الاسم، زاوية الفجر، العشاء: ("deg", زاوية) أو ("min", دقائق بعد المغرب))
METHODS: Dict[str, Tuple[str, float, Tuple[str, float]]] = {
    "makkah": ("أم القرى (مكة المكرمة)", 18.5, ("min", 90)),
    "mwl": ("رابطة العالم الإسلامي", 18.0, ("deg", 17.0)),
    "egypt": ("الهيئة المصرية العامة للمساحة", 19.5, ("deg", 17.5)),
    "isna": ("أمريكا الشمالية (ISNA)", 15.0, ("deg", 15.0)),
    "karachi": ("جامعة العلوم الإسلامية - كراتشي", 18.0, ("deg", 18.0)),
    "kuwait": ("الكويت", 18.0, ("deg", 17.5)),
    "qatar": ("قطر", 18.0, ("min", 90)),
}
ASR_FACTORS = {"standard": 1, "hanafi": 2}
ASR_LABELS = {
    "standard": "الجمهور (الشافعي والمالكي والحنبلي)",
    "hanafi": "الحنفي",
}

GRACE_SECONDS = 90      # الإشعار الذي مرّ موعده بأكثر من هذا لا يُعرض (يُتجاوز)
KEEP_DAYS = 3           # مدة الاحتفاظ بسجل الإشعارات
REARM_SHIFT_SECONDS = 120

DEFAULT_PRAYER_CONFIG: dict = {
    "enabled": False,
    "display_mode": MODE_HOVER,
    "time_format": "24",
    "countdown_format": "seconds",
    "location": {"mode": "auto", "name": "", "lat": None, "lon": None, "tz": "",
                 "source": "", "accuracy_m": None},
    "method": "makkah",
    "asr": "standard",
    "adjust": {p: 0 for p in PRAYERS},            # تعديل المواقيت بالدقائق
    "notify_pre": True,
    "pre_minutes": 5,
    "notify_adhan": True,
    # مدد الإقامة الافتراضية قابلة للتعديل وليست مواقيت إقامة رسمية
    "iqama_minutes": {"fajr": 20, "dhuhr": 20, "asr": 20, "maghrib": 10, "isha": 20},
    "sound": {"enabled": False, "path": ""},
}


# ----------------------------------------------------------------------------
# 1) التحقق من الإعدادات
# ----------------------------------------------------------------------------
def _int_in(value, lo: int, hi: int, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        return max(lo, min(hi, int(value)))
    except Exception:
        return default


def _float_or_none(value, lo: float, hi: float) -> Optional[float]:
    try:
        if isinstance(value, bool) or value is None:
            return None
        f = float(value)
        if math.isnan(f) or math.isinf(f) or f < lo or f > hi:
            return None
        return f
    except Exception:
        return None


def sanitize_config(raw) -> dict:
    """يرجع إعدادات صالحة دائماً (يملأ الناقص بالقيم الافتراضية ويصلح التالف)."""
    cfg = copy.deepcopy(DEFAULT_PRAYER_CONFIG)
    if not isinstance(raw, dict):
        return cfg

    cfg["enabled"] = bool(raw.get("enabled", cfg["enabled"]))
    if raw.get("display_mode") in DISPLAY_MODES:
        cfg["display_mode"] = raw["display_mode"]
    if raw.get("time_format") in TIME_FORMATS:
        cfg["time_format"] = raw["time_format"]
    if raw.get("countdown_format") in COUNTDOWN_FORMATS:
        cfg["countdown_format"] = raw["countdown_format"]
    if raw.get("method") in METHODS:
        cfg["method"] = raw["method"]
    if raw.get("asr") in ASR_FACTORS:
        cfg["asr"] = raw["asr"]

    loc = raw.get("location")
    if isinstance(loc, dict):
        mode = loc.get("mode")
        cfg["location"]["mode"] = mode if mode in ("auto", "manual") else "auto"
        cfg["location"]["name"] = str(loc.get("name") or "")[:80]
        lat = _float_or_none(loc.get("lat"), -90.0, 90.0)
        lon = _float_or_none(loc.get("lon"), -180.0, 180.0)
        if lat is not None and lon is not None:
            cfg["location"]["lat"], cfg["location"]["lon"] = lat, lon
        cfg["location"]["tz"] = str(loc.get("tz") or "")[:64]
        cfg["location"]["source"] = str(loc.get("source") or "")[:12]
        cfg["location"]["accuracy_m"] = _float_or_none(loc.get("accuracy_m"), 0.0, 1.0e7)

    adj = raw.get("adjust")
    if isinstance(adj, dict):
        for p in PRAYERS:
            cfg["adjust"][p] = _int_in(adj.get(p), -60, 60, 0)

    cfg["notify_pre"] = bool(raw.get("notify_pre", cfg["notify_pre"]))
    cfg["pre_minutes"] = _int_in(raw.get("pre_minutes"), 1, 120, cfg["pre_minutes"])
    cfg["notify_adhan"] = bool(raw.get("notify_adhan", cfg["notify_adhan"]))

    iq = raw.get("iqama_minutes")
    if isinstance(iq, dict):
        for p in PRAYERS:
            cfg["iqama_minutes"][p] = _int_in(iq.get(p), 0, 120, cfg["iqama_minutes"][p])

    snd = raw.get("sound")
    if isinstance(snd, dict):
        cfg["sound"]["enabled"] = bool(snd.get("enabled", False))
        cfg["sound"]["path"] = str(snd.get("path") or "")[:500]
    return cfg


def location_ready(cfg: dict) -> bool:
    loc = cfg.get("location", {})
    return loc.get("lat") is not None and loc.get("lon") is not None


def times_key(cfg: dict) -> str:
    """مفتاح يلخّص كل ما يؤثر في المواقيت وأزمنة الأحداث (لإبطال الذاكرة المؤقتة)."""
    loc = cfg["location"]
    return json.dumps(
        [loc["lat"], loc["lon"], loc["tz"], cfg["method"], cfg["asr"], cfg["adjust"],
         cfg["notify_pre"], cfg["pre_minutes"], cfg["notify_adhan"], cfg["iqama_minutes"]],
        sort_keys=True,
    )


# ----------------------------------------------------------------------------
# 2) حساب المواقيت (PrayTimes.org)
# ----------------------------------------------------------------------------
def _sin(d: float) -> float:
    return math.sin(math.radians(d))


def _cos(d: float) -> float:
    return math.cos(math.radians(d))


def _tan(d: float) -> float:
    return math.tan(math.radians(d))


def _arccos(x: float) -> float:
    return math.degrees(math.acos(x))   # يرفع ValueError خارج المجال


def _arcsin(x: float) -> float:
    return math.degrees(math.asin(x))


def _arccot(x: float) -> float:
    return math.degrees(math.atan(1.0 / x))


def _fix_angle(a: float) -> float:
    return a - 360.0 * math.floor(a / 360.0)


def _fix_hour(h: float) -> float:
    return h - 24.0 * math.floor(h / 24.0)


def julian_date(year: int, month: int, day: int) -> float:
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    return (math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1))
            + day + b - 1524.5)


def sun_position(jd: float) -> Tuple[float, float]:
    """(الميل الشمسي بالدرجات، معادلة الزمن بالساعات)."""
    d = jd - 2451545.0
    g = _fix_angle(357.529 + 0.98560028 * d)
    q = _fix_angle(280.459 + 0.98564736 * d)
    lon = _fix_angle(q + 1.915 * _sin(g) + 0.020 * _sin(2 * g))
    e = 23.439 - 0.00000036 * d
    ra = math.degrees(math.atan2(_cos(e) * _sin(lon), _cos(lon))) / 15.0
    eqt = q / 15.0 - _fix_hour(ra)
    decl = _arcsin(_sin(e) * _sin(lon))
    return decl, eqt


def _compute_hours(d: date, lat: float, lon: float, tz_hours: float, method: str,
                   asr: str, elevation: float = 0.0) -> Optional[Dict[str, float]]:
    """ساعات عشرية بالتوقيت المحلي للمناطق الزمنية، أو None إن تعذّر الحساب."""
    _, fajr_angle, isha_spec = METHODS[method]
    asr_factor = ASR_FACTORS[asr]
    jd = julian_date(d.year, d.month, d.day) - lon / (15.0 * 24.0)

    def mid_day(t: float) -> float:
        _, eqt = sun_position(jd + t)
        return _fix_hour(12.0 - eqt)

    def angle_time(angle: float, t: float, ccw: bool = False) -> float:
        decl, _ = sun_position(jd + t)
        noon = mid_day(t)
        x = (-_sin(angle) - _sin(decl) * _sin(lat)) / (_cos(decl) * _cos(lat))
        if x < -1.0 or x > 1.0:
            raise ValueError("sun never reaches this angle")
        tt = _arccos(x) / 15.0
        return noon + (-tt if ccw else tt)

    def asr_time(factor: int, t: float) -> float:
        decl, _ = sun_position(jd + t)
        angle = -_arccot(factor + _tan(abs(lat - decl)))
        return angle_time(angle, t)

    try:
        rise_set = 0.0347 * math.sqrt(max(0.0, elevation)) + 0.833
        fajr = angle_time(fajr_angle, 5 / 24.0, ccw=True)
        sunrise = angle_time(rise_set, 6 / 24.0, ccw=True)
        dhuhr = mid_day(12 / 24.0)
        asr_t = asr_time(asr_factor, 13 / 24.0)
        sunset = angle_time(rise_set, 18 / 24.0)
        maghrib = sunset
        if isha_spec[0] == "deg":
            isha = angle_time(isha_spec[1], 18 / 24.0)
        else:
            isha = 0.0  # يُحسب لاحقاً بعد المغرب
    except (ValueError, ZeroDivisionError):
        return None

    shift = tz_hours - lon / 15.0
    out = {
        "fajr": fajr + shift, "sunrise": sunrise + shift, "dhuhr": dhuhr + shift,
        "asr": asr_t + shift, "maghrib": maghrib + shift, "isha": isha + shift,
    }
    if isha_spec[0] == "min":
        out["isha"] = out["maghrib"] + isha_spec[1] / 60.0
    if any(math.isnan(v) or math.isinf(v) for v in out.values()):
        return None
    return out


def resolve_tzinfo(name: str) -> Optional[tzinfo]:
    if not name or ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def system_tzinfo() -> tzinfo:
    return datetime.now().astimezone().tzinfo  # type: ignore


def compute_day(d: date, lat: float, lon: float, tz: tzinfo, method: str = "makkah",
                asr: str = "standard", adjust: Optional[dict] = None,
                elevation: float = 0.0) -> Optional[Dict[str, datetime]]:
    """مواقيت يوم واحد كـ datetimes (مقرّبة لأقرب دقيقة). None عند تعذّر الحساب.

    لا تُخترع أي قيمة: إن لم تُحسب الخمس صلوات بترتيب منطقي نرجع None.
    """
    adjust = adjust or {}
    noon = datetime(d.year, d.month, d.day, 12, 0, tzinfo=tz)
    off = noon.utcoffset()
    if off is None:
        return None
    hours = _compute_hours(d, lat, lon, off.total_seconds() / 3600.0, method, asr, elevation)
    if hours is None:
        return None

    base = datetime(d.year, d.month, d.day, tzinfo=tz)
    minutes: Dict[str, int] = {}
    for name in PRAYERS:
        adj = _int_in(adjust.get(name, 0), -60, 60, 0)
        minutes[name] = int(math.floor(hours[name] * 60.0 + 0.5)) + adj
    # الشروق للمعلومات فقط
    sunrise_min = int(math.floor(hours["sunrise"] * 60.0 + 0.5))

    order = [minutes[p] for p in PRAYERS]
    if any(order[i] >= order[i + 1] for i in range(len(order) - 1)):
        return None
    if order[0] < 0 or order[-1] >= 48 * 60:
        return None

    out = {p: base + timedelta(minutes=minutes[p]) for p in PRAYERS}
    out["sunrise"] = base + timedelta(minutes=sunrise_min)
    return out


# ----------------------------------------------------------------------------
# 4) تخزين حالة الإشعارات
# ----------------------------------------------------------------------------
class StateStore:
    """يحفظ معرّفات الإشعارات المُرسلة/المتجاوزة في ملف JSON (كتابة ذرّية)."""

    def __init__(self, path: Optional[Path]):
        self.path = Path(path) if path else None
        self.events: Dict[str, dict] = {}
        self._dirty = False
        self._load()

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            ev = raw.get("events", {})
            if isinstance(ev, dict):
                for k, v in ev.items():
                    if isinstance(v, dict) and v.get("s") in ("fired", "skipped"):
                        self.events[str(k)] = {"s": v["s"], "t": str(v.get("t", ""))}
        except Exception:
            self.events = {}

    def get(self, event_id: str) -> Optional[dict]:
        return self.events.get(event_id)

    def set(self, event_id: str, status: str, when: datetime):
        self.events[event_id] = {"s": status, "t": when.isoformat()}
        self._dirty = True

    def delete(self, event_id: str):
        if event_id in self.events:
            del self.events[event_id]
            self._dirty = True

    def prune(self, today: date):
        cutoff = today - timedelta(days=KEEP_DAYS)
        for k in list(self.events):
            try:
                if date.fromisoformat(k.split(":", 1)[0]) < cutoff:
                    del self.events[k]
                    self._dirty = True
            except Exception:
                del self.events[k]
                self._dirty = True

    def save(self):
        if not self._dirty or not self.path:
            self._dirty = False if not self.path else self._dirty
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": 1, "events": self.events},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
            self._dirty = False
        except Exception:
            pass  # فشل الحفظ لا يُوقف الإشعارات (تبقى الحالة في الذاكرة)


# ----------------------------------------------------------------------------
# 3) المحرّك
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Entry:
    prayer: str
    day: date
    start: datetime
    iqama_end: Optional[datetime]


@dataclass(frozen=True)
class Status:
    kind: str                       # disabled | unavailable | next | iqama
    prayer: str = ""
    target: Optional[datetime] = None
    remaining: int = 0              # ثوانٍ (>= 0)
    reason: str = ""                # no_location | calc_failed (عند unavailable)
    note: str = ""                  # tz_fallback مثلاً


@dataclass(frozen=True)
class Notice:
    id: str
    kind: str                       # pre | adhan
    prayer: str
    when: datetime
    text: str


def minutes_phrase(n: int) -> str:
    if n == 1:
        return "دقيقة واحدة"
    if n == 2:
        return "دقيقتان"
    if 3 <= n <= 10:
        return f"{n} دقائق"
    return f"{n} دقيقة"


def pre_text(prayer: str, minutes: int) -> str:
    return f"باقي {minutes_phrase(minutes)} على أذان {PRAYER_AR[prayer]}"


def adhan_text(prayer: str) -> str:
    return f"حان الآن وقت أذان {PRAYER_AR[prayer]}"


LESS_THAN_MINUTE = "أقل من دقيقة"


def format_countdown(seconds: int, fmt: str = "seconds") -> str:
    """الوقت المتبقي. seconds: 2:20:31 (أو 47:05 تحت الساعة). minutes: 2:20 (ساعات:دقائق)."""
    seconds = max(0, int(seconds))
    if fmt == "minutes":
        if seconds < 60:
            return LESS_THAN_MINUTE
        h, m = divmod(seconds // 60, 60)
        return f"{h}:{m:02d}"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_clock(dt: datetime, fmt: str = "24") -> str:
    """وقت الساعة: 24 => 15:29، و12 => 3:29 م (ص/م)."""
    if fmt == "12":
        return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'ص' if dt.hour < 12 else 'م'}"
    return f"{dt.hour:02d}:{dt.minute:02d}"


REASON_TEXT = {
    "no_location": "حدّد موقعك من الإعدادات لعرض المواقيت",
    "calc_failed": "تعذّر حساب المواقيت لهذا الموقع",
}


def status_texts(st: Status, countdown_format: str = "seconds") -> Optional[dict]:
    """نصوص جاهزة للعرض: label (اسم/عنوان) وcountdown (عدّاد) وline (سطر واحد)."""
    if st.kind in ("next", "iqama"):
        name = PRAYER_AR[st.prayer]
        cd = format_countdown(st.remaining, countdown_format)
        label = name if st.kind == "next" else f"إقامة {name}"
        return {"label": label, "countdown": cd, "line": f"{label} بعد {cd}"}
    if st.kind == "unavailable":
        msg = REASON_TEXT.get(st.reason, REASON_TEXT["calc_failed"])
        return {"label": "", "countdown": "", "line": msg}
    return None


class PrayerEngine:
    def __init__(self, config: dict, store: Optional[StateStore] = None,
                 clock: Optional[Callable[[], datetime]] = None):
        self.store = store or StateStore(None)
        self.clock = clock or (lambda: datetime.now().astimezone())
        self._lock = threading.Lock()
        self._day_cache: Dict[Tuple[date, str], Optional[dict]] = {}
        self.cfg: dict = sanitize_config(config)
        self._key = times_key(self.cfg)
        self._tz: Optional[tzinfo] = None
        self._tz_note = ""
        self._refresh_tz()

    # --- الإعدادات ---
    def set_config(self, config: dict):
        """تطبيق إعدادات جديدة فوراً (بدون إعادة تشغيل)."""
        self.cfg = sanitize_config(config)
        self._key = times_key(self.cfg)
        self._day_cache.clear()
        self._refresh_tz()

    @property
    def enabled(self) -> bool:
        return bool(self.cfg["enabled"])

    def times_for(self, now: Optional[datetime] = None) -> Optional[Dict[str, datetime]]:
        """مواقيت اليوم المحلي للحظة now (للعرض في الواجهة). None إن لم تتوفر."""
        now = now or self.clock()
        if self._tz is None or not location_ready(self.cfg):
            return None
        return self.day_times(now.astimezone(self._tz).date())

    def _refresh_tz(self):
        loc = self.cfg["location"]
        tz = resolve_tzinfo(loc["tz"])
        self._tz_note = ""
        if tz is None and location_ready(self.cfg):
            tz = system_tzinfo()
            self._tz_note = "tz_fallback"
        self._tz = tz

    # --- الحساب ---
    def day_times(self, d: date) -> Optional[Dict[str, datetime]]:
        if not location_ready(self.cfg) or self._tz is None:
            return None
        key = (d, self._key)
        if key in self._day_cache:
            return self._day_cache[key]
        if len(self._day_cache) > 12:
            self._day_cache.clear()
        loc = self.cfg["location"]
        res = compute_day(d, loc["lat"], loc["lon"], self._tz, self.cfg["method"],
                          self.cfg["asr"], self.cfg["adjust"])
        self._day_cache[key] = res
        return res

    def _entries(self, now: datetime) -> Optional[List[Entry]]:
        tz = self._tz
        d0 = now.astimezone(tz).date()
        entries: List[Entry] = []
        for delta in (-1, 0, 1):
            d = d0 + timedelta(days=delta)
            times = self.day_times(d)
            if times is None:
                if delta == 0:
                    return None
                continue
            for p in PRAYERS:
                start = times[p]
                iq = self.cfg["iqama_minutes"][p]
                entries.append(Entry(p, d, start, start + timedelta(minutes=iq) if iq > 0 else None))
        entries.sort(key=lambda e: e.start)
        return entries

    # --- الحالة (الصلاة القادمة / الإقامة) ---
    def status(self, now: Optional[datetime] = None) -> Status:
        now = now or self.clock()
        if not self.enabled:
            return Status("disabled")
        if not location_ready(self.cfg) or self._tz is None:
            return Status("unavailable", reason="no_location")
        entries = self._entries(now)
        if not entries:
            return Status("unavailable", reason="calc_failed", note=self._tz_note)
        for e in entries:
            if e.iqama_end is not None and e.start <= now < e.iqama_end:
                return Status("iqama", e.prayer, e.iqama_end, _ceil_seconds(e.iqama_end - now),
                              note=self._tz_note)
        for e in entries:
            if e.start > now:
                return Status("next", e.prayer, e.start, _ceil_seconds(e.start - now),
                              note=self._tz_note)
        return Status("unavailable", reason="calc_failed", note=self._tz_note)

    # --- الإشعارات ---
    def _events(self, entries: List[Entry]) -> List[Notice]:
        out: List[Notice] = []
        pre_min = self.cfg["pre_minutes"]
        for e in entries:
            if self.cfg["notify_pre"]:
                out.append(Notice(f"{e.day.isoformat()}:{e.prayer}:pre", "pre", e.prayer,
                                  e.start - timedelta(minutes=pre_min), pre_text(e.prayer, pre_min)))
            if self.cfg["notify_adhan"]:
                out.append(Notice(f"{e.day.isoformat()}:{e.prayer}:adhan", "adhan", e.prayer,
                                  e.start, adhan_text(e.prayer)))
        out.sort(key=lambda n: n.when)
        return out

    def due_notices(self, now: Optional[datetime] = None) -> List[Notice]:
        """إشعارات حان وقتها الآن (حدّ أقصى واحد). لا يُسجَّل الإشعار كمُرسَل إلا بـ mark_delivered.

        سياسة الإشعارات الفائتة: ما مرّ موعده بأكثر من GRACE_SECONDS يُتجاوز بصمت (مثلاً
        أثناء إغلاق التطبيق أو السكون)، ولا تُعرض أكثر من إشعار واحد دفعة واحدة.
        """
        if not self._lock.acquire(blocking=False):
            return []  # منع تنفيذ المعالج مرتين بالتوازي
        try:
            now = now or self.clock()
            if not self.enabled or not location_ready(self.cfg) or self._tz is None:
                return []
            entries = self._entries(now)
            if not entries:
                return []
            start_by_id = {f"{e.day.isoformat()}:{e.prayer}": e.start for e in entries}

            candidates: List[Notice] = []
            for ev in self._events(entries):
                rec = self.store.get(ev.id)
                if rec is not None:
                    # تغيّر الموعد كثيراً إلى المستقبل (موقع/طريقة/تعديل): أعد التفعيل بأمان
                    try:
                        old = datetime.fromisoformat(rec["t"])
                        shifted = abs((ev.when - old).total_seconds()) >= REARM_SHIFT_SECONDS
                    except Exception:
                        shifted = False
                    if shifted and ev.when > now:
                        self.store.delete(ev.id)
                        rec = None
                if rec is not None:
                    continue
                if now < ev.when:
                    continue  # في المستقبل
                if ev.kind == "pre" and now >= start_by_id[ev.id.rsplit(":", 1)[0]]:
                    self.store.set(ev.id, "skipped", ev.when)   # انتهى وقت التنبيه المسبق
                    continue
                if (now - ev.when).total_seconds() <= GRACE_SECONDS:
                    candidates.append(ev)
                else:
                    self.store.set(ev.id, "skipped", ev.when)   # فات موعده: لا نعرضه متأخراً

            chosen: List[Notice] = []
            if candidates:
                candidates.sort(key=lambda n: n.when)
                for old in candidates[:-1]:
                    self.store.set(old.id, "skipped", old.when)
                chosen = [candidates[-1]]
            self.store.prune(now.astimezone(self._tz).date())
            self.store.save()
            return chosen
        finally:
            self._lock.release()

    def mark_delivered(self, notice: Notice):
        """يُستدعى بعد نجاح عرض الإشعار فعلاً."""
        self.store.set(notice.id, "fired", notice.when)
        self.store.save()


def _ceil_seconds(delta: timedelta) -> int:
    return max(0, int(math.ceil(delta.total_seconds())))


# ----------------------------------------------------------------------------
# الساعة (مع إمكانية الاختبار اليدوي بساعة وهمية)
# ----------------------------------------------------------------------------
def make_clock(env=None) -> Callable[[], datetime]:
    """الساعة الحقيقية، أو ساعة وهمية تبدأ من ADHKAR_FAKE_NOW (ISO) وتتقدم بالزمن الفعلي.

    للاختبار اليدوي فقط، مثال: set ADHKAR_FAKE_NOW=2026-10-11T15:25:00+03:00
    """
    env = os.environ if env is None else env
    raw = env.get("ADHKAR_FAKE_NOW")
    if raw:
        try:
            start = datetime.fromisoformat(raw.strip())
            if start.tzinfo is None:
                start = start.astimezone()
            t0 = _time.monotonic()
            return lambda: start + timedelta(seconds=_time.monotonic() - t0)
        except Exception:
            pass
    return lambda: datetime.now().astimezone()


# ----------------------------------------------------------------------------
# 5) الموقع: IP + بحث المدن
# ----------------------------------------------------------------------------
USER_AGENT = "AdhkarApp/1.0 (desktop)"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
IP_URLS = ("https://ipwho.is/", "https://ipapi.co/json/")   # الثاني احتياطي


class GeoError(Exception):
    pass


def http_get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https فقط)
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _valid_loc(name, lat, lon, tz) -> Optional[dict]:
    la = _float_or_none(lat, -90.0, 90.0)
    lo = _float_or_none(lon, -180.0, 180.0)
    if la is None or lo is None:
        return None
    return {"name": str(name or "")[:80], "lat": la, "lon": lo, "tz": str(tz or "")[:64]}


def parse_ip_location(payload) -> Optional[dict]:
    """يفهم ردّ ipwho.is وipapi.co. يرجع None إن لم يكن الرد موقعاً حقيقياً."""
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False or payload.get("error"):
        return None
    tz = payload.get("timezone")
    if isinstance(tz, dict):
        tz = tz.get("id")
    name = payload.get("city") or payload.get("region") or payload.get("country") \
        or payload.get("country_name") or ""
    country = payload.get("country") or payload.get("country_name") or ""
    if name and country and name != country:
        name = f"{name}، {country}"
    return _valid_loc(name, payload.get("latitude"), payload.get("longitude"), tz)


def detect_location_by_ip(fetch: Callable = http_get_json) -> Tuple[Optional[dict], str]:
    """(الموقع، رسالة خطأ). لا نقول إننا اكتشفنا الموقع إلا إذا وصلتنا نتيجة فعلية صالحة."""
    last = "تعذّر الاتصال بخدمة تحديد الموقع"
    for url in IP_URLS:
        try:
            loc = parse_ip_location(fetch(url))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            last = "تعذّر الاتصال بالإنترنت"
            continue
        except Exception:
            continue
        if loc:
            return loc, ""
        last = "لم تُرجع الخدمة موقعاً صالحاً"
    return None, last


def parse_city_results(payload) -> List[dict]:
    out: List[dict] = []
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        parts = [r.get("name"), r.get("admin1"), r.get("country")]
        label = "، ".join(dict.fromkeys(str(p) for p in parts if p))
        loc = _valid_loc(label, r.get("latitude"), r.get("longitude"), r.get("timezone"))
        if loc:
            out.append(loc)
    return out


def search_cities(query: str, fetch: Callable = http_get_json, language: str = "ar",
                  count: int = 8) -> Tuple[List[dict], str]:
    q = (query or "").strip()
    if len(q) < 2:
        return [], "اكتب حرفين على الأقل للبحث"
    url = GEOCODE_URL + "?" + urllib.parse.urlencode(
        {"name": q, "count": count, "language": language, "format": "json"})
    try:
        res = parse_city_results(fetch(url))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return [], "تعذّر الاتصال بالإنترنت للبحث عن المدينة"
    except Exception:
        return [], "حدث خطأ أثناء البحث"
    if not res:
        return [], "لا توجد نتائج مطابقة"
    return res, ""


# ----------------------------------------------------------------------------
# تحديد الموقع الأدق: خدمة الموقع في ويندوز (Wi-Fi/GPS) ثم الـ IP كحل أخير تقريبي
# ----------------------------------------------------------------------------
ACCURATE_METERS = 10_000.0    # أدق من هذا = موقع موثوق للمواقيت (≈ فرق أقل من نصف دقيقة)
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WINLOC_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Device
  $w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High)
  [void]$w.TryStart($false, [TimeSpan]::FromSeconds(8))
  $deadline = (Get-Date).AddSeconds(12)
  while (($w.Status -ne 'Ready') -and ($w.Permission -ne 'Denied') -and ((Get-Date) -lt $deadline)) { Start-Sleep -Milliseconds 150 }
  if ($w.Permission -eq 'Denied') { $o = @{ status = 'denied' } }
  elseif ($w.Status -ne 'Ready' -or $w.Position.Location.IsUnknown) { $o = @{ status = 'unknown' } }
  else { $l = $w.Position.Location; $o = @{ status = 'ok'; lat = $l.Latitude; lon = $l.Longitude; acc = $l.HorizontalAccuracy } }
} catch { $o = @{ status = 'error'; msg = $_.Exception.Message } }
$o | ConvertTo-Json -Compress
"""

WINLOC_ERRORS = {
    "denied": "تم رفض الوصول إلى الموقع. فعّل «الموقع» من إعدادات ويندوز > الخصوصية والأمان > الموقع، "
              "واسمح لتطبيقات سطح المكتب",
    "unknown": "لم تتمكن خدمة الموقع في ويندوز من تحديد موقعك (فعّل الموقع وتأكد من اتصال Wi-Fi)",
    "error": "تعذّر الحصول على الموقع من ويندوز",
    "timeout": "انتهت مهلة خدمة الموقع في ويندوز",
    "unavailable": "خدمة الموقع في ويندوز غير متاحة على هذا الجهاز",
}


def run_powershell(script: str, timeout: float = 25.0) -> Tuple[int, str, str]:
    """يشغّل PowerShell 5.1 (المدمج في ويندوز) بدون نافذة. يرفع استثناءات subprocess كما هي."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    cp = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", encoded],
        capture_output=True, timeout=timeout, creationflags=flags)
    return (cp.returncode, cp.stdout.decode("utf-8", errors="replace"),
            cp.stderr.decode("utf-8", errors="replace"))


def parse_windows_location(text: str) -> dict:
    """يفهم ناتج WINLOC_SCRIPT. يرجع {'status': ok|denied|unknown|error, ...}."""
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end < start:
        return {"status": "error"}
    try:
        raw = json.loads(text[start:end + 1])
    except ValueError:
        return {"status": "error"}
    if not isinstance(raw, dict):
        return {"status": "error"}
    status = str(raw.get("status") or "error")
    if status != "ok":
        return {"status": status if status in ("denied", "unknown") else "error"}
    lat = _float_or_none(raw.get("lat"), -90.0, 90.0)
    lon = _float_or_none(raw.get("lon"), -180.0, 180.0)
    if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
        return {"status": "unknown"}
    acc = _float_or_none(raw.get("acc"), 0.0, 1.0e7)   # NaN أو سالب => غير معروفة (None)
    return {"status": "ok", "lat": lat, "lon": lon, "acc": acc}


def detect_location_windows(run: Callable = run_powershell) -> Tuple[Optional[dict], str]:
    """(الموقع، رسالة خطأ). الموقع يحمل source='windows' وaccuracy_m وapprox."""
    try:
        _, out, _ = run(WINLOC_SCRIPT)
    except FileNotFoundError:
        return None, WINLOC_ERRORS["unavailable"]
    except subprocess.TimeoutExpired:
        return None, WINLOC_ERRORS["timeout"]
    except Exception:
        return None, WINLOC_ERRORS["error"]
    res = parse_windows_location(out)
    if res["status"] != "ok":
        return None, WINLOC_ERRORS.get(res["status"], WINLOC_ERRORS["error"])
    acc = res["acc"]
    loc = {"name": "", "lat": res["lat"], "lon": res["lon"], "tz": "", "source": "windows",
           "accuracy_m": acc, "approx": acc is None or acc > ACCURATE_METERS}
    return loc, ""


def reverse_geocode_name(lat: float, lon: float, fetch: Callable = http_get_json) -> str:
    """اسم المدينة من الإحداثيات (Nominatim). يرجع '' عند أي فشل."""
    url = NOMINATIM_REVERSE_URL + "?" + urllib.parse.urlencode(
        {"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 10,
         "addressdetails": 1, "accept-language": "ar"})
    try:
        data = fetch(url)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    addr = data.get("address")
    if isinstance(addr, dict):
        place = next((addr[k] for k in ("city", "town", "village", "suburb", "municipality",
                                        "county", "state_district") if addr.get(k)), "")
        parts = [place, addr.get("state"), addr.get("country")]
        label = "، ".join(dict.fromkeys(str(p) for p in parts if p))
        if label:
            return label[:80]
    return str(data.get("display_name") or "")[:80]


def lookup_timezone(lat: float, lon: float, fetch: Callable = http_get_json) -> str:
    """اسم المنطقة الزمنية IANA من الإحداثيات (Open-Meteo timezone=auto). '' عند الفشل."""
    url = OPEN_METEO_FORECAST_URL + "?" + urllib.parse.urlencode(
        {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto",
         "current_weather": "true"})
    try:
        data = fetch(url)
    except Exception:
        return ""
    name = data.get("timezone") if isinstance(data, dict) else None
    if isinstance(name, str) and resolve_tzinfo(name) is not None:
        return name
    return ""


def resolve_point(lat: float, lon: float, fetch: Callable = http_get_json) -> dict:
    """يُكمل نقطة بالإحداثيات فقط: اسم المدينة والمنطقة الزمنية (كلٌّ منهما اختياري)."""
    return {"name": reverse_geocode_name(lat, lon, fetch), "tz": lookup_timezone(lat, lon, fetch)}


def detect_location_precise(run: Callable = run_powershell,
                            fetch: Callable = http_get_json) -> Tuple[Optional[dict], str]:
    """الأدق أولاً: خدمة الموقع في ويندوز، ثم IP كحل أخير يُعلَّم approx=True.

    يرجع (الموقع، رسالة). الرسالة عند النجاح قد تشرح لماذا لم نحصل على موقع دقيق.
    """
    loc, werr = detect_location_windows(run)
    if loc:
        info = resolve_point(loc["lat"], loc["lon"], fetch)
        loc["tz"] = info["tz"]
        loc["name"] = info["name"] or f"{loc['lat']:.3f}, {loc['lon']:.3f}"
        return loc, ""
    ip, ierr = detect_location_by_ip(fetch)
    if ip:
        ip = dict(ip, source="ip", accuracy_m=None, approx=True)
        return ip, werr
    return None, f"{werr}. {ierr}"


def format_accuracy(meters: Optional[float]) -> str:
    if meters is None:
        return ""
    if meters < 1000:
        return f"≈ {int(round(meters, -1)) or int(meters)} م"
    return f"≈ {int(round(meters / 1000.0))} كم"


SOURCE_LABELS = {
    "windows": "خدمة الموقع في ويندوز",
    "ip": "تقدير من الإنترنت (تقريبي)",
    "search": "اختيار يدوي",
    "coords": "إحداثيات يدوية",
}


def describe_location(loc: dict) -> str:
    """وصف نصي للموقع الحالي (المدينة والإحداثيات والمنطقة الزمنية والمصدر والدقة)."""
    lat, lon = loc.get("lat"), loc.get("lon")
    if lat is None or lon is None:
        return "لم يتم تحديد موقع بعد"
    parts = [f"{loc.get('name') or 'موقع بدون اسم'} ({lat:.3f}, {lon:.3f})",
             loc.get("tz") or "توقيت النظام"]
    src = SOURCE_LABELS.get(loc.get("source") or "")
    if src:
        parts.append(src)
    acc = format_accuracy(loc.get("accuracy_m"))
    if acc:
        parts.append("الدقة " + acc)
    return " · ".join(parts)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """المسافة التقريبية بين نقطتين بالكيلومتر (haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))
