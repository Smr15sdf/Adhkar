# -*- coding: utf-8 -*-
"""اختبار منطق تبويب مواقيت الصلاة (PrayerTab) بأدوات واجهة مزيّفة بسيطة (بدون Qt).

نختبر هنا: العدّاد الحي وصيغ الساعة والوقت المتبقي، وتدفقات الموقع (تلقائي/تقدير/يدوي/إحداثيات)،
وجمع النموذج وحفظه وإعادة تحميله. الرسم والتخطيط الفعلي لا يُختبران هنا (راجع TESTING_WINDOWS.md).
"""
import copy
import importlib
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import qt_stub  # noqa: E402

qt_stub.install()
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="adhkar_tab_")
app = importlib.import_module("adhkar_app")
import prayer_times as pt  # noqa: E402

RIYADH = ZoneInfo("Asia/Riyadh")


def at(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=RIYADH)


# ---------------------------------------------------------------- أدوات مزيّفة
class FW:
    """عنصر واجهة مزيّف عام."""

    def __init__(self, text="", value=0, checked=False):
        self._text, self._value, self.checked = text, value, checked
        self.enabled, self.visible, self.style_sheet = True, True, ""
        self.props, self.cleared, self.items = {}, 0, []

    def setText(self, t): self._text = t
    def text(self): return self._text
    def value(self): return self._value
    def setValue(self, v): self._value = v
    def isChecked(self): return self.checked
    def setEnabled(self, b): self.enabled = bool(b)
    def setVisible(self, b): self.visible = bool(b)
    def setStyleSheet(self, s): self.style_sheet = s
    def clear(self): self.cleared += 1; self.items = []
    def addItem(self, it): self.items.append(it)
    def property(self, k): return self.props.get(k)
    def setProperty(self, k, v): self.props[k] = v
    def style(self): return SimpleNamespace(unpolish=lambda w: None, polish=lambda w: None)

    def setChecked(self, b):
        self.checked = bool(b)


class Radio(FW):
    def __init__(self, group):
        super().__init__()
        self.group = group
        group.append(self)

    def setChecked(self, b):
        if b:
            for r in self.group:
                r.checked = False
        self.checked = bool(b)


class Combo(FW):
    def __init__(self, items):
        super().__init__()
        self.data_items, self.index = items, 0

    def currentData(self): return self.data_items[self.index][1]
    def findData(self, key): return next((i for i, (_, k) in enumerate(self.data_items) if k == key), -1)
    def setCurrentIndex(self, i): self.index = i


class FakeGeo:
    def __init__(self):
        self.detects, self.searches, self.resolves = 0, [], []
        self.detect_returns = True

    def detect(self):
        self.detects += 1
        return self.detect_returns

    def search(self, q): self.searches.append(q)
    def resolve(self, lat, lon): self.resolves.append((lat, lon))


class Item:
    def __init__(self, loc): self.loc = loc
    def data(self, role): return self.loc


KHOBAR = {"name": "الخبر", "lat": 26.2794, "lon": 50.2083, "tz": "Asia/Riyadh", "source": "windows",
          "accuracy_m": 60.0, "approx": False}
RIYADH_EST = {"name": "Riyadh", "lat": 24.7136, "lon": 46.6753, "tz": "Asia/Riyadh", "source": "ip",
              "accuracy_m": None, "approx": True}


def base_cfg(**over):
    raw = {"enabled": True, "location": {"mode": "manual", "name": "مكة", "lat": 21.4225, "lon": 39.8262,
                                         "tz": "Asia/Riyadh", "source": "search"}}
    raw.update(over)
    return pt.sanitize_config(raw)


def make_tab(now=None, **over):
    cfg = base_cfg(**over)
    tab = app.PrayerTab.__new__(app.PrayerTab)
    holder = {"now": now or at(2026, 8, 12, 15, 0)}
    applied = []
    tab._ctx = SimpleNamespace(cfg=cfg, on_apply=lambda c: applied.append(c), on_test=lambda *a: None,
                               now_fn=lambda: holder["now"], sound=None)
    tab._cfg = pt.sanitize_config(cfg)
    tab._applied = copy.deepcopy(tab._cfg)
    tab._loading = False
    tab._pending_estimate = None
    tab._tf, tab._cf = tab._cfg["time_format"], tab._cfg["countdown_format"]
    tab._preview = pt.PrayerEngine(dict(tab._cfg, enabled=True), None, tab._ctx.now_fn)

    tab.enabled_chk = FW()
    g1, g2, g3, g4 = [], [], [], []
    tab.mode_rbs = {k: Radio(g1) for k in pt.DISPLAY_MODES}
    tab.tf_rbs = {k: Radio(g2) for k in pt.TIME_FORMATS}
    tab.cd_rbs = {k: Radio(g3) for k in pt.COUNTDOWN_FORMATS}
    tab.auto_rb, tab.manual_rb = Radio(g4), Radio(g4)
    tab.method_cb = Combo([(n, k) for k, (n, _, _) in pt.METHODS.items()])
    tab.asr_cb = Combo([(n, k) for k, n in pt.ASR_LABELS.items()])
    tab.adjust_spins = {p: FW() for p in pt.PRAYERS}
    tab.iqama_spins = {p: FW() for p in pt.PRAYERS}
    tab.pre_chk, tab.pre_spin, tab.adhan_chk = FW(), FW(), FW()
    tab.sound_chk, tab.sound_path = FW(), FW()
    tab.lat_spin, tab.lon_spin = FW(), FW()
    for name in ("detect_btn", "use_est_btn", "city_input", "search_btn", "results", "coord_btn",
                 "loc_line", "geo_status", "next_label", "dirty_label", "save_status"):
        setattr(tab, name, FW())
    tab.time_boxes = {p: (FW(), FW()) for p in pt.PRAYERS}
    tab.geo = FakeGeo()
    tab._populate(tab._cfg)
    tab._on_form_changed()
    return tab, holder, applied


def times_text(tab):
    return {p: lbl.text() for p, (_, lbl) in tab.time_boxes.items()}


def active(tab):
    return [p for p, (box, _) in tab.time_boxes.items() if box.property("active")]


# ---------------------------------------------------------------- الاختبارات
class LiveStripTests(unittest.TestCase):
    def test_24h_seconds_default(self):
        tab, _, _ = make_tab()
        self.assertEqual(tab.next_label.text(), "العصر بعد 47:00")
        self.assertEqual(times_text(tab), {"fajr": "04:37", "dhuhr": "12:26", "asr": "15:47",
                                           "maghrib": "18:53", "isha": "20:23"})
        self.assertEqual(active(tab), ["asr"])

    def test_12h_clock_and_minutes_countdown(self):
        tab, _, _ = make_tab(time_format="12", countdown_format="minutes")
        self.assertEqual(tab.next_label.text(), "العصر بعد 0:47")
        self.assertEqual(times_text(tab), {"fajr": "4:37 ص", "dhuhr": "12:26 م", "asr": "3:47 م",
                                           "maghrib": "6:53 م", "isha": "8:23 م"})

    def test_switching_formats_updates_live_without_saving(self):
        tab, _, applied = make_tab()
        tab.tf_rbs["12"].setChecked(True)
        tab._on_form_changed()
        self.assertEqual(times_text(tab)["asr"], "3:47 م")
        tab.cd_rbs["minutes"].setChecked(True)
        tab._on_form_changed()
        self.assertEqual(tab.next_label.text(), "العصر بعد 0:47")
        self.assertEqual(applied, [])                              # لم يُحفظ شيء بعد
        self.assertTrue(tab.dirty_label.text())
        tab.tf_rbs["24"].setChecked(True)
        tab.cd_rbs["seconds"].setChecked(True)
        tab._on_form_changed()
        self.assertEqual(tab.dirty_label.text(), "")               # عاد كما حُفظ

    def test_countdown_advances_each_tick(self):
        tab, h, _ = make_tab()
        h["now"] += timedelta(seconds=1)
        tab._refresh_strip()
        self.assertEqual(tab.next_label.text(), "العصر بعد 46:59")
        h["now"] += timedelta(minutes=46, seconds=59)
        tab._refresh_strip()
        self.assertIn("إقامة العصر بعد 20:00", tab.next_label.text())     # بدأت الإقامة عند الأذان
        self.assertEqual(active(tab), ["asr"])

    def test_after_isha_next_is_tomorrow_and_shows_tomorrows_time(self):
        tab, h, _ = make_tab(now=at(2026, 8, 12, 21, 0))
        eng = tab._preview
        tomorrow_fajr = eng.day_times(date(2026, 8, 13))["fajr"]
        self.assertEqual(active(tab), ["fajr"])
        self.assertEqual(tab._tf, "24")
        self.assertEqual(times_text(tab)["fajr"], pt.format_clock(tomorrow_fajr, "24"))
        self.assertTrue(tab.next_label.text().startswith("الفجر بعد "))

    def test_no_location_shows_placeholders(self):
        tab, _, _ = make_tab(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        self.assertEqual(tab.next_label.text(), "حدّد موقعك لعرض المواقيت")
        self.assertEqual(set(times_text(tab).values()), {"--:--"})
        self.assertEqual(active(tab), [])
        self.assertEqual(tab.loc_line.text(), "لم يتم تحديد موقع بعد")

    def test_strip_reflects_unsaved_adjustments_live(self):
        tab, _, _ = make_tab()
        tab.adjust_spins["asr"].setValue(10)
        tab._on_form_changed()
        self.assertEqual(times_text(tab)["asr"], "15:57")
        self.assertEqual(tab.next_label.text(), "العصر بعد 57:00")


class FormTests(unittest.TestCase):
    def test_collect_roundtrips_through_populate(self):
        cfg = base_cfg(display_mode="side", time_format="12", countdown_format="minutes", method="isna",
                       asr="hanafi", pre_minutes=9, adjust={"fajr": 3, "asr": -2},
                       iqama_minutes={"fajr": 25, "dhuhr": 15, "asr": 12, "maghrib": 8, "isha": 35},
                       sound={"enabled": True, "path": "C:/a.mp3"}, notify_adhan=False)
        tab, _, _ = make_tab(**{k: v for k, v in cfg.items()})
        self.assertEqual(tab._collect(), cfg)
        self.assertEqual(tab.dirty_label.text(), "")

    def test_save_applies_collected_config_and_clears_dirty(self):
        tab, _, applied = make_tab()
        tab.mode_rbs["side"].setChecked(True)
        tab.tf_rbs["12"].setChecked(True)
        tab._on_form_changed()
        self.assertTrue(tab.dirty_label.text())
        tab._save()
        self.assertEqual(len(applied), 1)
        self.assertEqual((applied[0]["display_mode"], applied[0]["time_format"]), ("side", "12"))
        self.assertEqual(tab.dirty_label.text(), "")
        self.assertEqual(tab.save_status.text(), "تم الحفظ ✓")
        self.assertEqual(tab._applied, applied[0])

    def test_radio_sets_are_independent(self):
        tab, _, _ = make_tab()
        tab.mode_rbs["stack"].setChecked(True)
        tab.tf_rbs["12"].setChecked(True)
        tab.cd_rbs["minutes"].setChecked(True)
        cfg = tab._collect()
        self.assertEqual((cfg["display_mode"], cfg["time_format"], cfg["countdown_format"]),
                         ("stack", "12", "minutes"))
        self.assertTrue(tab.mode_rbs["stack"].isChecked() and tab.tf_rbs["12"].isChecked())

    def test_manual_and_auto_enable_the_right_controls(self):
        tab, _, _ = make_tab()                                    # يدوي
        self.assertTrue(tab.city_input.enabled and tab.lat_spin.enabled and tab.coord_btn.enabled)
        self.assertFalse(tab.detect_btn.enabled)
        tab.auto_rb.setChecked(True)
        tab._update_location_ui()
        self.assertFalse(tab.city_input.enabled or tab.lat_spin.enabled or tab.results.enabled)
        self.assertTrue(tab.detect_btn.enabled)

    def test_switching_to_auto_detects_once_and_to_manual_does_not(self):
        tab, _, _ = make_tab()
        tab.auto_rb.setChecked(True)
        tab._on_mode_toggled(True)
        self.assertEqual(tab.geo.detects, 1)
        tab.manual_rb.setChecked(True)
        tab._on_mode_toggled(False)
        self.assertEqual(tab.geo.detects, 1)


class LocationFlowTests(unittest.TestCase):
    def auto_tab(self, **over):
        tab, h, applied = make_tab(location={"mode": "auto", "name": "الرياض", "lat": 24.7136, "lon": 46.6753,
                                             "tz": "Asia/Riyadh", "source": "ip"}, **over)
        return tab, h, applied

    def test_accurate_windows_result_is_applied_with_source_and_accuracy(self):
        tab, _, _ = self.auto_tab()
        tab._on_detected(dict(KHOBAR), "")
        loc = tab._cfg["location"]
        self.assertEqual((loc["name"], loc["source"], loc["accuracy_m"]), ("الخبر", "windows", 60.0))
        self.assertAlmostEqual(loc["lat"], 26.2794)
        self.assertIn("تم تحديد موقعك: الخبر", tab.geo_status.text())
        self.assertIn("الدقة ≈ 60 م", tab.geo_status.text())
        self.assertFalse(tab.use_est_btn.visible)
        self.assertIn("الخبر", tab.loc_line.text())
        self.assertAlmostEqual(tab.lat_spin.value(), 26.2794)         # حقلا الإحداثيات يتبعان
        self.assertTrue(tab.dirty_label.text())                       # تغيير لم يُحفظ بعد

    def test_approximate_result_is_only_offered_never_applied(self):
        tab, _, _ = self.auto_tab()
        tab._on_detected(dict(RIYADH_EST), "خدمة الموقع غير متاحة")
        self.assertEqual(tab._cfg["location"]["name"], "الرياض")      # لم يتغير
        self.assertTrue(tab.use_est_btn.visible)
        self.assertIn("تقدير", tab.geo_status.text())
        self.assertIn("Riyadh", tab.geo_status.text())
        self.assertIn("يدوياً", tab.geo_status.text())
        tab._use_estimate()
        self.assertEqual(tab._cfg["location"]["source"], "ip")
        self.assertFalse(tab.use_est_btn.visible)

    def test_estimate_button_visibility_follows_state(self):
        tab, _, _ = self.auto_tab()
        self.assertFalse(tab.use_est_btn.visible)                      # مخفي افتراضياً
        tab._on_detected(dict(RIYADH_EST), "")
        self.assertTrue(tab.use_est_btn.visible)
        tab._start_detect()                                            # محاولة جديدة تُسقط التقدير القديم
        self.assertFalse(tab.use_est_btn.visible)
        tab._on_detected(dict(RIYADH_EST), "")
        tab._on_detected(dict(KHOBAR), "")                             # نتيجة دقيقة لاحقة تلغي التقدير
        self.assertFalse(tab.use_est_btn.visible)
        self.assertIsNone(tab._pending_estimate)

    def test_stale_estimate_cannot_be_applied_after_switching_to_manual(self):
        tab, _, _ = self.auto_tab()
        tab._on_detected(dict(RIYADH_EST), "")
        tab.manual_rb.setChecked(True)
        tab._on_mode_toggled(False)
        self.assertFalse(tab.use_est_btn.visible)
        before = copy.deepcopy(tab._cfg["location"])
        tab._use_estimate()                                            # حتى لو وصل نقر متأخر
        self.assertEqual(tab._cfg["location"], before)

    def test_use_estimate_is_refused_in_manual_mode_even_if_a_stale_one_is_pending(self):
        tab, _, _ = make_tab()                                         # يدوي
        tab._pending_estimate = dict(RIYADH_EST)                       # حالة غير متوقعة (دفاع إضافي)
        before = copy.deepcopy(tab._cfg["location"])
        tab._use_estimate()
        self.assertEqual(tab._cfg["location"], before)
        self.assertIsNone(tab._pending_estimate)

    def test_failure_switches_to_manual_with_a_clear_message(self):
        tab, _, _ = self.auto_tab()
        tab._on_detected(None, "تم رفض الوصول إلى الموقع")
        self.assertTrue(tab.manual_rb.isChecked())
        self.assertIn("تم رفض الوصول", tab.geo_status.text())
        self.assertIn("اختر مدينتك يدوياً", tab.geo_status.text())
        self.assertEqual(tab._cfg["location"]["name"], "الرياض")      # الموقع القديم محفوظ

    def test_result_after_user_chose_manual_is_ignored(self):
        tab, _, _ = make_tab()                                         # يدوي
        before = copy.deepcopy(tab._cfg["location"])
        tab._on_detected(dict(KHOBAR), "")
        self.assertEqual(tab._cfg["location"], before)

    def test_choosing_a_city_sets_source_search_and_updates_strip(self):
        tab, _, _ = make_tab()
        tab._choose_city(Item({"name": "الخبر، المنطقة الشرقية، السعودية", "lat": 26.2794, "lon": 50.2083,
                               "tz": "Asia/Riyadh"}))
        loc = tab._cfg["location"]
        self.assertEqual((loc["source"], loc["accuracy_m"], loc["lat"]), ("search", None, 26.2794))
        self.assertNotEqual(times_text(tab)["fajr"], "04:37")         # مواقيت الخبر غير مكة
        self.assertIn("تم اختيار", tab.geo_status.text())

    def test_search_results_and_errors(self):
        tab, _, _ = make_tab()
        tab.city_input.setText("الخبر")
        tab._search()
        self.assertEqual(tab.geo.searches, ["الخبر"])
        tab._on_searched([{"name": "الخبر", "lat": 1.0, "lon": 2.0, "tz": ""}], "")
        self.assertEqual(len(tab.results.items), 1)
        tab._on_searched([], "لا توجد نتائج مطابقة")
        self.assertIn("لا توجد نتائج", tab.geo_status.text())
        tab.auto_rb.setChecked(True)
        tab._search()
        self.assertEqual(tab.geo.searches, ["الخبر"])                  # لا بحث في الوضع التلقائي

    def test_manual_coordinates_flow_with_background_resolution(self):
        tab, _, _ = make_tab()
        tab.lat_spin.setValue(0.0)
        tab.lon_spin.setValue(0.0)
        tab._apply_coords()
        self.assertEqual(tab.geo.resolves, [])
        self.assertIn("أدخل", tab.geo_status.text())
        tab.lat_spin.setValue(26.2794)
        tab.lon_spin.setValue(50.2083)
        tab._apply_coords()
        loc = tab._cfg["location"]
        self.assertEqual((loc["source"], loc["lat"], loc["tz"]), ("coords", 26.2794, ""))
        self.assertEqual(tab.geo.resolves, [(26.2794, 50.2083)])
        tab._on_resolved({"name": "الخبر، السعودية", "tz": "Asia/Riyadh", "lat": 26.2794, "lon": 50.2083}, "")
        self.assertEqual((loc["name"], loc["tz"]), ("الخبر، السعودية", "Asia/Riyadh"))

    def test_stale_or_foreign_resolution_results_are_ignored(self):
        tab, _, _ = make_tab()
        tab.lat_spin.setValue(26.2794)
        tab.lon_spin.setValue(50.2083)
        tab._apply_coords()
        tab._on_resolved({"name": "قديم", "tz": "Europe/London", "lat": 51.5, "lon": -0.1}, "")
        self.assertEqual(tab._cfg["location"]["tz"], "")
        tab._on_resolved(None, "خطأ")
        self.assertEqual(tab._cfg["location"]["name"], "26.279, 50.208")
        tab._choose_city(Item({"name": "مكة", "lat": 21.4, "lon": 39.8, "tz": "Asia/Riyadh"}))   # صار المصدر search
        tab._on_resolved({"name": "متأخر", "tz": "Asia/Tokyo", "lat": 21.4, "lon": 39.8}, "")
        self.assertEqual(tab._cfg["location"]["tz"], "Asia/Riyadh")

    def test_start_detect_guards(self):
        tab, _, _ = make_tab()
        tab._start_detect()
        self.assertFalse(tab.detect_btn.enabled)
        self.assertIn("جارٍ تحديد", tab.geo_status.text())
        tab.geo.detect_returns = False
        tab._start_detect()
        self.assertIn("ما زال", tab.geo_status.text())


class ExternalReloadTests(unittest.TestCase):
    def test_reload_when_clean_replaces_everything(self):
        tab, _, _ = make_tab()
        new = base_cfg(display_mode="side", time_format="12",
                       location={"mode": "auto", "name": "الخبر", "lat": 26.2794, "lon": 50.2083,
                                 "tz": "Asia/Riyadh", "source": "windows", "accuracy_m": 55.0})
        tab.reload(new)
        self.assertEqual(tab._collect(), new)
        self.assertEqual(tab.dirty_label.text(), "")
        self.assertTrue(tab.auto_rb.isChecked())

    def test_reload_with_unsaved_edits_updates_only_the_location(self):
        tab, _, _ = make_tab()
        tab.mode_rbs["side"].setChecked(True)
        tab.adjust_spins["fajr"].setValue(5)
        tab._on_form_changed()
        new = base_cfg(location={"mode": "manual", "name": "الخبر", "lat": 26.2794, "lon": 50.2083,
                                 "tz": "Asia/Riyadh", "source": "windows", "accuracy_m": 55.0})
        tab.reload(new)
        cfg = tab._collect()
        self.assertEqual(cfg["display_mode"], "side")                   # ما كتبه المستخدم باقٍ
        self.assertEqual(cfg["adjust"]["fajr"], 5)
        self.assertEqual(cfg["location"]["name"], "الخبر")              # والموقع الجديد دخل
        self.assertTrue(tab.dirty_label.text())                         # ما زال لديه تعديلات غير محفوظة


if __name__ == "__main__":
    unittest.main()
