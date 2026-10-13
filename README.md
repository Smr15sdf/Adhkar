<div align="center">

<img src="docs/social_preview.png" alt="Adhkar - adhkar and prayer times in a glass capsule" width="100%">

# Adhkar | أذكار

**A Windows desktop app that shows short authentic adhkar and your prayer times in an iOS-style glass capsule notification.**

[![tests](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)

[العربية](README.ar.md) · English

</div>

---

## Why

It's easy to forget the adhkar and the time of the next prayer while working on the computer. Adhkar sits quietly in the system tray and, at an interval you choose, slides a small frosted-glass capsule down from the top of the screen with a short dhikr, then lets it disappear. It never takes focus away from what you're doing.

## Features

### Adhkar
- **Glass capsule notification:** frameless rounded pill with a blurred backdrop, slides down from the top-center and back up. It does not steal keyboard focus.
- **You control the timing:** interval between notifications (1–1440 minutes) and how long each stays (2–120 seconds).
- **Click to dismiss**, or turn it off and clicks pass straight through to the window behind.
- **Your own adhkar:** add and delete, import a `.txt` file (one dhikr per line; UTF-8, UTF-16 and Windows-1256 are supported, duplicates are skipped), or drag and drop the file onto the window.
- **Built-in starter set:** nine short adhkar from the Qur'an and the Sunnah, with references below.
- **Separate font sizes** for the interface and for the notification.

### Prayer times (new)
- **Computed locally, offline:** the five prayers are calculated on your machine from your coordinates (seven calculation methods, standard or Hanafi Asr, manual ±60 minute adjustment per prayer).
- **Three capsule modes**, switchable without restarting:
  1. *Dhikr only:* hover the capsule to see the next prayer and the time left.
  2. *Dhikr with time:* the countdown under the dhikr.
  3. *Side by side:* dhikr on one side, prayer name and countdown on the other.
- **Display formats:** 24-hour or 12-hour clock (3:29 PM style with ص/م), and the remaining time **with seconds (2:20:31)** or **in minutes (2:20)**.
- **Prayer cycle:** a notice before the adhan (5 minutes by default), a notice at the adhan, then a **per-prayer iqama countdown**, then the next prayer. Notices are never repeated, survive restarts, and anything that came due while the app was closed or the PC was asleep is skipped instead of showing a pile of old notices.
- **Optional adhan sound:** you pick your own file (WAV, MP3 or WMA). Off by default.
- **Accurate location:**
  - *Automatic* uses the **Windows Location Service** (Wi-Fi/GPS) and shows the accuracy. If it isn't available, an internet-based estimate is offered as an approximation and never silently replaces a saved location.
  - *Manual:* search for your city, or enter exact coordinates.
- **Tabs UI:** *Adhkar* and *Prayer times & alerts*, with a live strip of today's times and the next prayer highlighted.
- **Number fields and drop-downs ignore the mouse wheel**, so scrolling the page never changes a value by accident.
- **Runs in the background:** closing the window minimizes to the system tray (its tooltip shows the next prayer). Optional start with Windows.

## Screenshots

<!-- Replace these design renders with real screenshots of your build before publishing. -->

<p align="center">
  <img src="docs/capsule_modes.png" alt="The three capsule modes" width="100%">
</p>
<p align="center">
  <img src="docs/settings_preview.png" alt="Adhkar tab" width="48%">
  <img src="docs/prayer_tab_preview.png" alt="Prayer times tab" width="48%">
</p>

## Download

Get the latest installer (`Adhkar_Setup.exe`) from the [Releases](../../releases) page.

> The installer and executable are not code-signed, so Windows SmartScreen may show a warning. Choose **More info → Run anyway**.

## Run from source

Requirements: Windows and Python 3.10+ (developed and tested with 3.12).

```bash
pip install -r requirements.txt
python adhkar_app.py
```

### Font

The interface uses the Thmanyah font. The font file is not included in this repository: put the `.otf`/`.ttf` file in `fonts/` and the app loads it automatically. Without it the app falls back to Segoe UI. Please check the font's license before redistributing it.

## Build

```bash
build.bat              # builds dist\Adhkar.exe (PyInstaller)
build_installer.bat    # builds the exe, then installer_output\Adhkar_Setup.exe (Inno Setup 6)
```

`build_installer.bat` can install Inno Setup for you through `winget` if it isn't found. The build bundles `tzdata` so time zones work in the packaged exe.

## Tests

```bash
python -m unittest discover -s tests -v
```

169 unit tests cover the calculation (checked against published timetables), the countdown and iqama cycle, notification de-duplication, sleep/clock-change handling, location parsing, display formats, config persistence and the UI logic (with fake widgets, no GUI needed). The actual rendering, animation, mouse hover and sound are verified by hand: see [docs/TESTING_WINDOWS.md](docs/TESTING_WINDOWS.md).

To watch a full prayer cycle without waiting, run the app with a fake clock and an isolated data folder:

```bat
test_mode.bat 2026-10-11T15:23:00+03:00
```

## Importing adhkar from a text file

One dhikr per line:

```text
سُبْحَانَ اللَّهِ وَبِحَمْدِهِ
الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ
اللَّهُ أَكْبَرُ
```

Click **Import adhkar from a text file** (or drop the file on the window) and press **Save**. A sample is in [`sample/adhkar_sample.txt`](sample/adhkar_sample.txt).

## Data and privacy

Settings are stored in `%APPDATA%\Adhkar\data.json` and notification state in `prayer_state.json` next to it. Prayer times are computed locally. Network access happens **only** when you ask for it (automatic location or city search) and uses these services:

| Purpose | Service |
|---|---|
| Automatic location | Windows Location Service (Microsoft); `ipwho.is` / `ipapi.co` as an approximate fallback |
| City search and time zone | [Open-Meteo](https://open-meteo.com) |
| City name from coordinates | [OpenStreetMap Nominatim](https://nominatim.org) |

## Built-in adhkar and references

| Dhikr | Reference |
|---|---|
| سبحان الله وبحمده، سبحان الله العظيم | Bukhari 6406, Muslim 2694 |
| لا حول ولا قوة إلا بالله | Bukhari 6409, Muslim 2704 |
| سبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر | Muslim 2137 |
| اللهم صل وسلم على نبينا محمد | Muslim 408 (virtue of sending blessings upon the Prophet) |
| رضيت بالله ربا، وبالإسلام دينا، وبمحمد رسولا | Abu Dawud 1529, Muslim 1884 |
| سبحان الله وبحمده، أستغفر الله وأتوب إليه | Muslim 484 |
| أستغفر الله وأتوب إليه | Bukhari 6307 |
| لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير | Bukhari 3293, Muslim 2691 |
| حسبي الله لا إله إلا هو عليه توكلت وهو رب العرش العظيم | Qur'an 9:129 |

References are provided for convenience; please verify them against trusted hadith sources.

## Notes on prayer times

- The astronomical formulas follow the well-known [PrayTimes.org](http://praytimes.org) method, re-implemented in Python.
- Times can differ by a minute or two from your local mosque's timetable; use the per-prayer adjustment to match it.
- Umm al-Qura adds 30 minutes to Isha in Ramadan. This is not applied automatically: set the Isha adjustment to +30 during Ramadan.
- The default iqama durations are approximate and editable, not official iqama times.

## Tech stack

Python · PySide6 (Qt for Python) · PyInstaller · Inno Setup · `unittest`

## Project structure

```text
adhkar_app.py          UI: tabs, capsule notification, tray, settings
prayer_times.py        Qt-free logic: calculation, engine, iqama, notices, location
tests/                 unit tests (no GUI required)
build.bat              build the executable
build_installer.bat    build the executable and the installer
adhkar_setup.iss       Inno Setup script
test_mode.bat          run with a fake clock and isolated data
assets/ sample/ docs/  icon, sample text file, images and guides
fonts/                 put the Thmanyah font here
```

## License

[MIT](LICENSE)
