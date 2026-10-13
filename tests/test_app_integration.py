# -*- coding: utf-8 -*-
"""اختبارات ربط مواقيت الصلاة بالتطبيق: منطق AdhkarApp الحقيقي مع بدائل مزيّفة للكبسولة والـ Tray والصوت.

هذه ليست اختبارات واجهة رسومية (لا Qt هنا): الرسم والحركة والتمرير يُختبران يدوياً على ويندوز.
"""
import ast
import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SRC))

import qt_stub  # noqa: E402

qt_stub.install()
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="adhkar_it_")
os.environ.pop("ADHKAR_DATA_DIR", None)
app_mod = importlib.import_module("adhkar_app")
import prayer_times as pt  # noqa: E402

RIYADH = ZoneInfo("Asia/Riyadh")


def at(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=RIYADH)


class FakeCapsule:
    def __init__(self):
        self.shown, self.opts, self.view = [], [], None
        self.fail = False
        self.prayer_showing = False

    def show_message(self, text, kind="dhikr"):
        if self.fail:
            raise RuntimeError("boom")
        self.shown.append((text, kind))
        return True

    def is_prayer_showing(self):
        return self.prayer_showing

    def set_font_size(self, v):
        self.opts.append(("font", v))

    def set_duration(self, v):
        self.opts.append(("dur", v))

    def set_click_dismiss(self, v):
        self.opts.append(("click", v))

    def set_prayer_view(self, mode, fn, fmt="seconds"):
        self.view = (mode, fn)
        self.fmt = fmt


class FakeTray:
    def __init__(self):
        self.tips, self.messages = [], []

    def setToolTip(self, t):
        self.tips.append(t)

    def showMessage(self, *a):
        self.messages.append(a)


class FakeSound:
    def __init__(self):
        self.calls = []

    def play(self, path):
        self.calls.append(path)
        return True, ""

    def stop(self):
        pass


class FakeTab:
    def __init__(self):
        self.reloads = []

    def reload(self, cfg):
        self.reloads.append(cfg)


class FakeWindow:
    def __init__(self):
        self.prayer_tab = FakeTab()


class FakeGeo:
    def __init__(self):
        self.detects = 0

    def detect(self):
        self.detects += 1
        return True


class FakeTimer:
    def stop(self):
        pass

    def start(self, *_):
        pass


def cfg_dict(**over):
    raw = {"enabled": True,
           "location": {"mode": "manual", "name": "مكة", "lat": 21.4225, "lon": 39.8262,
                        "tz": "Asia/Riyadh"}}
    raw.update(over)
    return pt.sanitize_config(raw)


def make_app(now=None, **over):
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="adhkar_case_")
    a = app_mod.AdhkarApp.__new__(app_mod.AdhkarApp)
    a.data = app_mod.load_data()
    cfg = cfg_dict(**over)
    a.prayer_cfg = cfg
    a.data["prayer"] = cfg
    holder = {"now": now or at(2026, 8, 12, 15, 0)}
    a.clock = lambda: holder["now"]
    a.engine = pt.PrayerEngine(cfg, pt.StateStore(app_mod.prayer_state_file()), a.clock)
    a.capsule, a.tray, a.sound, a.geo = FakeCapsule(), FakeTray(), FakeSound(), FakeGeo()
    a.timer = FakeTimer()
    a.window = FakeWindow()
    a._tray_tip = None
    a._prayer_dialog = None
    a.last = None
    return a, holder


class TickAndDelivery(unittest.TestCase):
    def test_adhan_is_delivered_once_with_sound_and_pre_without_sound(self):
        a, h = make_app(sound={"enabled": True, "path": "C:/x/adhan.mp3"})
        day = a.engine.day_times(date(2026, 8, 12))
        t = day["asr"] - timedelta(minutes=6)
        while t <= day["asr"] + timedelta(minutes=2):
            h["now"] = t
            a.prayer_tick()
            t += timedelta(seconds=1)
        self.assertEqual(a.capsule.shown, [("باقي 5 دقائق على أذان العصر", "prayer"),
                                           ("حان الآن وقت أذان العصر", "prayer")])
        self.assertEqual(a.sound.calls, ["C:/x/adhan.mp3"])     # للأذان فقط، ومرة واحدة

    def test_sound_disabled_by_default_is_never_played(self):
        a, h = make_app()
        h["now"] = a.engine.day_times(date(2026, 8, 12))["asr"]
        a.prayer_tick()
        self.assertEqual(len(a.capsule.shown), 1)
        self.assertEqual(a.sound.calls, [])

    def test_failed_delivery_is_not_marked_and_retried_then_succeeds_once(self):
        a, h = make_app()
        t = a.engine.day_times(date(2026, 8, 12))["asr"]
        a.capsule.fail = True
        h["now"] = t
        a.prayer_tick()
        self.assertEqual(a.capsule.shown, [])
        a.capsule.fail = False
        h["now"] = t + timedelta(seconds=3)
        a.prayer_tick()
        a.prayer_tick()
        self.assertEqual(len(a.capsule.shown), 1)

    def test_disabled_prayers_do_nothing(self):
        a, h = make_app(enabled=False)
        h["now"] = a.engine.day_times(date(2026, 8, 12))["asr"]
        a.prayer_tick()
        self.assertEqual(a.capsule.shown, [])
        self.assertEqual(a.tray.tips[-1], "الأذكار")

    def test_exception_in_tick_does_not_propagate(self):
        a, h = make_app()
        a.engine.due_notices = lambda *_: (_ for _ in ()).throw(RuntimeError("x"))
        a.prayer_tick()   # يجب ألا يرفع استثناء (وإلا توقف المؤقت)

    def test_dhikr_does_not_interrupt_a_showing_prayer_notice(self):
        a, _ = make_app()
        a.capsule.prayer_showing = True
        a.show_random()
        self.assertEqual(a.capsule.shown, [])
        a.capsule.prayer_showing = False
        a.show_random()
        self.assertEqual(len(a.capsule.shown), 1)
        self.assertEqual(a.capsule.shown[0][1], "dhikr")

    def test_test_buttons_show_prayer_notices_and_play_sound_only_when_enabled(self):
        a, _ = make_app()
        a.test_prayer_notice("باقي 5 دقائق على أذان العصر", None)
        a.test_prayer_notice("حان الآن وقت أذان العصر", {"enabled": True, "path": "a.wav"})
        a.test_prayer_notice("حان الآن وقت أذان العصر", {"enabled": False, "path": "a.wav"})
        self.assertEqual([k for _, k in a.capsule.shown], ["prayer"] * 3)
        self.assertEqual(a.sound.calls, ["a.wav"])

    def test_show_prayer_status_message(self):
        a, _ = make_app()
        a.show_prayer_status()
        self.assertEqual(a.capsule.shown[-1], ("العصر بعد 47:00", "prayer"))
        b, _ = make_app(enabled=False)
        b.show_prayer_status()
        self.assertIn("غير مفعّلة", b.capsule.shown[-1][0])


class ConfigApplication(unittest.TestCase):
    def test_apply_updates_engine_view_and_persists_to_disk(self):
        a, h = make_app()
        new = cfg_dict(display_mode="side", adjust={"asr": 10},
                       iqama_minutes={"fajr": 20, "dhuhr": 20, "asr": 7, "maghrib": 10, "isha": 20})
        a.apply_prayer_config(new)
        self.assertEqual(a.capsule.view[0], "side")
        asr = a.engine.day_times(date(2026, 8, 12))["asr"]
        self.assertEqual(asr.strftime("%H:%M"), "15:57")        # 15:47 + 10 دقائق
        self.assertEqual(a.engine.status(asr + timedelta(minutes=1)).remaining, 6 * 60)
        saved = json.loads(app_mod.data_file().read_text(encoding="utf-8"))
        self.assertEqual(saved["prayer"]["display_mode"], "side")
        self.assertEqual(saved["prayer"]["adjust"]["asr"], 10)
        self.assertEqual(saved["adhkar"], a.data["adhkar"])      # لم نفقد الأذكار

    def test_switching_modes_live_changes_capsule_view_each_time(self):
        a, _ = make_app()
        seen = []
        for mode in ("hover", "stack", "side", "hover"):
            a.apply_prayer_config(cfg_dict(display_mode=mode))
            seen.append(a.capsule.view[0])
        self.assertEqual(seen, ["hover", "stack", "side", "hover"])
        a.apply_prayer_config(cfg_dict(enabled=False))
        self.assertEqual(a.capsule.view, ("none", None))

    def test_auto_mode_without_location_triggers_detection_only_then(self):
        a, _ = make_app(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        a.apply_prayer_config(a.prayer_cfg)
        self.assertEqual(a.geo.detects, 1)
        b, _ = make_app()          # موقع جاهز: لا حاجة للكشف
        b.apply_prayer_config(b.prayer_cfg)
        self.assertEqual(b.geo.detects, 0)

    def test_auto_location_result_is_ignored_in_manual_mode(self):
        a, _ = make_app()
        before = json.dumps(a.prayer_cfg, sort_keys=True)
        a._on_auto_location({"name": "X", "lat": 1.0, "lon": 2.0, "tz": "UTC"}, "")
        self.assertEqual(json.dumps(a.prayer_cfg, sort_keys=True), before)

    def test_auto_location_success_updates_and_persists_once(self):
        a, _ = make_app(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        loc = {"name": "الدمام", "lat": 26.43, "lon": 50.1, "tz": "Asia/Riyadh"}
        a._on_auto_location(loc, "")
        self.assertEqual(a.prayer_cfg["location"]["lat"], 26.43)
        self.assertEqual(a.prayer_cfg["location"]["mode"], "auto")
        saved = json.loads(app_mod.data_file().read_text(encoding="utf-8"))
        self.assertEqual(saved["prayer"]["location"]["name"], "الدمام")
        mtime = app_mod.data_file().stat().st_mtime_ns
        a._on_auto_location(loc, "")                  # نفس الموقع: لا إعادة حفظ ولا تغيير
        self.assertEqual(app_mod.data_file().stat().st_mtime_ns, mtime)

    def test_auto_location_failure_warns_only_when_no_location_exists(self):
        a, _ = make_app(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        a._on_auto_location(None, "تعذّر الاتصال بالإنترنت")
        self.assertEqual(len(a.tray.messages), 1)
        self.assertIn("يدوياً", a.tray.messages[0][1])
        b, _ = make_app(location={"mode": "auto", "name": "مكة", "lat": 21.4, "lon": 39.8,
                                  "tz": "Asia/Riyadh"})
        b._on_auto_location(None, "تعذّر الاتصال بالإنترنت")
        self.assertEqual(b.tray.messages, [])                  # نبقي آخر موقع بصمت
        self.assertEqual(b.prayer_cfg["location"]["name"], "مكة")

    def test_on_saved_keeps_prayer_config(self):
        a, _ = make_app(display_mode="stack")
        new_data = {k: v for k, v in a.data.items() if k != "prayer"}
        a.on_saved(new_data)
        self.assertEqual(a.data["prayer"]["display_mode"], "stack")
        self.assertEqual(a.capsule.opts[-3][0], "font")

    def test_tray_tip_updates_only_when_text_changes(self):
        a, h = make_app()
        a._update_tray_tip()
        a._update_tray_tip()
        self.assertEqual(len(a.tray.tips), 1)
        self.assertEqual(a.tray.tips[0], "الأذكار\nالعصر بعد 47 د")
        h["now"] = h["now"] + timedelta(seconds=20)
        a._update_tray_tip()
        self.assertEqual(len(a.tray.tips), 1)                   # نفس الدقيقة
        h["now"] = h["now"] + timedelta(minutes=5)
        a._update_tray_tip()
        self.assertEqual(len(a.tray.tips), 2)

    def test_tray_tip_shows_iqama_and_hours(self):
        a, h = make_app(now=at(2026, 8, 12, 3, 0))
        a._update_tray_tip()
        self.assertIn("الفجر بعد 1 س", a.tray.tips[-1])
        h["now"] = a.engine.day_times(date(2026, 8, 12))["asr"] + timedelta(minutes=5)
        a._update_tray_tip()
        self.assertIn("إقامة العصر بعد 15 د", a.tray.tips[-1])


class AutoLocationPolicy(unittest.TestCase):
    AUTO_EMPTY = {"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""}
    AUTO_SAVED = {"mode": "auto", "name": "الرياض", "lat": 24.71, "lon": 46.67, "tz": "Asia/Riyadh",
                  "source": "ip"}
    KHOBAR = {"name": "الخبر", "lat": 26.2794, "lon": 50.2083, "tz": "Asia/Riyadh", "source": "windows",
              "accuracy_m": 60.0, "approx": False}

    def test_accurate_windows_location_replaces_the_saved_riyadh_estimate(self):
        a, _ = make_app(location=self.AUTO_SAVED)
        a._on_auto_location(dict(self.KHOBAR), "")
        loc = a.prayer_cfg["location"]
        self.assertEqual((loc["name"], loc["source"], loc["accuracy_m"]), ("الخبر", "windows", 60.0))
        self.assertAlmostEqual(loc["lat"], 26.2794)
        saved = json.loads(app_mod.data_file().read_text(encoding="utf-8"))
        self.assertEqual(saved["prayer"]["location"]["source"], "windows")
        self.assertEqual(len(a.window.prayer_tab.reloads), 1)      # التبويب يعرض الموقع الجديد
        self.assertEqual(a.engine.cfg["location"]["lat"], loc["lat"])

    def test_same_accurate_location_does_not_resave_or_reload_tab(self):
        a, _ = make_app(location=dict(self.AUTO_SAVED, **{k: self.KHOBAR[k] for k in
                                                         ("name", "lat", "lon", "tz", "source", "accuracy_m")}))
        a._on_auto_location(dict(self.KHOBAR), "")
        self.assertEqual(a.window.prayer_tab.reloads, [])

    def test_approximate_estimate_never_replaces_a_saved_location(self):
        a, _ = make_app(location=dict(self.AUTO_SAVED, name="الخبر", lat=26.28, lon=50.2, source="windows"))
        a._on_auto_location({"name": "Riyadh", "lat": 24.7, "lon": 46.7, "tz": "Asia/Riyadh",
                             "source": "ip", "accuracy_m": None, "approx": True}, "تعذّر")
        self.assertEqual(a.prayer_cfg["location"]["name"], "الخبر")
        self.assertEqual((a.tray.messages, a.window.prayer_tab.reloads), ([], []))

    def test_approximate_estimate_is_used_only_when_nothing_else_exists_and_user_is_warned(self):
        a, _ = make_app(location=self.AUTO_EMPTY)
        a._on_auto_location({"name": "Riyadh", "lat": 24.7, "lon": 46.7, "tz": "Asia/Riyadh",
                             "source": "ip", "accuracy_m": None, "approx": True}, "")
        self.assertEqual(a.prayer_cfg["location"]["source"], "ip")
        self.assertEqual(len(a.tray.messages), 1)
        self.assertIn("تقدير تقريبي", a.tray.messages[0][1])
        self.assertIn("يدوياً", a.tray.messages[0][1])

    def test_missing_timezone_keeps_known_one_only_when_location_barely_moved(self):
        a, _ = make_app(location=dict(self.AUTO_SAVED, source="windows"))
        near = dict(self.KHOBAR, lat=24.72, lon=46.68, tz="")          # ~1.5 كم عن المحفوظ
        a._on_auto_location(near, "")
        self.assertEqual(a.prayer_cfg["location"]["tz"], "Asia/Riyadh")
        far = dict(self.KHOBAR, tz="")                                  # الخبر: يبعد ~380 كم
        a._on_auto_location(far, "")
        self.assertEqual(a.prayer_cfg["location"]["tz"], "")            # توقيت النظام أصحّ من تخمين خاطئ

    def test_manual_mode_is_never_touched_by_detection(self):
        a, _ = make_app()
        before = json.dumps(a.prayer_cfg, sort_keys=True)
        a._on_auto_location(dict(self.KHOBAR), "")
        self.assertEqual(json.dumps(a.prayer_cfg, sort_keys=True), before)
        self.assertEqual(a.window.prayer_tab.reloads, [])


class DisplayFormatsInApp(unittest.TestCase):
    def test_capsule_receives_countdown_format_from_config(self):
        a, _ = make_app()
        a.apply_prayer_config(cfg_dict(countdown_format="minutes"))
        self.assertEqual(a.capsule.fmt, "minutes")
        a.apply_prayer_config(cfg_dict(countdown_format="seconds"))
        self.assertEqual(a.capsule.fmt, "seconds")

    def test_status_message_follows_countdown_format(self):
        a, _ = make_app(countdown_format="minutes")
        a.show_prayer_status()
        self.assertEqual(a.capsule.shown[-1], ("العصر بعد 0:47", "prayer"))
        b, _ = make_app(countdown_format="seconds")
        b.show_prayer_status()
        self.assertEqual(b.capsule.shown[-1], ("العصر بعد 47:00", "prayer"))

    def test_display_formats_are_persisted_to_disk(self):
        a, _ = make_app()
        a.apply_prayer_config(cfg_dict(time_format="12", countdown_format="minutes"))
        saved = json.loads(app_mod.data_file().read_text(encoding="utf-8"))["prayer"]
        self.assertEqual((saved["time_format"], saved["countdown_format"]), ("12", "minutes"))
        self.assertEqual(app_mod.load_data()["prayer"]["time_format"], "12")


class StructuralGuards(unittest.TestCase):
    """حراسة بنيوية بالـ AST: لا مؤقتات ولا اتصالات إضافية عند فتح الإعدادات مراراً."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((SRC / "adhkar_app.py").read_text(encoding="utf-8"))

    def _cls(self, name):
        return next(n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == name)

    @staticmethod
    def _calls(node, func_name):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call)
                and ((isinstance(n.func, ast.Name) and n.func.id == func_name)
                     or (isinstance(n.func, ast.Attribute) and n.func.attr == func_name))]

    def test_app_creates_exactly_two_timers_once_in_init(self):
        app_cls = self._cls("AdhkarApp")
        init = next(n for n in app_cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        self.assertEqual(len(self._calls(init, "QTimer")), 2)        # الأذكار + الصلاة
        others = [n for n in app_cls.body if isinstance(n, ast.FunctionDef) and n.name != "__init__"]
        for fn in others:
            self.assertEqual(self._calls(fn, "QTimer"), [], fn.name)  # لا مؤقتات في أي دالة أخرى

    def test_no_dialog_anymore_and_tab_is_created_exactly_once(self):
        app_cls = self._cls("AdhkarApp")
        names = {n.name for n in app_cls.body if isinstance(n, ast.FunctionDef)}
        self.assertNotIn("open_prayer_dialog", names)
        win = self._cls("SettingsWindow")
        init = next(n for n in win.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        self.assertEqual(len(self._calls(init, "PrayerTab")), 1)
        others = [n for n in win.body if isinstance(n, ast.FunctionDef) and n.name != "__init__"]
        for fn in others:
            self.assertEqual(self._calls(fn, "PrayerTab"), [], fn.name)     # لا إنشاء عند التبديل بين التبويبين

    def test_tab_has_a_single_timer_and_switching_tabs_creates_none(self):
        tab = self._cls("PrayerTab")
        init = next(n for n in tab.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        self.assertEqual(len(self._calls(init, "QTimer")), 1)
        for fn in [n for n in tab.body if isinstance(n, ast.FunctionDef) and n.name != "__init__"]:
            self.assertEqual(self._calls(fn, "QTimer"), [], fn.name)        # (singleShot ليست إنشاء مؤقت)
        win = self._cls("SettingsWindow")
        switch = next(n for n in win.body if isinstance(n, ast.FunctionDef) and n.name == "_switch_tab")
        self.assertEqual(self._calls(switch, "QTimer"), [])

    def test_tab_timer_runs_only_while_visible(self):
        tab = self._cls("PrayerTab")
        src = {n.name: ast.unparse(n) for n in tab.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("self._tick.start()", src["showEvent"])
        self.assertIn("self._tick.stop()", src["hideEvent"])

    def test_no_raw_wheel_sensitive_widgets_anywhere(self):
        for name in ("QSpinBox", "QDoubleSpinBox", "QComboBox"):
            self.assertEqual(self._calls(self.tree, name), [], name)       # فقط النسخ الآمنة (NoWheel*)

    def test_wheel_guard_classes_ignore_wheel_events_and_avoid_wheel_focus(self):
        for name in ("NoWheelSpinBox", "NoWheelDoubleSpinBox", "NoWheelComboBox"):
            cls = self._cls(name)
            wheel = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "wheelEvent")
            self.assertIn("event.ignore()", ast.unparse(wheel))
            init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
            self.assertIn("setFocusPolicy(Qt.StrongFocus)", ast.unparse(init))

    def test_every_numeric_and_combo_field_is_built_with_a_wheel_guard(self):
        win, tab = self._cls("SettingsWindow"), self._cls("PrayerTab")
        # النافذة الرئيسية: فاصل الأذكار + مدة الإشعار + حجما الخط
        self.assertEqual(len(self._calls(win, "NoWheelSpinBox")), 4)
        # التبويب: كل الخانات الرقمية تُبنى عبر _spin (نقطة واحدة)، والقوائم والإحداثيات مباشرة
        helper = next(n for n in tab.body if isinstance(n, ast.FunctionDef) and n.name == "_spin")
        self.assertEqual(len(self._calls(helper, "NoWheelSpinBox")), 1)
        self.assertEqual(len(self._calls(tab, "NoWheelComboBox")), 2)
        self.assertEqual(len(self._calls(tab, "NoWheelDoubleSpinBox")), 2)
        # كل مواضع استخدام _spin: التنبيه المسبق + 5 تعديلات + 5 إقامات (عبر حلقتين)
        self.assertEqual(len(self._calls(tab, "_spin")), 3)

    def test_radio_groups_are_explicit_so_option_sets_do_not_interfere(self):
        tab = self._cls("PrayerTab")
        group = next(n for n in tab.body if isinstance(n, ast.FunctionDef) and n.name == "_radio_group")
        self.assertIn("QButtonGroup", ast.unparse(group))
        gen = next(n for n in tab.body if isinstance(n, ast.FunctionDef) and n.name == "_build_general_card")
        self.assertEqual(len(self._calls(gen, "_radio_group")), 3)         # العرض + نظام الساعة + صيغة العدّاد

    def test_worker_signals_connect_to_qobject_methods_not_lambdas(self):
        for c in self._calls(self.tree, "connect"):
            if isinstance(c.func, ast.Attribute) and c.func.attr == "connect":
                tgt = c.func.value
                if isinstance(tgt, ast.Attribute) and tgt.attr == "done":
                    self.assertFalse(isinstance(c.args[0], ast.Lambda))


if __name__ == "__main__":
    unittest.main()
