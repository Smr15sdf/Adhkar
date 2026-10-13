# -*- coding: utf-8 -*-
"""اختبارات منطق مواقيت الصلاة (بدون واجهة). تُشغَّل:  python -m unittest discover -s tests -v

الساعة تُحقن (datetime ثابت) فلا ننتظر الأذان الحقيقي. المراجع الخارجية غير رسمية (مواقع منشورة).
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import prayer_times as pt  # noqa: E402

RIYADH = ZoneInfo("Asia/Riyadh")
MAKKAH = (21.4225, 39.8262)


def at(y, mo, d, h=0, mi=0, s=0, us=0, tz=RIYADH):
    return datetime(y, mo, d, h, mi, s, us, tzinfo=tz)


def make_cfg(**over):
    raw = {
        "enabled": True,
        "location": {"mode": "manual", "name": "مكة", "lat": MAKKAH[0], "lon": MAKKAH[1],
                     "tz": "Asia/Riyadh"},
        "method": "makkah", "asr": "standard",
    }
    raw.update(over)
    return pt.sanitize_config(raw)


def make_engine(tmpdir=None, now=None, **over):
    path = Path(tmpdir) / "state.json" if tmpdir else None
    store = pt.StateStore(path)
    holder = {"now": now or at(2026, 8, 12, 3, 0)}
    eng = pt.PrayerEngine(make_cfg(**over), store, clock=lambda: holder["now"])
    return eng, holder, store


def hm(dt):
    return dt.strftime("%H:%M")


def minutes_between(a, b):
    return abs((a - b).total_seconds()) / 60.0


class CalculationTests(unittest.TestCase):
    def test_makkah_matches_published_timetable_exactly(self):
        # المرجع: جدول أم القرى لمكة 12 أغسطس 2026 (saudilifeguide.com)
        t = pt.compute_day(date(2026, 8, 12), *MAKKAH, RIYADH, "makkah", "standard")
        self.assertEqual({k: hm(v) for k, v in t.items()},
                         {"fajr": "04:37", "sunrise": "05:58", "dhuhr": "12:26",
                          "asr": "15:47", "maghrib": "18:53", "isha": "20:23"})

    def test_makkah_aug7_within_one_minute_of_published(self):
        # المرجع: edarabia.com (قد تختلف الإحداثيات والتقريب بدقيقة)
        t = pt.compute_day(date(2026, 8, 7), *MAKKAH, RIYADH, "makkah", "standard")
        ref = {"fajr": (4, 34), "dhuhr": (12, 26), "asr": (15, 47), "maghrib": (18, 56), "isha": (20, 26)}
        for name, (h, m) in ref.items():
            self.assertLessEqual(minutes_between(t[name], at(2026, 8, 7, h, m)), 1.0, name)

    def test_hanafi_asr(self):
        t = pt.compute_day(date(2026, 8, 7), *MAKKAH, RIYADH, "makkah", "hanafi")
        self.assertEqual(hm(t["asr"]), "17:00")   # المرجع: edarabia (حنفي)

    def test_dhahran_within_one_minute_of_published(self):
        # المرجع: gtaf.org للظهران 26 أغسطس 2026
        t = pt.compute_day(date(2026, 8, 26), 26.2361, 50.0393, RIYADH, "makkah", "standard")
        ref = {"fajr": (3, 54), "dhuhr": (11, 41), "asr": (15, 12), "maghrib": (18, 5), "isha": (19, 35)}
        for name, (h, m) in ref.items():
            self.assertLessEqual(minutes_between(t[name], at(2026, 8, 26, h, m)), 1.0, name)

    def test_umm_alqura_isha_is_90_minutes_after_maghrib(self):
        t = pt.compute_day(date(2026, 10, 11), *MAKKAH, RIYADH, "makkah", "standard")
        self.assertEqual((t["isha"] - t["maghrib"]).total_seconds(), 90 * 60)

    def test_manual_minute_adjustment(self):
        base = pt.compute_day(date(2026, 10, 11), *MAKKAH, RIYADH)
        adj = pt.compute_day(date(2026, 10, 11), *MAKKAH, RIYADH, adjust={"fajr": 3, "isha": -2})
        self.assertEqual((adj["fajr"] - base["fajr"]).total_seconds(), 180)
        self.assertEqual((adj["isha"] - base["isha"]).total_seconds(), -120)
        self.assertEqual(adj["asr"], base["asr"])

    def test_order_is_valid_for_all_methods_cities_and_dates(self):
        cities = [("Asia/Riyadh", 21.42, 39.83), ("Asia/Riyadh", 26.43, 50.10),
                  ("Africa/Cairo", 30.04, 31.24), ("Europe/London", 51.5, -0.12),
                  ("America/New_York", 40.71, -74.0), ("Asia/Karachi", 24.86, 67.0),
                  ("Australia/Sydney", -33.87, 151.2), ("Asia/Jakarta", -6.2, 106.8)]
        for tzname, lat, lon in cities:
            tz = ZoneInfo(tzname)
            for method in pt.METHODS:
                for asr in pt.ASR_FACTORS:
                    for doy in range(1, 366, 11):
                        d = date(2026, 1, 1) + timedelta(days=doy - 1)
                        t = pt.compute_day(d, lat, lon, tz, method, asr)
                        if lat < 45:   # دون خطوط العرض العالية لا يجوز أن يفشل الحساب
                            self.assertIsNotNone(t, (tzname, method, asr, d))
                        if t:
                            seq = [t[p] for p in pt.PRAYERS]
                            self.assertEqual(seq, sorted(seq))
                            self.assertLess(t["fajr"], t["sunrise"])
                            self.assertLess(t["sunrise"], t["dhuhr"])

    def test_polar_summer_returns_none_not_invented_times(self):
        tz = ZoneInfo("Europe/Oslo")
        self.assertIsNone(pt.compute_day(date(2026, 6, 21), 69.65, 18.96, tz, "mwl"))

    def test_dst_offset_is_handled(self):
        tz = ZoneInfo("Europe/London")
        before = pt.compute_day(date(2026, 3, 28), 51.5, -0.12, tz, "mwl")
        after = pt.compute_day(date(2026, 3, 29), 51.5, -0.12, tz, "mwl")
        self.assertEqual(before["dhuhr"].hour, 12)   # GMT
        self.assertEqual(after["dhuhr"].hour, 13)    # BST بعد التحول
        self.assertEqual(after["dhuhr"].utcoffset(), timedelta(hours=1))

    def test_unknown_tz_falls_back_to_system_with_note(self):
        eng, _, _ = make_engine(location={"mode": "manual", "name": "x", "lat": 21.4, "lon": 39.8,
                                          "tz": "Nope/Invalid"})
        st = eng.status(at(2026, 8, 12, 3, 0))
        self.assertEqual(st.note, "tz_fallback")
        self.assertIn(st.kind, ("next", "iqama"))


class StatusTests(unittest.TestCase):
    def test_countdown_to_next_prayer(self):
        eng, _, _ = make_engine()
        st = eng.status(at(2026, 8, 12, 15, 0, 0))
        self.assertEqual((st.kind, st.prayer), ("next", "asr"))
        self.assertEqual(st.remaining, 47 * 60)
        self.assertEqual(pt.format_countdown(st.remaining), "47:00")

    def test_countdown_rounds_up_so_it_never_shows_zero_early(self):
        eng, _, _ = make_engine()
        st = eng.status(at(2026, 8, 12, 15, 46, 59, 500000))
        self.assertEqual(st.remaining, 1)

    def test_before_fajr_next_is_fajr_same_day(self):
        eng, _, _ = make_engine()
        st = eng.status(at(2026, 8, 12, 3, 0))
        self.assertEqual((st.kind, st.prayer), ("next", "fajr"))
        self.assertEqual(st.target.date(), date(2026, 8, 12))

    def test_after_isha_next_is_tomorrows_fajr(self):
        eng, _, _ = make_engine()
        isha_end = eng.day_times(date(2026, 8, 12))["isha"] + timedelta(minutes=21)
        st = eng.status(isha_end)
        self.assertEqual((st.kind, st.prayer), ("next", "fajr"))
        self.assertEqual(st.target.date(), date(2026, 8, 13))

    def test_midnight_rollover(self):
        eng, _, _ = make_engine()
        a = eng.status(at(2026, 8, 12, 23, 59, 30))
        b = eng.status(at(2026, 8, 13, 0, 0, 30))
        self.assertEqual((a.prayer, a.target.date()), ("fajr", date(2026, 8, 13)))
        self.assertEqual((b.prayer, b.target.date()), ("fajr", date(2026, 8, 13)))
        self.assertEqual(a.remaining - b.remaining, 60)

    def test_iqama_starts_at_adhan_and_counts_down_per_prayer(self):
        iq = {"fajr": 25, "dhuhr": 15, "asr": 20, "maghrib": 10, "isha": 30}
        eng, _, _ = make_engine(iqama_minutes=iq)
        day = eng.day_times(date(2026, 8, 12))
        for p in pt.PRAYERS:
            st = eng.status(day[p])                                   # لحظة الأذان بالضبط
            self.assertEqual((st.kind, st.prayer), ("iqama", p), p)
            self.assertEqual(st.remaining, iq[p] * 60, p)
            st2 = eng.status(day[p] + timedelta(minutes=4, seconds=30))
            self.assertEqual(st2.remaining, iq[p] * 60 - 270, p)
            self.assertEqual(st2.target, day[p] + timedelta(minutes=iq[p]))

    def test_after_iqama_moves_to_next_prayer(self):
        eng, _, _ = make_engine()
        day = eng.day_times(date(2026, 8, 12))
        st = eng.status(day["asr"] + timedelta(minutes=20))   # لحظة انتهاء إقامة العصر
        self.assertEqual((st.kind, st.prayer), ("next", "maghrib"))
        self.assertEqual(st.remaining, int((day["maghrib"] - day["asr"]).total_seconds()) - 20 * 60)

    def test_zero_iqama_disables_phase(self):
        eng, _, _ = make_engine(iqama_minutes={"fajr": 0, "dhuhr": 0, "asr": 0, "maghrib": 0, "isha": 0})
        day = eng.day_times(date(2026, 8, 12))
        st = eng.status(day["asr"] + timedelta(seconds=30))
        self.assertEqual((st.kind, st.prayer), ("next", "maghrib"))

    def test_first_run_mid_day(self):
        eng, _, _ = make_engine(now=at(2026, 8, 12, 14, 0))
        st = eng.status()
        self.assertEqual((st.kind, st.prayer), ("next", "asr"))
        self.assertEqual(eng.due_notices(), [])   # لا إشعارات قديمة

    def test_disabled_and_missing_location_and_failed_calc(self):
        eng, _, _ = make_engine(enabled=False)
        self.assertEqual(eng.status(at(2026, 8, 12, 3)).kind, "disabled")
        eng2, _, _ = make_engine(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        st = eng2.status(at(2026, 8, 12, 3))
        self.assertEqual((st.kind, st.reason), ("unavailable", "no_location"))
        self.assertEqual(eng2.due_notices(at(2026, 8, 12, 3)), [])
        eng3, _, _ = make_engine(method="mwl", location={"mode": "manual", "name": "Tromso", "lat": 69.65,
                                                         "lon": 18.96, "tz": "Europe/Oslo"})
        st3 = eng3.status(datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("Europe/Oslo")))
        self.assertEqual((st3.kind, st3.reason), ("unavailable", "calc_failed"))
        txt = pt.status_texts(st3)
        self.assertEqual(txt["countdown"], "")

    def test_status_texts(self):
        eng, _, _ = make_engine()
        day = eng.day_times(date(2026, 8, 12))
        t1 = pt.status_texts(eng.status(at(2026, 8, 12, 15, 0)))
        self.assertEqual(t1, {"label": "العصر", "countdown": "47:00", "line": "العصر بعد 47:00"})
        t2 = pt.status_texts(eng.status(day["asr"] + timedelta(minutes=5)))
        self.assertEqual(t2["label"], "إقامة العصر")
        self.assertEqual(t2["line"], "إقامة العصر بعد 15:00")
        self.assertEqual(pt.format_countdown(3725), "1:02:05")
        self.assertIsNone(pt.status_texts(pt.Status("disabled")))


def run_ticks(eng, start, end, step_seconds=1, deliver=True):
    """يحاكي مؤقتاً يعمل كل step ثانية؛ يرجع قائمة (الوقت، الإشعار)."""
    out = []
    t = start
    while t <= end:
        for n in eng.due_notices(t):
            out.append((t, n))
            if deliver:
                eng.mark_delivered(n)
        t += timedelta(seconds=step_seconds)
    return out


class NotificationTests(unittest.TestCase):
    def test_exactly_one_pre_and_one_adhan_per_prayer_over_full_day(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            got = run_ticks(eng, at(2026, 8, 12, 0, 0, 0), at(2026, 8, 12, 23, 59, 59), step_seconds=5)
            ids = [n.id for _, n in got]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(sorted(n.kind for _, n in got), ["adhan"] * 5 + ["pre"] * 5)
            self.assertEqual([n.prayer for _, n in got if n.kind == "adhan"], list(pt.PRAYERS))

    def test_fires_at_the_right_second_with_one_second_ticks(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["asr"] - timedelta(minutes=10), day["asr"] + timedelta(minutes=2))
            self.assertEqual(len(got), 2)
            (t_pre, n_pre), (t_adhan, n_adhan) = got
            self.assertEqual(t_pre, day["asr"] - timedelta(minutes=5))
            self.assertEqual(n_pre.text, "باقي 5 دقائق على أذان العصر")
            self.assertEqual(t_adhan, day["asr"])
            self.assertEqual(n_adhan.text, "حان الآن وقت أذان العصر")

    def test_repeated_polling_never_duplicates_after_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            t = day["asr"]
            first = eng.due_notices(t)
            self.assertEqual(len(first), 1)
            eng.mark_delivered(first[0])
            for i in range(200):
                self.assertEqual(eng.due_notices(t + timedelta(milliseconds=i * 100)), [])

    def test_undelivered_notice_is_retried_only_within_grace_then_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            t = eng.day_times(date(2026, 8, 12))["asr"]
            self.assertEqual(len(eng.due_notices(t)), 1)                       # فشل العرض: لم نسجّله
            self.assertEqual(len(eng.due_notices(t + timedelta(seconds=30))), 1)   # يُعاد المحاولة
            self.assertEqual(eng.due_notices(t + timedelta(seconds=120)), [])      # فات الأوان
            self.assertEqual(eng.due_notices(t + timedelta(seconds=121)), [])      # ولا يعود

    def test_app_started_after_pre_notice_time_skips_it(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["asr"] - timedelta(minutes=2), day["asr"] + timedelta(minutes=1))
            self.assertEqual([n.kind for _, n in got], ["adhan"])

    def test_sleep_resume_long_jump_shows_nothing_old(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            self.assertEqual(eng.due_notices(day["asr"] - timedelta(minutes=30)), [])
            # نام الجهاز ثم استيقظ بعد وقت العصر بـ 10 دقائق
            self.assertEqual(eng.due_notices(day["asr"] + timedelta(minutes=10)), [])
            self.assertEqual(eng.due_notices(day["asr"] + timedelta(minutes=10, seconds=1)), [])

    def test_sleep_resume_within_grace_shows_single_latest(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            got = eng.due_notices(day["asr"] + timedelta(seconds=40))
            self.assertEqual([n.kind for n in got], ["adhan"])
            eng.mark_delivered(got[0])
            self.assertEqual(eng.due_notices(day["asr"] + timedelta(seconds=41)), [])

    def test_clock_moved_back_and_forward_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            first = run_ticks(eng, day["asr"] - timedelta(minutes=6), day["asr"] + timedelta(minutes=1))
            self.assertEqual(len(first), 2)
            again = run_ticks(eng, day["asr"] - timedelta(minutes=6), day["asr"] + timedelta(minutes=1))
            self.assertEqual(again, [])   # الساعة رجعت للخلف ثم تقدمت: لا تكرار

    def test_single_notice_when_two_are_due_together(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, store = make_engine(d)
            t = at(2026, 8, 12, 15, 0)
            a = pt.Notice("2026-08-12:dhuhr:adhan", "adhan", "dhuhr", t - timedelta(seconds=20), "a")
            b = pt.Notice("2026-08-12:asr:pre", "pre", "asr", t, "b")
            eng._events = lambda entries: [a, b]
            got = eng.due_notices(t + timedelta(seconds=5))
            self.assertEqual([n.id for n in got], [b.id])
            self.assertEqual(store.get(a.id)["s"], "skipped")

    def test_concurrent_handler_is_blocked(self):
        eng, _, _ = make_engine()
        t = eng.day_times(date(2026, 8, 12))["asr"]
        self.assertTrue(eng._lock.acquire(blocking=False))
        try:
            self.assertEqual(eng.due_notices(t), [])
        finally:
            eng._lock.release()
        self.assertEqual(len(eng.due_notices(t)), 1)

    def test_pre_minutes_and_flags(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d, pre_minutes=10)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["isha"] - timedelta(minutes=12), day["isha"] + timedelta(seconds=5))
            self.assertEqual(got[0][0], day["isha"] - timedelta(minutes=10))
            self.assertEqual(got[0][1].text, "باقي 10 دقائق على أذان العشاء")
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d, notify_pre=False)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["asr"] - timedelta(minutes=10), day["asr"] + timedelta(minutes=1))
            self.assertEqual([n.kind for _, n in got], ["adhan"])
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d, notify_adhan=False)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["asr"] - timedelta(minutes=10), day["asr"] + timedelta(minutes=1))
            self.assertEqual([n.kind for _, n in got], ["pre"])

    def test_pre_notice_is_never_shown_after_adhan_time(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d, pre_minutes=1, notify_adhan=False)
            asr = eng.day_times(date(2026, 8, 12))["asr"]
            # بعد الأذان بـ 20 ثانية (ما زلنا ضمن سماحية 90 ثانية من وقت التنبيه المسبق)
            self.assertEqual(eng.due_notices(asr + timedelta(seconds=20)), [])
            # وقبل الأذان بـ 30 ثانية يظهر التنبيه المسبق بشكل طبيعي
            eng2, _, _ = make_engine(d + "/b", pre_minutes=1, notify_adhan=False)
            got = eng2.due_notices(asr - timedelta(seconds=30))
            self.assertEqual([n.text for n in got], ["باقي دقيقة واحدة على أذان العصر"])

    def test_text_helpers(self):
        self.assertEqual(pt.pre_text("asr", 1), "باقي دقيقة واحدة على أذان العصر")
        self.assertEqual(pt.pre_text("fajr", 2), "باقي دقيقتان على أذان الفجر")
        self.assertEqual(pt.pre_text("asr", 5), "باقي 5 دقائق على أذان العصر")
        self.assertEqual(pt.pre_text("isha", 15), "باقي 15 دقيقة على أذان العشاء")

    def test_notification_independent_of_countdown_or_ui_state(self):
        # الإشعار والعدّاد مستقلان: استدعاء status كثيراً لا يغيّر الإشعارات
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            t = day["asr"]
            for _ in range(50):
                eng.status(t)
            got = eng.due_notices(t)
            self.assertEqual(len(got), 1)


class PersistenceTests(unittest.TestCase):
    def test_restart_does_not_repeat_delivered_notices(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            got = run_ticks(eng, day["asr"] - timedelta(minutes=6), day["asr"] + timedelta(seconds=10))
            self.assertEqual(len(got), 2)
            eng2, _, _ = make_engine(d)    # إعادة تشغيل التطبيق (نفس ملف الحالة)
            self.assertEqual(run_ticks(eng2, day["asr"] - timedelta(minutes=6),
                                       day["asr"] + timedelta(seconds=60)), [])

    def test_iqama_countdown_is_restored_after_restart(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            day = eng.day_times(date(2026, 8, 12))
            before = eng.status(day["asr"] + timedelta(minutes=5))
            eng2, _, _ = make_engine(d)
            after = eng2.status(day["asr"] + timedelta(minutes=5))
            self.assertEqual((after.kind, after.prayer, after.remaining),
                             (before.kind, before.prayer, before.remaining))
            self.assertEqual(after.remaining, 15 * 60)

    def test_state_file_roundtrip_corrupt_and_prune(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            st = pt.StateStore(p)
            st.set("2026-08-12:asr:adhan", "fired", at(2026, 8, 12, 15, 47))
            st.set("2026-08-01:asr:adhan", "fired", at(2026, 8, 1, 15, 47))
            st.save()
            self.assertFalse((Path(d) / "s.tmp").exists())
            st2 = pt.StateStore(p)
            self.assertEqual(st2.get("2026-08-12:asr:adhan")["s"], "fired")
            st2.prune(date(2026, 8, 12))
            self.assertIsNone(st2.get("2026-08-01:asr:adhan"))
            self.assertIsNotNone(st2.get("2026-08-12:asr:adhan"))
            p.write_text("{broken", encoding="utf-8")
            self.assertEqual(pt.StateStore(p).events, {})

    def test_config_roundtrip_through_json_keeps_choices(self):
        cfg = make_cfg(display_mode="side", method="isna", asr="hanafi", pre_minutes=7,
                       adjust={"fajr": 2, "dhuhr": 0, "asr": -1, "maghrib": 3, "isha": 0},
                       iqama_minutes={"fajr": 25, "dhuhr": 15, "asr": 12, "maghrib": 8, "isha": 35},
                       sound={"enabled": True, "path": "C:/a/b.mp3"})
        again = pt.sanitize_config(json.loads(json.dumps(cfg, ensure_ascii=False)))
        self.assertEqual(cfg, again)
        self.assertEqual(again["display_mode"], "side")
        self.assertEqual(again["location"]["mode"], "manual")

    def test_sanitize_repairs_garbage(self):
        bad = {"enabled": "yes", "display_mode": "nonsense", "method": 5, "asr": None,
               "location": {"mode": "weird", "lat": 999, "lon": "x", "tz": 5},
               "adjust": {"fajr": 9999, "asr": "z"}, "pre_minutes": -4,
               "iqama_minutes": {"fajr": 5000, "maghrib": None}, "sound": "no"}
        cfg = pt.sanitize_config(bad)
        self.assertEqual(cfg["display_mode"], pt.MODE_HOVER)
        self.assertEqual(cfg["method"], "makkah")
        self.assertEqual(cfg["location"]["mode"], "auto")
        self.assertIsNone(cfg["location"]["lat"])
        self.assertEqual(cfg["adjust"]["fajr"], 60)
        self.assertEqual(cfg["adjust"]["asr"], 0)
        self.assertEqual(cfg["pre_minutes"], 1)
        self.assertEqual(cfg["iqama_minutes"]["fajr"], 120)
        self.assertEqual(cfg["iqama_minutes"]["maghrib"], 10)
        self.assertEqual(pt.sanitize_config(None), pt.DEFAULT_PRAYER_CONFIG)
        self.assertEqual(pt.sanitize_config("x"), pt.DEFAULT_PRAYER_CONFIG)

    def test_default_config_is_not_shared_or_mutated(self):
        a = pt.sanitize_config({})
        a["adjust"]["fajr"] = 9
        a["location"]["name"] = "x"
        self.assertEqual(pt.DEFAULT_PRAYER_CONFIG["adjust"]["fajr"], 0)
        self.assertEqual(pt.DEFAULT_PRAYER_CONFIG["location"]["name"], "")


class ConfigChangeTests(unittest.TestCase):
    def test_changing_adjustment_moves_future_events_and_fires_once_at_new_time(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            old_asr = eng.day_times(date(2026, 8, 12))["asr"]
            self.assertEqual(eng.due_notices(old_asr - timedelta(minutes=30)), [])
            eng.set_config(make_cfg(adjust={"asr": 20}))
            new_asr = eng.day_times(date(2026, 8, 12))["asr"]
            self.assertEqual(new_asr - old_asr, timedelta(minutes=20))
            got = run_ticks(eng, old_asr - timedelta(minutes=10), new_asr + timedelta(minutes=1))
            self.assertEqual([(n.kind, t) for t, n in got],
                             [("pre", new_asr - timedelta(minutes=5)), ("adhan", new_asr)])

    def test_event_skipped_earlier_is_rearmed_when_config_moves_it_to_the_future(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, store = make_engine(d)
            old_asr = eng.day_times(date(2026, 8, 12))["asr"]
            # بعد وقت العصر بـ 10 دقائق: أحداث العصر القديمة تُتجاوز وتُسجَّل كـ skipped
            self.assertEqual(eng.due_notices(old_asr + timedelta(minutes=10)), [])
            self.assertEqual(store.get("2026-08-12:asr:adhan")["s"], "skipped")
            # المستخدم عدّل التوقيت فصار العصر بعد ساعة من الآن: يجب إعادة تفعيله
            eng.set_config(make_cfg(adjust={"asr": 60}))
            new_asr = eng.day_times(date(2026, 8, 12))["asr"]
            got = run_ticks(eng, old_asr + timedelta(minutes=10), new_asr + timedelta(minutes=1))
            self.assertEqual([(n.kind, t) for t, n in got],
                             [("pre", new_asr - timedelta(minutes=5)), ("adhan", new_asr)])

    def test_event_already_fired_is_not_repeated_when_time_moves_to_the_past(self):
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            old_asr = eng.day_times(date(2026, 8, 12))["asr"]
            got = run_ticks(eng, old_asr - timedelta(minutes=6), old_asr + timedelta(seconds=5))
            self.assertEqual(len(got), 2)
            eng.set_config(make_cfg(adjust={"asr": -10}))     # الموعد الجديد أصبح في الماضي
            self.assertEqual(run_ticks(eng, old_asr, old_asr + timedelta(minutes=3)), [])

    def test_changing_location_and_method_recomputes(self):
        eng, _, _ = make_engine()
        t1 = eng.day_times(date(2026, 8, 12))["fajr"]
        eng.set_config(make_cfg(method="isna"))
        t2 = eng.day_times(date(2026, 8, 12))["fajr"]
        self.assertGreater(t2, t1)   # زاوية 15° أبكر دخولاً للفجر من 18.5° => الفجر لاحقاً
        eng.set_config(make_cfg(location={"mode": "manual", "name": "القاهرة", "lat": 30.04,
                                          "lon": 31.24, "tz": "Africa/Cairo"}))
        self.assertEqual(eng.status(datetime(2026, 8, 12, 3, 0, tzinfo=ZoneInfo("Africa/Cairo"))).prayer,
                         "fajr")

    def test_repeated_set_config_does_not_accumulate_state(self):
        eng, _, _ = make_engine()
        for _ in range(50):
            eng.set_config(make_cfg())
        self.assertLessEqual(len(eng._day_cache), 1)


class FakeClockTests(unittest.TestCase):
    def test_fake_clock_starts_at_value_and_advances(self):
        c = pt.make_clock({"ADHKAR_FAKE_NOW": "2026-10-11T15:25:00+03:00"})
        a = c()
        self.assertEqual((a.year, a.month, a.day, a.hour, a.minute), (2026, 10, 11, 15, 25))
        self.assertGreaterEqual(c(), a)

    def test_invalid_fake_clock_falls_back_to_real(self):
        c = pt.make_clock({"ADHKAR_FAKE_NOW": "garbage"})
        self.assertLess(abs((c() - datetime.now().astimezone()).total_seconds()), 2)


class GeoTests(unittest.TestCase):
    IPWHO_OK = {"ip": "1.2.3.4", "success": True, "country": "Saudi Arabia", "city": "Dammam",
                "latitude": 26.4207, "longitude": 50.0888,
                "timezone": {"id": "Asia/Riyadh", "abbr": "+03", "offset": 10800}}

    def test_parse_ipwho_success(self):
        loc = pt.parse_ip_location(self.IPWHO_OK)
        self.assertEqual((loc["lat"], loc["lon"], loc["tz"]), (26.4207, 50.0888, "Asia/Riyadh"))
        self.assertIn("Dammam", loc["name"])

    def test_parse_ipapi_format(self):
        loc = pt.parse_ip_location({"city": "Cairo", "country_name": "Egypt", "latitude": 30.04,
                                    "longitude": 31.24, "timezone": "Africa/Cairo"})
        self.assertEqual(loc["tz"], "Africa/Cairo")

    def test_parse_rejects_failures_and_bad_coordinates(self):
        self.assertIsNone(pt.parse_ip_location({"success": False, "message": "limit"}))
        self.assertIsNone(pt.parse_ip_location({"error": True, "reason": "RateLimited"}))
        self.assertIsNone(pt.parse_ip_location({"success": True, "city": "X"}))
        self.assertIsNone(pt.parse_ip_location({"latitude": 123, "longitude": 10}))
        self.assertIsNone(pt.parse_ip_location({"latitude": "a", "longitude": "b"}))
        self.assertIsNone(pt.parse_ip_location(None))
        self.assertIsNone(pt.parse_ip_location([1, 2]))

    def test_detect_offline_returns_clear_error_and_no_location(self):
        def boom(url, timeout=8.0):
            raise urllib.error.URLError("no network")
        loc, err = pt.detect_location_by_ip(boom)
        self.assertIsNone(loc)
        self.assertIn("الإنترنت", err)

    def test_detect_uses_fallback_service_when_first_fails(self):
        calls = []

        def fetch(url, timeout=8.0):
            calls.append(url)
            if "ipwho.is" in url:
                raise urllib.error.URLError("down")
            return {"city": "Cairo", "country_name": "Egypt", "latitude": 30.04, "longitude": 31.24,
                    "timezone": "Africa/Cairo"}
        loc, err = pt.detect_location_by_ip(fetch)
        self.assertEqual(len(calls), 2)
        self.assertEqual((loc["tz"], err), ("Africa/Cairo", ""))

    def test_detect_with_unusable_payload_does_not_pretend_success(self):
        loc, err = pt.detect_location_by_ip(lambda url, timeout=8.0: {"success": False})
        self.assertIsNone(loc)
        self.assertTrue(err)

    def test_city_search_parsing_and_url(self):
        seen = {}

        def fetch(url, timeout=8.0):
            seen["url"] = url
            return {"results": [
                {"name": "الدمام", "admin1": "المنطقة الشرقية", "country": "السعودية",
                 "latitude": 26.43, "longitude": 50.1, "timezone": "Asia/Riyadh"},
                {"name": "بلا إحداثيات"},
                {"name": "Dammam", "latitude": 26.4, "longitude": 50.0, "timezone": "Asia/Riyadh"}]}
        res, err = pt.search_cities("الدمام", fetch)
        self.assertEqual(err, "")
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["name"], "الدمام، المنطقة الشرقية، السعودية")
        self.assertEqual(res[0]["tz"], "Asia/Riyadh")
        self.assertIn("geocoding-api.open-meteo.com/v1/search", seen["url"])
        self.assertIn("language=ar", seen["url"])
        self.assertIn("%D8%A7%D9%84%D8%AF%D9%85%D8%A7%D9%85", seen["url"])

    def test_city_search_edge_cases(self):
        self.assertEqual(pt.search_cities("a")[0], [])
        self.assertTrue(pt.search_cities(" ")[1])
        res, err = pt.search_cities("zzzz", lambda u, timeout=8.0: {"generationtime_ms": 1.0})
        self.assertEqual((res, bool(err)), ([], True))

        def boom(url, timeout=8.0):
            raise urllib.error.URLError("offline")
        res, err = pt.search_cities("mecca", boom)
        self.assertEqual(res, [])
        self.assertIn("الإنترنت", err)


class ManualLocationPersistenceTests(unittest.TestCase):
    def test_manual_location_is_stable_across_restart(self):
        cfg = make_cfg()
        again = pt.sanitize_config(json.loads(json.dumps(cfg)))
        self.assertEqual(again["location"], cfg["location"])
        self.assertEqual(again["location"]["mode"], "manual")
        self.assertTrue(pt.location_ready(again))


KHOBAR = (26.2794, 50.2083)
RIYADH_PT = (24.7136, 46.6753)


def ok_runner(lat=KHOBAR[0], lon=KHOBAR[1], acc="60.0"):
    return lambda script: (0, '{"status":"ok","lat":%s,"lon":%s,"acc":%s}' % (lat, lon, acc), "")


class PreciseLocationTests(unittest.TestCase):
    def test_wrong_city_shifts_times_materially(self):
        # لماذا تهم الدقة: الخبر والرياض يفصلهما ~14 دقيقة في الفجر
        d = date(2026, 10, 11)
        khobar = pt.compute_day(d, *KHOBAR, RIYADH, "makkah")
        riyadh = pt.compute_day(d, *RIYADH_PT, RIYADH, "makkah")
        self.assertGreaterEqual((riyadh["fajr"] - khobar["fajr"]).total_seconds() / 60, 10)

    # --- ناتج PowerShell ---
    def test_parse_windows_output_variants(self):
        ok = pt.parse_windows_location('{"status":"ok","lat":26.2794,"lon":50.2083,"acc":60.5}')
        self.assertEqual((ok["status"], ok["lat"], ok["acc"]), ("ok", 26.2794, 60.5))
        nan = pt.parse_windows_location('{"status":"ok","lat":26.2,"lon":50.2,"acc":NaN}')
        self.assertEqual((nan["status"], nan["acc"]), ("ok", None))
        noisy = pt.parse_windows_location('WARNING: x\r\n{"status":"ok","lat":1.5,"lon":2.5,"acc":10}\r\n')
        self.assertEqual(noisy["status"], "ok")
        self.assertEqual(pt.parse_windows_location('{"status":"denied"}')["status"], "denied")
        self.assertEqual(pt.parse_windows_location('{"status":"unknown"}')["status"], "unknown")
        self.assertEqual(pt.parse_windows_location('{"status":"error","msg":"x"}')["status"], "error")
        self.assertEqual(pt.parse_windows_location("garbage")["status"], "error")
        self.assertEqual(pt.parse_windows_location("")["status"], "error")
        self.assertEqual(pt.parse_windows_location('{"status":"ok","lat":0,"lon":0,"acc":1}')["status"], "unknown")
        self.assertEqual(pt.parse_windows_location('{"status":"ok","lat":999,"lon":1}')["status"], "unknown")

    def test_powershell_script_is_sane_and_encoded_safely(self):
        self.assertIn("GeoCoordinateWatcher", pt.WINLOC_SCRIPT)
        self.assertIn("ConvertTo-Json", pt.WINLOC_SCRIPT)
        import base64
        enc = base64.b64encode(pt.WINLOC_SCRIPT.encode("utf-16-le")).decode()
        self.assertEqual(base64.b64decode(enc).decode("utf-16-le"), pt.WINLOC_SCRIPT)

    def test_detect_windows_accuracy_flag(self):
        loc, err = pt.detect_location_windows(ok_runner(acc="80"))
        self.assertEqual((err, loc["source"], loc["approx"], loc["accuracy_m"]), ("", "windows", False, 80.0))
        loc, _ = pt.detect_location_windows(ok_runner(acc="40000"))
        self.assertTrue(loc["approx"])
        loc, _ = pt.detect_location_windows(ok_runner(acc="NaN"))
        self.assertTrue(loc["approx"])

    def test_detect_windows_failures_have_clear_messages(self):
        def raises(exc):
            def run(script):
                raise exc
            return run
        import subprocess as sp
        self.assertEqual(pt.detect_location_windows(raises(FileNotFoundError()))[1], pt.WINLOC_ERRORS["unavailable"])
        self.assertEqual(pt.detect_location_windows(raises(sp.TimeoutExpired("p", 1)))[1], pt.WINLOC_ERRORS["timeout"])
        self.assertEqual(pt.detect_location_windows(raises(RuntimeError("x")))[1], pt.WINLOC_ERRORS["error"])
        loc, err = pt.detect_location_windows(lambda s: (0, '{"status":"denied"}', ""))
        self.assertIsNone(loc)
        self.assertIn("الموقع", err)
        loc, err = pt.detect_location_windows(lambda s: (1, "boom", "err"))
        self.assertEqual((loc, err), (None, pt.WINLOC_ERRORS["error"]))

    # --- الاسم والمنطقة الزمنية ---
    def test_reverse_geocode_name(self):
        seen = {}

        def fetch(url, timeout=8.0):
            seen["url"] = url
            return {"address": {"suburb": "الراكة", "city": "الخبر", "state": "المنطقة الشرقية",
                                "country": "السعودية"}, "display_name": "long text"}
        self.assertEqual(pt.reverse_geocode_name(26.2794, 50.2083, fetch), "الخبر، المنطقة الشرقية، السعودية")
        self.assertIn("nominatim.openstreetmap.org/reverse", seen["url"])
        self.assertIn("accept-language=ar", seen["url"])
        self.assertIn("lat=26.27940", seen["url"])
        self.assertEqual(pt.reverse_geocode_name(1, 1, lambda u, timeout=8.0: {"display_name": "مكان ما"}), "مكان ما")
        self.assertEqual(pt.reverse_geocode_name(1, 1, lambda u, timeout=8.0: {"error": "x"}), "")
        self.assertEqual(pt.reverse_geocode_name(1, 1, lambda u, timeout=8.0: [1]), "")

        def boom(url, timeout=8.0):
            raise urllib.error.URLError("offline")
        self.assertEqual(pt.reverse_geocode_name(1, 1, boom), "")

    def test_lookup_timezone(self):
        seen = {}

        def fetch(url, timeout=8.0):
            seen["url"] = url
            return {"timezone": "Asia/Riyadh", "utc_offset_seconds": 10800}
        self.assertEqual(pt.lookup_timezone(26.28, 50.2, fetch), "Asia/Riyadh")
        self.assertIn("timezone=auto", seen["url"])
        self.assertEqual(pt.lookup_timezone(1, 1, lambda u, timeout=8.0: {"timezone": "Not/AZone"}), "")
        self.assertEqual(pt.lookup_timezone(1, 1, lambda u, timeout=8.0: {"x": 1}), "")

        def boom(url, timeout=8.0):
            raise OSError("down")
        self.assertEqual(pt.lookup_timezone(1, 1, boom), "")

    # --- التنسيق العام: ويندوز أولاً، ثم IP تقريبي ---
    def make_fetch(self, log, ip_city=("Riyadh", 24.7136, 46.6753)):
        def fetch(url, timeout=8.0):
            log.append(url)
            if "ipwho.is" in url:
                return {"success": True, "city": ip_city[0], "country": "Saudi Arabia",
                        "latitude": ip_city[1], "longitude": ip_city[2], "timezone": {"id": "Asia/Riyadh"}}
            if "nominatim" in url:
                return {"address": {"city": "الخبر", "state": "المنطقة الشرقية", "country": "السعودية"}}
            if "open-meteo" in url:
                return {"timezone": "Asia/Riyadh"}
            raise urllib.error.URLError("unexpected " + url)
        return fetch

    def test_windows_location_beats_ip_the_khobar_not_riyadh_case(self):
        log = []
        loc, msg = pt.detect_location_precise(ok_runner(), self.make_fetch(log))
        self.assertEqual((loc["source"], loc["approx"], msg), ("windows", False, ""))
        self.assertAlmostEqual(loc["lat"], KHOBAR[0], places=3)
        self.assertEqual(loc["tz"], "Asia/Riyadh")
        self.assertIn("الخبر", loc["name"])
        self.assertFalse(any("ipwho.is" in u or "ipapi.co" in u for u in log))   # لم نسأل الـ IP أصلاً

    def test_falls_back_to_ip_flagged_approximate_with_reason(self):
        log = []
        denied = lambda script: (0, '{"status":"denied"}', "")
        loc, msg = pt.detect_location_precise(denied, self.make_fetch(log))
        self.assertEqual((loc["source"], loc["approx"]), ("ip", True))
        self.assertIn("Riyadh", loc["name"])
        self.assertIn("الموقع", msg)

    def test_both_sources_failing_returns_none_with_message(self):
        def boom(url, timeout=8.0):
            raise urllib.error.URLError("offline")
        loc, msg = pt.detect_location_precise(lambda s: (0, '{"status":"unknown"}', ""), boom)
        self.assertIsNone(loc)
        self.assertIn("الإنترنت", msg)

    def test_name_falls_back_to_coordinates_when_reverse_geocode_fails(self):
        def fetch(url, timeout=8.0):
            raise urllib.error.URLError("offline")
        loc, _ = pt.detect_location_precise(ok_runner(), fetch)
        self.assertEqual(loc["name"], "26.279, 50.208")
        self.assertEqual(loc["tz"], "")          # بدون إنترنت: يُستخدم توقيت النظام

    def test_describe_location(self):
        self.assertEqual(pt.describe_location({"lat": None, "lon": None}), "لم يتم تحديد موقع بعد")
        txt = pt.describe_location({"name": "الخبر", "lat": 26.2794, "lon": 50.2083, "tz": "Asia/Riyadh",
                                    "source": "windows", "accuracy_m": 123.4})
        self.assertEqual(txt, "الخبر (26.279, 50.208) · Asia/Riyadh · خدمة الموقع في ويندوز · الدقة ≈ 120 م")
        self.assertIn("≈ 12 كم", pt.describe_location({"lat": 1.0, "lon": 2.0, "accuracy_m": 12300,
                                                         "source": "ip", "tz": ""}))
        self.assertIn("توقيت النظام", pt.describe_location({"lat": 1.0, "lon": 2.0}))

    def test_config_keeps_source_and_accuracy_and_repairs_bad_values(self):
        cfg = make_cfg(location={"mode": "auto", "name": "الخبر", "lat": 26.2, "lon": 50.2, "tz": "Asia/Riyadh",
                                 "source": "windows", "accuracy_m": 55.5})
        again = pt.sanitize_config(json.loads(json.dumps(cfg)))
        self.assertEqual((again["location"]["source"], again["location"]["accuracy_m"]), ("windows", 55.5))
        bad = pt.sanitize_config({"location": {"lat": 1, "lon": 2, "accuracy_m": -5, "source": "x" * 99}})
        self.assertIsNone(bad["location"]["accuracy_m"])
        self.assertEqual(len(bad["location"]["source"]), 12)

    def test_engine_times_for(self):
        eng, _, _ = make_engine()
        t = eng.times_for(at(2026, 8, 12, 15, 0))
        self.assertEqual(t, eng.day_times(date(2026, 8, 12)))
        none_eng, _, _ = make_engine(location={"mode": "auto", "name": "", "lat": None, "lon": None, "tz": ""})
        self.assertIsNone(none_eng.times_for(at(2026, 8, 12, 15, 0)))


class DisplayFormatTests(unittest.TestCase):
    def test_clock_24h(self):
        self.assertEqual(pt.format_clock(at(2026, 8, 12, 4, 59), "24"), "04:59")
        self.assertEqual(pt.format_clock(at(2026, 8, 12, 15, 29), "24"), "15:29")
        self.assertEqual(pt.format_clock(at(2026, 8, 12, 0, 5), "24"), "00:05")
        self.assertEqual(pt.format_clock(at(2026, 8, 12, 15, 29)), "15:29")        # الافتراضي 24

    def test_clock_12h_with_arabic_am_pm_and_edges(self):
        cases = {(4, 59): "4:59 ص", (15, 29): "3:29 م", (0, 5): "12:05 ص", (12, 0): "12:00 م",
                 (12, 30): "12:30 م", (23, 59): "11:59 م", (13, 7): "1:07 م", (6, 0): "6:00 ص",
                 (11, 59): "11:59 ص"}
        for (h, m), expected in cases.items():
            self.assertEqual(pt.format_clock(at(2026, 8, 12, h, m), "12"), expected, (h, m))

    def test_countdown_seconds_and_minutes_formats(self):
        self.assertEqual(pt.format_countdown(2 * 3600 + 20 * 60 + 31, "seconds"), "2:20:31")
        self.assertEqual(pt.format_countdown(2 * 3600 + 20 * 60 + 31, "minutes"), "2:20")
        self.assertEqual(pt.format_countdown(47 * 60, "seconds"), "47:00")
        self.assertEqual(pt.format_countdown(47 * 60, "minutes"), "0:47")
        self.assertEqual(pt.format_countdown(3600, "minutes"), "1:00")
        self.assertEqual(pt.format_countdown(36000, "minutes"), "10:00")
        self.assertEqual(pt.format_countdown(60, "minutes"), "0:01")
        self.assertEqual(pt.format_countdown(59, "minutes"), pt.LESS_THAN_MINUTE)
        self.assertEqual(pt.format_countdown(0, "minutes"), pt.LESS_THAN_MINUTE)
        self.assertEqual(pt.format_countdown(-5, "minutes"), pt.LESS_THAN_MINUTE)
        self.assertEqual(pt.format_countdown(3725), "1:02:05")                      # الافتراضي بالثواني
        self.assertEqual(pt.format_countdown(3725, "garbage"), "1:02:05")           # صيغة مجهولة => الافتراضي

    def test_status_texts_follow_countdown_format(self):
        eng, _, _ = make_engine()
        day = eng.day_times(date(2026, 8, 12))
        nxt = eng.status(at(2026, 8, 12, 15, 0, 15))
        self.assertEqual(pt.status_texts(nxt, "seconds")["line"], "العصر بعد 46:45")
        self.assertEqual(pt.status_texts(nxt, "minutes")["line"], "العصر بعد 0:46")
        self.assertEqual(pt.status_texts(nxt)["countdown"], "46:45")
        iq = eng.status(day["asr"] + timedelta(minutes=5, seconds=30))
        self.assertEqual(pt.status_texts(iq, "minutes")["line"], "إقامة العصر بعد 0:14")
        last = eng.status(day["asr"] - timedelta(seconds=20))
        self.assertEqual(pt.status_texts(last, "minutes")["line"], "العصر بعد أقل من دقيقة")
        self.assertEqual(pt.status_texts(last, "seconds")["line"], "العصر بعد 00:20")

    def test_format_settings_are_validated_and_persisted(self):
        cfg = make_cfg(time_format="12", countdown_format="minutes")
        again = pt.sanitize_config(json.loads(json.dumps(cfg)))
        self.assertEqual((again["time_format"], again["countdown_format"]), ("12", "minutes"))
        bad = pt.sanitize_config({"time_format": "13", "countdown_format": "hours"})
        self.assertEqual((bad["time_format"], bad["countdown_format"]), ("24", "seconds"))
        self.assertEqual(pt.sanitize_config(None)["time_format"], "24")
        self.assertEqual(pt.sanitize_config({"time_format": 12})["time_format"], "24")   # رقم لا نص

    def test_display_formats_do_not_affect_times_or_notification_state(self):
        a = make_cfg(time_format="24", countdown_format="seconds")
        b = make_cfg(time_format="12", countdown_format="minutes")
        self.assertEqual(pt.times_key(a), pt.times_key(b))     # لا إبطال للذاكرة ولا إعادة تفعيل للإشعارات
        with tempfile.TemporaryDirectory() as d:
            eng, _, _ = make_engine(d)
            t = eng.day_times(date(2026, 8, 12))["asr"]
            first = eng.due_notices(t)
            eng.mark_delivered(first[0])
            eng.set_config(b)
            self.assertEqual(eng.due_notices(t + timedelta(seconds=5)), [])

    def test_distance_km(self):
        self.assertAlmostEqual(pt.distance_km(*KHOBAR, *KHOBAR), 0.0, places=6)
        d = pt.distance_km(*KHOBAR, *RIYADH_PT)
        self.assertTrue(350 < d < 420, d)


if __name__ == "__main__":
    unittest.main()
