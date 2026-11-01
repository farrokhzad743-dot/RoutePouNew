#!/usr/bin/env bash
# Copies the flat repository files into a standard Android Gradle project (default: build/android).
# Then build with:   cd build/android && gradle assembleDebug assembleRelease
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:-$repo/build/android}"
src="$out/src/main"

rm -rf "$out"
mkdir -p "$src/java/com/pou/routepou" "$src/res" "$out/libs"

shopt -s nullglob
kotlin=("$repo"/*.kt)
[[ ${#kotlin[@]} -ge 10 ]] || { echo "ERROR: expected the Kotlin sources next to this script, found ${#kotlin[@]}" >&2; exit 1; }
cp "${kotlin[@]}" "$src/java/com/pou/routepou/"
cp "$repo/AndroidManifest.xml" "$src/AndroidManifest.xml"
cp -r "$repo/res/." "$src/res/"
cp "$repo/android-build.gradle.kts"    "$out/build.gradle.kts"
cp "$repo/android-settings.gradle.kts" "$out/settings.gradle.kts"
cp "$repo/android-gradle.properties"   "$out/gradle.properties"
cp "$repo/proguard-rules.pro"          "$out/proguard-rules.pro"

if [[ -s "$repo/build/relaywg.aar" ]]; then
  cp "$repo/build/relaywg.aar" "$out/libs/relaywg.aar"
  echo "Included Full Tunnel engine (relaywg.aar)."
else
  echo "NOTE: build/relaywg.aar not found; the APK will build WITHOUT the Full Tunnel engine (proxy mode only)."
fi
echo "Android project staged at: $out"
