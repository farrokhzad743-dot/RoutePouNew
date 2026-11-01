#!/usr/bin/env bash
# Creates the private signing key for RoutePou Android releases and prints the values to store
# as GitHub repository secrets. Run ONCE, keep the .jks file and passwords somewhere safe:
# losing them means users can never update the app in place again.
set -euo pipefail
command -v keytool >/dev/null || { echo "keytool (JDK 17+) is required" >&2; exit 1; }
out="${1:-routepou-release.jks}"
alias_name="${2:-routepou}"
[[ ! -e "$out" ]] || { echo "$out already exists; refusing to overwrite" >&2; exit 1; }
read -r -s -p "Choose a keystore password (min 8 chars): " pass; echo
[[ ${#pass} -ge 8 ]] || { echo "password too short" >&2; exit 1; }
keytool -genkeypair -v -keystore "$out" -alias "$alias_name" -keyalg RSA -keysize 4096 \
  -validity 10000 -storepass "$pass" -keypass "$pass" -dname "CN=RoutePou, O=RoutePou"
cat <<MSG

Add these four GitHub secrets (Settings > Secrets and variables > Actions):
  ANDROID_KEYSTORE_BASE64   = $(base64 -w0 "$out" 2>/dev/null | cut -c1-24)...  (run: base64 -w0 $out)
  ANDROID_KEYSTORE_PASSWORD = the password you just typed
  ANDROID_KEY_ALIAS         = $alias_name
  ANDROID_KEY_PASSWORD      = the same password
Back up $out outside the repository. Never commit it.
MSG
