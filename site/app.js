/* Adhkar landing logic: i18n (AR default, EN), downloads, gallery, FAQ-a11y */
(function () {
  "use strict";

  const STR = {
    ar: {
      dir: "rtl", locale: "ar",
      metaTitle: "أذكار | Adhkar — أذكارك ومواقيت صلاتك على سطح مكتبك",
      metaDesc: "تطبيق ويندوز مجاني يعرض الأذكار الصحيحة ومواقيت الصلاة في كبسولة زجاجية هادئة على سطح المكتب.",
      skip: "تخطَّ إلى المحتوى",
      brandSub: "لويندوز",
      navFeatures: "المميزات", navHow: "كيف يعمل", navShots: "المعاينة",
      navDl: "التحميل", navFaq: "الأسئلة الشائعة", navDemo: "فيديو",
      langBtn: "EN", menu: "القائمة", themeLabel: "التبديل بين الوضع الفاتح والليلي",
      winBadge: "تطبيق سطح مكتب لويندوز",
      heroTitleA: "أذكارك ومواقيت صلاتك،",
      heroTitleB: "بهدوء على سطح مكتبك",
      heroLead: "تطبيق ويندوز خفيف يجلس في شريط النظام، ويعرض لك ذكرًا قصيرًا من الكتاب والسنة في كبسولة زجاجية لا تسحب التركيز، مع عدّاد الصلاة القادمة وتنبيهات الأذان والإقامة — كل ذلك يُحسب على جهازك.",
      dlPrimary: "تحميل التطبيق لويندوز",
      explore: "اكتشف المميزات",
      heroNote: "مجاني ومفتوح المصدر (MIT) · يعمل دون حساب · الإصدار ",
      
      featTitle: "مصمم للذكر دون إزعاج",
      featSub: "كل ميزة أدناه موجودة فعلًا في التطبيق وتم التحقق منها في الكود.",
      f1t: "كبسولة عائمة زجاجية", f1d: "إشعار دائري شفاف ينزل من أعلى الشاشة ثم يختفي، ولا يسرق تركيزك أبدًا.",
      f2t: "ثلاثة أوضاع للعرض", f2d: "ذكر فقط مع الظهور عند التمرير، أو الذكر مع العدّاد تحته، أو جنبًا إلى جنب.",
      f3t: "مواقيت الصلاة دون إنترنت", f3d: "حساب محلي من إحداثياتك بسبع طرق حساب وخيار عصر حنفي وتعديل لكل صلاة.",
      f4t: "تنبيه وإقامة", f4d: "إشعار قبل الأذان وعنده، ثم عدّاد إقامة مستقل لكل صلاة دون تكرار.",
      f5t: "تحكم كامل بالتوقيت", f5d: "فاصل بين الأذكار من دقيقة إلى يوم كامل، ومدة بقاء من ثانيتين إلى دقيقتين.",
      f6t: "أذكارك الخاصة", f6d: "أضف واحذف واستورد من ملف نصي أو بالسحب والإفلات، مع تجاهل المكرر.",
      f7t: "تخصيص المظهر", f7d: "حجم خط مستقل للواجهة والإشعار، وإغلاق بالنقر أو تمرير النقرات للخلف.",
      f8t: "موقع تلقائي أو يدوي", f8d: "اكتشاف عبر خدمة موقع ويندوز مع عرض الدقة، أو بحث عن مدينتك وإحداثيات دقيقة.",
      f9t: "يعمل في الخلفية", f9d: "يستقر في شريط النظام مع عرض الصلاة القادمة، وخيار التشغيل مع بدء ويندوز.",
      howTitle: "كيف يعمل؟",
      howSub: "ثلاث خطوات فقط، دون حسابات أو تعقيد.",
      s1t: "حمّل وثبّت على ويندوز", s1d: "اختر النسخة المحمولة أو المثبّت من قسم التحميل وشغّلها.",
      s2t: "اضبط موقعك وتفضيلاتك", s2d: "حدد مدينتك أو إحداثياتك، واختر طريقة الحساب وأوقات الظهور.",
      s3t: "استمتع بالذكر والمواقيت", s3d: "تابع الأذكار والعدّاد التنازلي للصلاة القادمة حسب إعداداتك.",
      shotsTitle: "معاينة التطبيق",
      shotsSub: "لقطات حقيقية من التطبيق أثناء العمل. انقر أي صورة لعرضها بحجم أكبر.",
      realTag: "لقطة حقيقية",
      r1: "إشعار دخول وقت الأذان على سطح المكتب",
      r2: "وضع الذكر مع الوقت المتبقي للصلاة القادمة",
      r3: "وضع الذكر والوقت بجانب بعضهما",
      r4: "تبويب الأذكار: قائمتك، الفاصل الزمني، وأحجام الخط",
      demoTitle: "شاهد التطبيق يعمل",
      demoSub: "تسجيل حقيقي للكبسولة على سطح مكتب ويندوز.",
      close: "إغلاق ✕",
      dlTitle: "حمّل أذكار لويندوز",
      dlLead: "اختر النسخة المناسبة لك. الملفان غير موقّعين رقميًا، فقد يعرض ويندوز تحذير SmartScreen — حمّل دائمًا من المصدر الرسمي فقط.",
      dlPortable: "النسخة المحمولة (تشغيل مباشر)",
      dlSetup: "المثبّت (تثبيت تقليدي)",
      dlSoon: "رابط التحميل لم يُنشر بعد — سيتوفر مع أول إصدار على GitHub Releases.",
      dlMetaVer: "الإصدار", dlMetaWin: "ويندوز 10 / 11",
      releases: "صفحة الإصدارات", source: "الكود المصدري",
      smartscreen: "عند ظهور تحذير SmartScreen لا تتجاوزه إلا إذا حمّلت الملف من المصدر الرسمي وتأكدت من سلامته.",
      faqTitle: "الأسئلة الشائعة",
      faqSub: "إجابات عن المؤكد فقط — ما لم نتأكد منه تركْناه قابلًا للتعديل.",
      q1: "هل التطبيق مجاني؟", a1: "نعم، مجاني تمامًا ومرخّص بترخيص MIT، ولا يحتاج حسابًا أو اشتراكًا.",
      q2: "ما نظام التشغيل المدعوم؟", a2: "ويندوز 10 و11 (طُوّر واختُبر على ويندوز مع بايثون 3.12). لا توجد نسخة للجوال أو الماك.",
      q3: "كيف أثبّت التطبيق؟", a3: "حمّل نسخة المثبّت Adhkar_Setup.exe وشغّلها واتبع المعالج، أو شغّل النسخة المحمولة Adhkar.exe مباشرة دون تثبيت.",
      q4: "هل يحتاج إلى الإنترنت؟", a4: "لا. المواقيت تُحسب محليًا على جهازك. الإنترنت يُستخدم فقط عندما تطلب ذلك: تحديد الموقع التلقائي أو البحث عن مدينة.",
      q5: "كيف أغيّر المدينة؟", a5: "من تبويب «مواقيت الصلاة والتنبيهات»: اختر الوضع اليدوي ثم ابحث عن مدينتك أو أدخل خط العرض وخط الطول واضغط اعتماد.",
      q6: "ماذا أفعل مع تحذير SmartScreen؟", a6: "الملف غير موقّع رقميًا لذلك قد يعرض ويندوز تحذيرًا. حمّل البرنامج من المصدر الرسمي فقط، وتأكد من اسم الملف وحجمه قبل التشغيل، ولا تتجاوز التحذير لملفات من مصادر مجهولة.",
      q7: "أين أجد التحديثات؟", a7: "من صفحة GitHub Releases الرسمية للمشروع — ستجد هناك أحدث إصدار وملاحظاته.",
      footTag: "أذكار قصيرة ومواقيت دقيقة، بهدوء.",
      footNav: "الأقسام", footDl: "التحميل", rights: "سامر شفيع. مرخّص بـ MIT.",
      notFound: "لم يتم العثور على الصفحة",
      toastDl: "رابط التحميل سيُضاف هنا بعد نشر أول إصدار على GitHub Releases."
    },
    en: {
      dir: "ltr", locale: "en",
      metaTitle: "Adhkar — Your adhkar and prayer times, quietly on your desktop",
      metaDesc: "A free Windows app showing authentic adhkar and prayer times in a calm glass capsule on your desktop.",
      skip: "Skip to content",
      brandSub: "for Windows",
      navFeatures: "Features", navHow: "How it works", navShots: "Preview",
      navDl: "Download", navFaq: "FAQ", navDemo: "Video",
      langBtn: "عربي", menu: "Menu", themeLabel: "Toggle light and dark mode",
      winBadge: "Windows desktop app",
      heroTitleA: "Your adhkar and prayer times,",
      heroTitleB: "quietly on your desktop",
      heroLead: "A lightweight Windows app living in the system tray. It shows a short authentic dhikr in a glass capsule that never steals focus, with a next-prayer countdown plus adhan and iqama notices — all computed on your machine.",
      dlPrimary: "Download for Windows",
      explore: "Explore features",
      heroNote: "Free and open source (MIT) · no account needed · version ",
      
      featTitle: "Built for remembrance, not distraction",
      featSub: "Every feature below actually exists in the app and was verified in the code.",
      f1t: "Floating glass capsule", f1d: "A frosted pill slides down from the top of the screen, then disappears — never stealing focus.",
      f2t: "Three display modes", f2d: "Dhikr only (revealed on hover), dhikr with countdown below, or side by side.",
      f3t: "Offline prayer times", f3d: "Computed locally from your coordinates with seven methods, Hanafi Asr and per-prayer tweaks.",
      f4t: "Pre-adhan notice & iqama", f4d: "A reminder before the adhan, a notice at adhan, then a per-prayer iqama countdown — never repeated.",
      f5t: "Full timing control", f5d: "Dhikr interval from 1 minute to a full day; display time from 2 to 120 seconds.",
      f6t: "Your own adhkar", f6d: "Add, delete and import from a text file or drag & drop, with duplicates skipped.",
      f7t: "Appearance tuning", f7d: "Separate font sizes for UI and notification; click-to-dismiss or click-through.",
      f8t: "Auto or manual location", f8d: "Detection via Windows Location Service with accuracy shown, or city search plus exact coordinates.",
      f9t: "Runs in the background", f9d: "Lives in the system tray showing the next prayer, with optional start-with-Windows.",
      howTitle: "How does it work?",
      howSub: "Three steps only — no accounts, no fuss.",
      s1t: "Download & install on Windows", s1d: "Pick the portable build or the installer from the download section and run it.",
      s2t: "Set your location & prefs", s2d: "Choose your city or coordinates, calculation method and display timings.",
      s3t: "Enjoy adhkar & prayer times", s3d: "Follow the adhkar and the next-prayer countdown per your settings.",
      shotsTitle: "App preview",
      shotsSub: "Real screenshots of the app in use. Click any image to enlarge it.",
      realTag: "real shot",
      r1: "Adhan notice on the desktop",
      r2: "Dhikr with the countdown of the next prayer",
      r3: "Side-by-side dhikr and time mode",
      r4: "The Adhkar tab: your list, the interval and the font sizes",
      demoTitle: "See the app in action",
      demoSub: "A real recording of the capsule on a Windows desktop.",
      close: "Close ✕",
      dlTitle: "Download Adhkar for Windows",
      dlLead: "Pick the build that suits you. Both files are unsigned, so Windows SmartScreen may warn — always download from the official source only.",
      dlPortable: "Portable (runs directly)",
      dlSetup: "Installer (classic setup)",
      dlSoon: "Download link not published yet — it will appear with the first GitHub Release.",
      dlMetaVer: "Version", dlMetaWin: "Windows 10 / 11",
      releases: "Releases page", source: "Source code",
      smartscreen: "If SmartScreen warns, proceed only when you downloaded the file from the official source and verified its name and size.",
      faqTitle: "FAQ",
      faqSub: "Answers cover verified matters only — anything unconfirmed was left editable.",
      q1: "Is the app free?", a1: "Yes — completely free under the MIT license, with no account or subscription.",
      q2: "Which OS is supported?", a2: "Windows 10 and 11 (developed and tested on Windows with Python 3.12). No mobile or Mac version.",
      q3: "How do I install it?", a3: "Download Adhkar_Setup.exe, run it and follow the wizard — or run the portable Adhkar.exe directly with no install.",
      q4: "Does it need the internet?", a4: "No. Prayer times are computed locally on your machine. Network is used only when you ask: auto location or city search.",
      q5: "How do I change the city?", a5: "In the “Prayer times & alerts” tab: switch to manual mode, search for your city or enter latitude/longitude and apply.",
      q6: "What about the SmartScreen warning?", a6: "The file is not code-signed so Windows may warn. Download only from the official source, check the file name and size before running, and never bypass the warning for files from unknown sources.",
      q7: "Where do I find updates?", a7: "On the project's official GitHub Releases page — the latest version and its notes live there.",
      footTag: "Short adhkar and accurate times, quietly.",
      footNav: "Sections", footDl: "Download", rights: "Samer Shafi. Licensed under MIT.",
      notFound: "Page not found",
      toastDl: "The download link will be added here after the first GitHub Release is published."
    }
  };

  const root = document.documentElement;
  let lang = "ar";
  try { lang = localStorage.getItem("adhkar-lang") || "ar"; } catch (e) { /* private mode */ }
  if (!STR[lang]) lang = "ar";

  function t(key) { return (STR[lang] && STR[lang][key]) || STR.ar[key] || key; }

  function applyLang(next) {
    if (next) lang = STR[next] ? next : "ar";
    const d = STR[lang];
    root.lang = d.locale;
    root.dir = d.dir;
    document.title = d.metaTitle;
    const md = document.querySelector('meta[name="description"]');
    if (md) md.setAttribute("content", d.metaDesc);
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
    // version label + download buttons state
    const cfg = window.SITE_CONFIG || {};
    document.querySelectorAll("[data-ver]").forEach(function (el) { el.textContent = cfg.version || ""; });
    setupDownloads();
    try { localStorage.setItem("adhkar-lang", lang); } catch (e) {}
  }

  function setupDownloads() {
    const cfg = window.SITE_CONFIG || {};
    [["dlPortableBtn", cfg.portable], ["dlSetupBtn", cfg.setup]].forEach(function ([id, item]) {
      const btn = document.getElementById(id);
      if (!btn || !item) return;
      const sizeEl = btn.querySelector("[data-size]");
      if (sizeEl && item.size) sizeEl.textContent = " · " + item.size;
      if (item.url) {
        btn.removeAttribute("disabled");
        btn.setAttribute("href", item.url);
        btn.onclick = null;
      } else {
        btn.setAttribute("href", "#download");
        btn.onclick = function (ev) { ev.preventDefault(); notify(t("toastDl")); };
      }
    });
    // hero button mirrors portable, falls back to setup, else notice
    const hero = document.getElementById("heroDlBtn");
    if (hero) {
      const url = (cfg.portable && cfg.portable.url) || (cfg.setup && cfg.setup.url) || "";
      if (url) { hero.setAttribute("href", url); hero.onclick = null; }
      else { hero.setAttribute("href", "#download"); hero.onclick = function (ev) { ev.preventDefault(); notify(t("toastDl")); }; }
    }
    // optional links: hide when empty
    [["releasesLink", cfg.releasesPage], ["sourceLink", cfg.sourceCode]].forEach(function ([id, url]) {
      const a = document.getElementById(id);
      if (!a) return;
      if (url) { a.style.display = ""; a.setAttribute("href", url); }
      else { a.style.display = "none"; }
    });
    // download-soon notice visibility
    const soon = document.getElementById("dlSoon");
    if (soon) {
      const any = (cfg.portable && cfg.portable.url) || (cfg.setup && cfg.setup.url);
      soon.style.display = any ? "none" : "";
    }
  }

  let toastTimer = null;
  function notify(msg) {
    let box = document.getElementById("toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "toast";
      box.setAttribute("role", "status");
      box.style.cssText = "position:fixed;bottom:22px;inset-inline:0;margin-inline:auto;max-width:min(520px,90vw);background:#14201b;color:#fff;padding:12px 20px;border-radius:12px;text-align:center;z-index:99;box-shadow:0 12px 32px rgba(0,0,0,.25)";
      document.body.appendChild(box);
    }
    box.textContent = msg;
    box.style.display = "block";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { box.style.display = "none"; }, 4200);
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyLang();
    const langBtn = document.getElementById("langBtn");
    if (langBtn) langBtn.addEventListener("click", function () {
      applyLang(lang === "ar" ? "en" : "ar");
    });
    // theme: default comes from the <head> script (saved choice, else system)
    function setTheme(dark) {
      if (dark) root.dataset.theme = "dark";
      else delete root.dataset.theme;
      try { localStorage.setItem("adhkar-theme", dark ? "dark" : "light"); } catch (e) {}
    }
    const themeBtn = document.getElementById("themeBtn");
    if (themeBtn) themeBtn.addEventListener("click", function () {
      setTheme(root.dataset.theme !== "dark");
    });
    const menuBtn = document.getElementById("menuBtn");
    const nav = document.getElementById("mainNav");
    if (menuBtn && nav) menuBtn.addEventListener("click", function () {
      nav.classList.toggle("open");
    });
    if (nav) nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") nav.classList.remove("open");
    });
    // lightbox
    const lb = document.getElementById("lightbox");
    const lbImg = document.getElementById("lightboxImg");
    document.querySelectorAll(".shot").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const img = btn.querySelector("img");
        if (!img || !lb || !lbImg) return;
        lbImg.src = img.src;
        lbImg.alt = img.alt;
        lb.classList.add("open");
        const c = document.getElementById("lightboxClose");
        if (c) c.focus();
      });
    });
    function closeLb() { if (lb) lb.classList.remove("open"); }
    if (lb) lb.addEventListener("click", function (e) { if (e.target === lb) closeLb(); });
    const lc = document.getElementById("lightboxClose");
    if (lc) lc.addEventListener("click", closeLb);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeLb(); });
    // reveal on scroll
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("visible"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
    // footer year/version
    const y = document.getElementById("year");
    if (y) y.textContent = new Date().getFullYear();
  });
})();
