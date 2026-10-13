/* ============================================================
 * Adhkar website — central settings.
 * عدّل هذا الملف فقط لتحديث روابط التحميل ورقم الإصدار.
 *
 * How to publish a release:
 *  1. Build:  build.bat  then  build_installer.bat
 *  2. On GitHub create a Release (e.g. tag v1.0) and attach:
 *       dist\Adhkar.exe            (portable, runs directly)
 *       installer_output\Adhkar_Setup.exe  (installer)
 *  3. Copy each asset's download URL below and redeploy the site.
 *  4. If a URL is empty/null, the site shows a "coming soon" notice
 *     instead of a broken link — never a fake download.
 * ============================================================ */
const SITE_CONFIG = {
  version: "1.0",
  repo: "https://github.com/Smr15sdf/Adhkar",
  // Approximate sizes measured 2026-10-13 (may change after rebuild):
  portable: {
    file: "Adhkar.exe",
    kind: "portable", // runs directly, no install
    size: "≈ 48 MB",
    url: "https://github.com/Smr15sdf/Adhkar/releases/download/v1.0/Adhkar.exe"
  },
  setup: {
    file: "Adhkar_Setup.exe",
    kind: "setup", // installer (Inno Setup)
    size: "≈ 49 MB",
    url: "https://github.com/Smr15sdf/Adhkar/releases/download/v1.0/Adhkar_Setup.exe"
  },
  // Optional links (leave empty to hide the button):
  releasesPage: "https://github.com/Smr15sdf/Adhkar/releases",
  sourceCode: "https://github.com/Smr15sdf/Adhkar",
  license: "MIT"
};
