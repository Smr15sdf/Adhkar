# -*- coding: utf-8 -*-
"""اختبار حسابات تخطيط الكبسولة ومنطق أوضاع العرض بقياسات خطوط مزيّفة (بدون Qt).

قياسات الخط هنا تقريبية، لكن العلاقات المختبَرة (عدم التداخل، الاحتواء، اتساع أطول عدّاد) لا تعتمد
على دقتها. الرسم الفعلي والحركة وتمرير الماوس تُختبر يدوياً على ويندوز.
"""
import importlib
import math
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import qt_stub  # noqa: E402

qt_stub.install()
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="adhkar_cap_")
app = importlib.import_module("adhkar_app")
import prayer_times as pt  # noqa: E402


class FRect:
    def __init__(self, x=0, y=0, w=0, h=0):
        self._x, self._y, self._w, self._h = x, y, w, h

    def x(self): return self._x
    def y(self): return self._y
    def width(self): return self._w
    def height(self): return self._h
    def right(self): return self._x + self._w
    def bottom(self): return self._y + self._h


class FFont:
    def __init__(self, family="x", size=12):
        self.family, self.size = family, size


class FFM:
    def __init__(self, font):
        self.f = font

    def horizontalAdvance(self, text):
        return int(len(text) * self.f.size * 0.6)

    def height(self):
        return int(self.f.size * 1.9)

    def boundingRect(self, rect, flags, text):
        w = max(1, rect.width())
        lines = max(1, math.ceil(self.horizontalAdvance(text) / w))
        return FRect(0, 0, min(w, self.horizontalAdvance(text)), lines * self.height())


class Geo:
    def __init__(self, w=1920):
        self._w = w

    def width(self):
        return self._w


def make_capsule(size=16, mode_cfg="none", info_fn=None):
    c = app.CapsuleNotification.__new__(app.CapsuleNotification)
    c._family, c._size, c._font = "x", size, FFont("x", size)
    c._mode_cfg, c._info_fn, c._countdown_fmt = mode_cfg, info_fn, "seconds"
    c._info, c._eff_mode, c._kind = None, "none", "dhikr"
    c._dismissing, c._hover_paused, c._seq, c._mix = False, False, None, 0.0
    c._radius, c._layout = 30.0, {}
    return c


TEXTS = {
    "short": "اللَّهُ أَكْبَرُ",
    "medium": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ",
    "long": ("لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ "
             "وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ"),
}


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self._saved = (app.QFontMetrics, app.QFont, app.QRect)
        app.QFontMetrics, app.QFont, app.QRect = FFM, FFont, FRect

    def tearDown(self):
        app.QFontMetrics, app.QFont, app.QRect = self._saved

    def test_all_modes_texts_and_font_sizes_produce_consistent_layouts(self):
        geo = Geo(1920)
        for size in (10, 16, 24, 40):
            for mode in ("none", "hover", "stack", "side"):
                for tname, text in TEXTS.items():
                    c = make_capsule(size)
                    w, h = c._measure(text, mode, geo)
                    tag = f"size={size} mode={mode} text={tname}"
                    L = c._layout
                    self.assertGreaterEqual(h, 64, tag)
                    self.assertGreaterEqual(w, 260, tag)
                    self.assertLessEqual(w, geo.width(), tag)
                    self.assertGreater(c._radius, 0, tag)
                    for key in ("dhikr", "info"):
                        if key in L:
                            r = L[key]
                            self.assertGreaterEqual(r.x(), 0, tag + key)
                            self.assertGreaterEqual(r.y(), 0, tag + key)
                            self.assertLessEqual(r.right(), w, tag + key)
                            self.assertLessEqual(r.bottom(), h, tag + key)
                            self.assertGreater(r.width(), 0, tag + key)
                            self.assertGreater(r.height(), 0, tag + key)

    def test_side_mode_info_divider_and_dhikr_do_not_overlap_and_rtl_order(self):
        for size in (10, 16, 24, 40):
            c = make_capsule(size)
            w, h = c._measure(TEXTS["long"], "side", Geo())
            L = c._layout
            self.assertLess(L["info"].right(), L["divider_x"])
            self.assertLess(L["divider_x"], L["dhikr"].x())       # الذكر على اليمين والمعلومات على اليسار
            # عدّاد 8:88:88 والاسم الأطول يتسعان في منطقة المعلومات
            cfm = FFM(L["cd_font"])
            self.assertLessEqual(cfm.horizontalAdvance("8:88:88"), L["info"].width())
            nfm = FFM(L["name_font"])
            for p in pt.PRAYERS:
                self.assertLessEqual(nfm.horizontalAdvance("إقامة " + pt.PRAYER_AR[p]), L["info"].width())
            self.assertGreaterEqual(L["info"].height(), L["name_h"] + 2 + L["cd_h"] - 1)

    def test_stack_mode_info_is_below_dhikr_and_fits_worst_case_line(self):
        for size in (10, 16, 24, 40):
            c = make_capsule(size)
            w, h = c._measure(TEXTS["medium"], "stack", Geo())
            L = c._layout
            self.assertGreaterEqual(L["info"].y(), L["dhikr"].bottom())
            ifm = FFM(L["info_font"])
            for line in c._worst_lines(False):
                self.assertLessEqual(ifm.horizontalAdvance(line), L["info"].width(), line)

    def test_hover_mode_reserves_room_for_info_and_reasons(self):
        for size in (10, 16, 24, 40):
            c = make_capsule(size)
            w, h = c._measure(TEXTS["short"], "hover", Geo())
            L = c._layout
            self.assertEqual((L["dhikr"].x(), L["dhikr"].y()), (L["info"].x(), L["info"].y()))
            fm = FFM(c._font)
            for line in c._worst_lines(True):
                self.assertLessEqual(fm.horizontalAdvance(line), L["info"].width(), line)

    def test_capsule_size_is_stable_when_digits_change(self):
        # القياس يعتمد على أسوأ صيغة (8:88:88) لا على الوقت الحالي: الحجم ثابت أثناء العدّ
        a = make_capsule(16)
        b = make_capsule(16)
        self.assertEqual(a._measure(TEXTS["medium"], "stack", Geo()), b._measure(TEXTS["medium"], "stack", Geo()))
        self.assertEqual(a._worst_lines(False), b._worst_lines(False))

    def test_narrow_screen_does_not_overflow_in_side_mode(self):
        c = make_capsule(16)
        w, h = c._measure(TEXTS["long"], "side", Geo(1024))
        self.assertLessEqual(w, 1024)


class MinutesFormatLayoutTests(unittest.TestCase):
    def setUp(self):
        self._saved = (app.QFontMetrics, app.QFont, app.QRect)
        app.QFontMetrics, app.QFont, app.QRect = FFM, FFont, FRect

    def tearDown(self):
        app.QFontMetrics, app.QFont, app.QRect = self._saved

    def test_minutes_format_samples_include_the_widest_text(self):
        c = make_capsule(16)
        c._countdown_fmt = "minutes"
        self.assertIn(pt.LESS_THAN_MINUTE, c._samples())
        self.assertTrue(any(pt.LESS_THAN_MINUTE in line for line in c._worst_lines(False)))
        c._countdown_fmt = "seconds"
        self.assertEqual(c._samples(), ["8:88:88"])

    def test_all_modes_fit_worst_case_text_in_minutes_format(self):
        for size in (10, 16, 24, 40):
            for mode in ("hover", "stack", "side"):
                c = make_capsule(size)
                c._countdown_fmt = "minutes"
                w, h = c._measure(TEXTS["medium"], mode, Geo())
                L = c._layout
                self.assertLessEqual(w, 1920)
                if mode == "side":
                    cfm = FFM(L["cd_font"])
                    for x in c._samples():
                        self.assertLessEqual(cfm.horizontalAdvance(x), L["info"].width(), (size, x))
                else:
                    ifm = FFM(L.get("info_font", c._font))
                    for line in c._worst_lines(mode == "hover"):
                        self.assertLessEqual(ifm.horizontalAdvance(line), L["info"].width(), (size, mode, line))


class ModeSelectionTests(unittest.TestCase):
    AVAILABLE = pt.Status("next", "asr", None, 2820)

    def cap(self, mode, status):
        return make_capsule(16, mode, (lambda: status))

    def test_effective_modes(self):
        avail = self.AVAILABLE
        unavail = pt.Status("unavailable", reason="no_location")
        iq = pt.Status("iqama", "fajr", None, 600)
        cases = [
            ("hover", avail, "dhikr", "hover"), ("stack", avail, "dhikr", "stack"),
            ("side", avail, "dhikr", "side"), ("stack", iq, "dhikr", "stack"),
            ("hover", unavail, "dhikr", "hover"),      # يظهر سبب عدم التوفر عند التمرير
            ("stack", unavail, "dhikr", "none"), ("side", unavail, "dhikr", "none"),
            ("hover", avail, "prayer", "none"),        # إشعار الصلاة لا يحمل معلومات إضافية
            ("none", avail, "dhikr", "none"),
            ("hover", pt.Status("disabled"), "dhikr", "none"),
        ]
        for mode, status, kind, expected in cases:
            c = self.cap(mode, status)
            info = c._compute_info()      # نمرّر المعلومات حتى لإشعار الصلاة لنختبر الدالة نفسها
            self.assertEqual(c._effective_mode(kind, info), expected, (mode, status.kind, kind))

    def test_failing_provider_degrades_to_dhikr_only(self):
        def boom():
            raise RuntimeError("x")
        c = make_capsule(16, "side", boom)
        self.assertIsNone(c._compute_info())
        self.assertEqual(c._effective_mode("dhikr", None), "none")

    def test_refresh_updates_only_when_info_changes(self):
        st = {"s": pt.Status("next", "asr", None, 100)}
        c = make_capsule(16, "stack", lambda: st["s"])
        c._info = None
        updates = []
        c.update = lambda: updates.append(1)
        c._refresh_info()
        c._refresh_info()
        self.assertEqual(len(updates), 1)
        st["s"] = pt.Status("next", "asr", None, 99)
        c._refresh_info()
        self.assertEqual(len(updates), 2)

    def test_hover_enter_pauses_and_leave_resumes_only_in_hover_mode(self):
        # QWidget الحقيقي يملك هاتين الدالتين؛ نعرّفهما في البديل لأن super() لا يمرّ عبر __getattr__
        app.QWidget.enterEvent = lambda self, e: None
        app.QWidget.leaveEvent = lambda self, e: None
        app.QAbstractAnimation = types.SimpleNamespace(Running="R", Paused="P")

        class Seq:
            def __init__(self):
                self.st, self.log = "R", []

            def state(self): return self.st
            def pause(self): self.st = "P"; self.log.append("pause")
            def resume(self): self.st = "R"; self.log.append("resume")

        c = make_capsule(16, "hover")
        c._eff_mode, c._seq = "hover", Seq()
        mixes = []
        c._animate_mix = lambda v: mixes.append(v)
        c.enterEvent(None)
        self.assertEqual((c._seq.log, mixes, c._hover_paused), (["pause"], [1.0], True))
        c.leaveEvent(None)
        self.assertEqual((c._seq.log, mixes, c._hover_paused), (["pause", "resume"], [1.0, 0.0], False))

        c2 = make_capsule(16, "stack")
        c2._eff_mode, c2._seq = "stack", Seq()
        c2._animate_mix = lambda v: mixes.append(v)
        c2.enterEvent(None)
        c2.leaveEvent(None)
        self.assertEqual(c2._seq.log, [])                 # لا تأثير للتمرير خارج وضع «الذكر فقط»

        c3 = make_capsule(16, "hover")
        c3._eff_mode, c3._seq, c3._dismissing = "hover", Seq(), True
        c3._animate_mix = lambda v: mixes.append(v)
        c3.enterEvent(None)
        self.assertEqual(c3._seq.log, [])                 # أثناء الإغلاق لا نوقفه

    def test_is_prayer_showing(self):
        c = make_capsule(16)
        c.isVisible = lambda: True
        c._kind = "prayer"
        self.assertTrue(c.is_prayer_showing())
        c._dismissing = True
        self.assertFalse(c.is_prayer_showing())
        c._dismissing, c._kind = False, "dhikr"
        self.assertFalse(c.is_prayer_showing())

    def test_countdown_format_reaches_the_info_text_and_is_validated(self):
        st = pt.Status("next", "asr", None, 47 * 60)
        c = make_capsule(16, "stack", lambda: st)
        self.assertEqual(c._compute_info()["line"], "العصر بعد 47:00")
        c.set_prayer_view("stack", lambda: st, "minutes")
        self.assertEqual(c._compute_info()["line"], "العصر بعد 0:47")
        c.set_prayer_view("stack", lambda: st, "weird")
        self.assertEqual(c._countdown_fmt, "seconds")

    def test_set_prayer_view_rejects_unknown_modes(self):
        c = make_capsule(16)
        c.set_prayer_view("weird", None)
        self.assertEqual(c._mode_cfg, "none")
        c.set_prayer_view("side", lambda: None)
        self.assertEqual(c._mode_cfg, "side")


if __name__ == "__main__":
    unittest.main()
