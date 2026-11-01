#!/usr/bin/env bash
# Builds the Go WireGuard engine into build/relaywg.aar (gomobile).
# Needs: Go 1.25+, Android SDK (ANDROID_HOME) and NDK r27 (ANDROID_NDK_HOME), unzip.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$repo/build"

ndk="${ANDROID_NDK_HOME:-${ANDROID_NDK_LATEST_HOME:-}}"
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -n "$ndk" && -d "$ndk" ]] || { echo "ERROR: ANDROID_NDK_HOME is not set or does not exist." >&2; exit 2; }
[[ -n "$sdk" && -d "$sdk" ]] || { echo "ERROR: ANDROID_HOME is not set or does not exist." >&2; exit 2; }
export ANDROID_NDK_HOME="$ndk" ANDROID_HOME="$sdk"
# gomobile installs its own helper and may want a newer Go than the runner has.
export GOTOOLCHAIN=auto

cd "$repo"
go version
# Pin gomobile to the x/mobile version already locked in go.mod (never @latest).
mobile_version="$(go list -m -f '{{.Version}}' golang.org/x/mobile)"
echo "gomobile ${mobile_version}"
go install "golang.org/x/mobile/cmd/gomobile@${mobile_version}"
go install "golang.org/x/mobile/cmd/gobind@${mobile_version}"
export PATH="$(go env GOPATH)/bin:$PATH"
gomobile init

mkdir -p "$out"
rm -f "$out/relaywg.aar"
# max-page-size=16384: Android 15 devices with 16 KB pages cannot load 4 KB-aligned libraries.
gomobile bind -target=android/arm64,android/arm,android/amd64,android/386 \
  -androidapi 26 \
  -ldflags='-s -w -extldflags=-Wl,-z,max-page-size=16384' \
  -o "$out/relaywg.aar" .

[[ -s "$out/relaywg.aar" ]] || { echo "ERROR: relaywg.aar is missing or empty" >&2; exit 1; }

# The alignment flag has no visible effect until a 16 KB device refuses to load the library,
# so check the ELF program headers of the 64-bit builds.
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
unzip -q "$out/relaywg.aar" -d "$work"
readelf_bin="$(command -v readelf || true)"
[[ -n "$readelf_bin" ]] || readelf_bin="$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
bad=0
while IFS= read -r so; do
  abi="$(basename "$(dirname "$so")")"
  case "$abi" in arm64-v8a | x86_64) ;; *) continue ;; esac
  for align in $("$readelf_bin" -lW "$so" | awk '$1=="LOAD" {print $NF}'); do
    if [[ "$align" != "0x4000" && "$align" != "0x10000" ]]; then
      echo "ERROR: $abi LOAD alignment $align will not load on a 16 KB-page device" >&2
      bad=1
    fi
  done
done < <(find "$work" -name '*.so')
[[ "$bad" -eq 0 ]] || exit 1

ls -l "$out/relaywg.aar"
echo "OK: $out/relaywg.aar"
