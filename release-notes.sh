#!/usr/bin/env bash
# Prints the text of the GitHub release page for the version in the VERSION file.
# Used by publish-release.sh. Run it from the repository root:  bash release-notes.sh
set -euo pipefail
version="$(tr -d '[:space:]' < VERSION)"

echo "### دانلود"
echo "- **اندروید:** \`RoutePou-android.apk\` (اندروید ۸ یا بالاتر)"
echo "- **ویندوز:** \`RoutePou-windows-x64.exe\` (ویندوز ۱۰ و ۱۱، ۶۴ بیتی)"
echo "- گوشی و کامپیوتر باید به یک شبکه وصل باشند (یک وای‌فای، یا هات‌اسپات گوشی)."
echo "- کنار هر فایل، یک فایل \`.sha256\` برای بررسی سالم‌بودن دانلود هست."

# What changed in this version: the matching section of CHANGELOG.md (English), if there is one.
changes="$(awk -v v="## ${version}" 'index($0, v)==1 {p=1; next} /^## / {p=0} p' CHANGELOG.md 2>/dev/null || true)"
if [ -n "$(printf '%s' "$changes" | tr -d '[:space:]')" ]; then
  echo
  echo "### Changes"
  printf '%s\n' "$changes"
fi
