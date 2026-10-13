# -*- coding: utf-8 -*-
"""اختبارات السلوك الحالي لنظام الأذكار (الدوال غير الرسومية) - تعمل قبل التعديل وبعده.

تُشغَّل بـ:  python -m unittest discover -s tests -v
لتشغيلها على نسخة أخرى من المشروع:  ADHKAR_SRC_DIR=/path python -m unittest ...
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(os.environ.get("ADHKAR_SRC_DIR", HERE.parent)).resolve()
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SRC))

import qt_stub  # noqa: E402

qt_stub.install()
_tmp_appdata = tempfile.mkdtemp(prefix="adhkar_test_appdata_")
os.environ["APPDATA"] = _tmp_appdata
os.environ.pop("ADHKAR_DATA_DIR", None)
app = importlib.import_module("adhkar_app")


def fresh_dir():
    d = tempfile.mkdtemp(prefix="adhkar_case_")
    os.environ["APPDATA"] = d
    os.environ.pop("ADHKAR_DATA_DIR", None)
    return Path(d)


class ExistingBehaviour(unittest.TestCase):
    def test_first_run_creates_defaults(self):
        d = fresh_dir()
        data = app.load_data()
        self.assertEqual(data["adhkar"], app.SUGGESTED_ADHKAR)
        self.assertEqual(data["interval_minutes"], 10)
        self.assertEqual(data["display_seconds"], 7)
        self.assertTrue(data["click_to_dismiss"])
        self.assertTrue((d / "Adhkar" / "data.json").exists())

    def test_suggested_adhkar_are_nine_unique_and_diacritized(self):
        s = app.SUGGESTED_ADHKAR
        self.assertEqual(len(s), 9)
        self.assertEqual(len(set(s)), 9)
        self.assertTrue(all(any("\u064b" <= ch <= "\u0652" for ch in t) for t in s))

    def test_old_file_without_new_keys_gets_defaults(self):
        d = fresh_dir()
        (d / "Adhkar").mkdir()
        (d / "Adhkar" / "data.json").write_text(
            json.dumps({"adhkar": ["أ", "ب"], "interval_minutes": 15}, ensure_ascii=False),
            encoding="utf-8")
        data = app.load_data()
        self.assertEqual(data["adhkar"], ["أ", "ب"])
        self.assertEqual(data["interval_minutes"], 15)
        self.assertEqual(data["ui_font_size"], 11)
        self.assertEqual(data["notif_font_size"], 16)
        self.assertEqual(data["display_seconds"], 7)

    def test_out_of_range_values_are_clamped(self):
        d = fresh_dir()
        (d / "Adhkar").mkdir()
        (d / "Adhkar" / "data.json").write_text(json.dumps({
            "adhkar": [" x ", "", "  "], "interval_minutes": 99999, "ui_font_size": 1,
            "notif_font_size": 999, "display_seconds": 0}), encoding="utf-8")
        data = app.load_data()
        self.assertEqual(data["adhkar"], ["x"])
        self.assertEqual(data["interval_minutes"], 1440)
        self.assertEqual(data["ui_font_size"], app.UI_FONT_RANGE[0])
        self.assertEqual(data["notif_font_size"], app.NOTIF_FONT_RANGE[1])
        self.assertEqual(data["display_seconds"], app.DURATION_RANGE[0])

    def test_corrupt_json_does_not_crash(self):
        d = fresh_dir()
        (d / "Adhkar").mkdir()
        (d / "Adhkar" / "data.json").write_text("{not json", encoding="utf-8")
        data = app.load_data()
        self.assertEqual(data["adhkar"], app.SUGGESTED_ADHKAR)

    def test_save_load_roundtrip_atomic(self):
        d = fresh_dir()
        data = app.load_data()
        data["adhkar"] = ["ذكر تجريبي", "ذكر ثانٍ"]
        data["interval_minutes"] = 33
        app.save_data(data)
        self.assertFalse((d / "Adhkar" / "data.tmp").exists())
        again = app.load_data()
        self.assertEqual(again["adhkar"], ["ذكر تجريبي", "ذكر ثانٍ"])
        self.assertEqual(again["interval_minutes"], 33)

    def test_default_data_not_mutated_by_loading(self):
        fresh_dir()
        before = json.dumps(app.DEFAULT_DATA, ensure_ascii=False, sort_keys=True)
        data = app.load_data()
        data["adhkar"].append("x")
        after = json.dumps(app.DEFAULT_DATA, ensure_ascii=False, sort_keys=True)
        self.assertEqual(before, after)

    def test_read_text_file_encodings(self):
        lines = ["سُبْحَانَ اللَّهِ", "الحمد لله", "", "  لا إله إلا الله  "]
        d = Path(tempfile.mkdtemp())
        for name, enc in (("a", "utf-8"), ("b", "utf-8-sig"), ("c", "utf-16"), ("d", "cp1256")):
            p = d / f"{name}.txt"
            p.write_bytes("\r\n".join(lines).encode(enc))
            got = [x.strip() for x in app.read_text_file(p).splitlines() if x.strip()]
            self.assertEqual(got, [x.strip() for x in lines if x.strip()], enc)

    def test_clamp(self):
        self.assertEqual([app._clamp(x, 2, 120, 7) for x in (0, 500, "abc", None, "15")],
                         [2, 120, 7, 7, 15])

    def test_style_template_fully_substituted(self):
        css = app.build_style("Thmanyah", 12)
        self.assertNotIn("@", css)
        self.assertIn("12pt", css)
        self.assertIn("Thmanyah", css)


@unittest.skipUnless(hasattr(app, "pt"), "نظام مواقيت الصلاة غير موجود في هذه النسخة")
class PrayerDataIntegration(unittest.TestCase):
    def test_old_file_without_prayer_gets_disabled_defaults(self):
        d = fresh_dir()
        (d / "Adhkar").mkdir()
        (d / "Adhkar" / "data.json").write_text(json.dumps({"adhkar": ["أ"]}, ensure_ascii=False),
                                                encoding="utf-8")
        data = app.load_data()
        self.assertFalse(data["prayer"]["enabled"])
        self.assertEqual(data["prayer"]["display_mode"], "hover")
        self.assertEqual(data["adhkar"], ["أ"])

    def test_garbage_prayer_block_is_repaired(self):
        d = fresh_dir()
        (d / "Adhkar").mkdir()
        (d / "Adhkar" / "data.json").write_text(json.dumps({"prayer": {"method": "x", "enabled": "?",
                                                 "location": {"lat": 500}}}), encoding="utf-8")
        data = app.load_data()
        self.assertEqual(data["prayer"]["method"], "makkah")
        self.assertIsNone(data["prayer"]["location"]["lat"])

    def test_save_data_without_prayer_keeps_prayer_from_disk(self):
        fresh_dir()
        data = app.load_data()
        data["prayer"]["enabled"] = True
        data["prayer"]["display_mode"] = "side"
        app.save_data(data)
        settings_only = {k: v for k, v in data.items() if k != "prayer"}
        settings_only["interval_minutes"] = 45
        app.save_data(settings_only)           # كما يفعل زر «حفظ التغييرات» في النافذة الرئيسية
        again = app.load_data()
        self.assertEqual(again["interval_minutes"], 45)
        self.assertTrue(again["prayer"]["enabled"])
        self.assertEqual(again["prayer"]["display_mode"], "side")

    def test_prayer_defaults_not_shared_between_loads(self):
        fresh_dir()
        a = app.load_data()
        a["prayer"]["adjust"]["fajr"] = 33
        a["prayer"]["location"]["name"] = "x"
        fresh_dir()
        b = app.load_data()
        self.assertEqual(b["prayer"]["adjust"]["fajr"], 0)
        self.assertEqual(app.DEFAULT_DATA["prayer"]["location"]["name"], "")

    def test_data_dir_override_for_isolated_manual_testing(self):
        d = Path(tempfile.mkdtemp())
        os.environ["ADHKAR_DATA_DIR"] = str(d / "iso")
        try:
            app.load_data()
            self.assertTrue((d / "iso" / "data.json").exists())
            self.assertEqual(app.prayer_state_file().parent, d / "iso")
        finally:
            os.environ.pop("ADHKAR_DATA_DIR", None)


if __name__ == "__main__":
    unittest.main()
