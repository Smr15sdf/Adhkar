# Adhkar website — تشغيل ونشر الموقع

الموقع في مجلد `site/` فقط، ولا يمسّ التطبيق المكتبي أو بناءه.

## التشغيل محليًا (Windows)

```bat
cd site
python -m http.server 8000
```

ثم افتح: http://localhost:8000

## أين تغيّر رابط التحميل ورقم الإصدار؟

ملف واحد فقط: **`site/config.js`**

```js
version: "1.0",
portable: { url: "https://github.com/OWNER/REPO/releases/download/v1.0/Adhkar.exe" },
setup:    { url: "https://github.com/OWNER/REPO/releases/download/v1.0/Adhkar_Setup.exe" },
releasesPage: "https://github.com/OWNER/REPO/releases",
sourceCode:   "https://github.com/OWNER/REPO"
```

- الرابط الفارغ = زر يعرض رسالة «سيتوفر مع أول إصدار» بدل رابط معطّل.
- `portable` = ملف `dist\Adhkar.exe` (تشغيل مباشر، ≈48MB).
- `setup` = ملف `installer_output\Adhkar_Setup.exe` (مثبّت، ≈49MB).
- لا ترفع ملفات EXE إلى المستودع — استضفها في **GitHub Releases**.

## النشر مجانًا (GitHub Pages)

1. أنشئ مستودع GitHub وادفع المشروع (تأكد أن `dist/` و`installer_output/` وخطوط `fonts/` مستثناة — هي كذلك في `.gitignore`).
2. ابنِ الملفات التنفيذية (`build.bat` ثم `build_installer.bat`) وأنشئ **Release** (وسم `v1.0`) وأرفق ملفي EXE.
3. انسخ روابط الأصول إلى `site/config.js` كما أعلاه.
4. فعّل Pages: إعدادات المستودع → Pages → فرع `main` ومجلد `/site`.
5. الموقع يعمل بمسارات نسبية، فيعمل على النطاق الجذري أو مسار المستودع دون تعديل.

## ما الذي ما زلت أحتاجه منك؟

- [x] اسم صاحب الحقوق: سامر شفيع (محدّث في التذييل وLICENSE).
- [x] فيديو العرض: `site/assets/demo.mp4` مضمّن في قسم #demo.
- [ ] احفظ لقطاتك الحقيقية في `site/screenshots/` بهذه الأسماء تمامًا:
  `capsule-adhan.png`، `capsule-stacked.png`، `capsule-side.png` — وستظهر تلقائيًا.
- [ ] رابط مستودع GitHub (لملء `releasesPage` و`sourceCode`).
- [ ] روابط أصول أول Release (لملء `portable.url` و`setup.url`).
- [ ] لقطات شاشة حقيقية: تم تجهيز أماكنها — ضع الملفات كما في `site/screenshots/README.md`.
- [ ] (تم) اسمك في الحقوق: سامر شفيع.
