"""Cheap guards for the Kotlin sources, since CI is the first real compile.

These catch the classes of mistake that have broken the build before: syntax newer than the
pinned Kotlin version, unbalanced brackets, and stray secrets.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KOTLIN = sorted(ROOT.glob("*.kt"))
PAIRS = {")": "(", "]": "[", "}": "{"}


def balanced(src: str) -> bool:
    """Bracket balance, skipping comments, char literals and (nested-template) strings."""
    stack, i, n = [], 0, len(src)

    def skip_string(i, raw):
        # i points just after the opening quote(s); returns index after the closing quote(s).
        while i < n:
            c = src[i]
            if raw:
                if src.startswith('"""', i):
                    return i + 3
            else:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    return i + 1
            if src.startswith("${", i):
                depth, i = 1, i + 2
                while i < n and depth:
                    if src[i] == '"':
                        i = skip_string(i + 1, False)
                        continue
                    depth += (src[i] == "{") - (src[i] == "}")
                    i += 1
                continue
            i += 1
        return i

    while i < n:
        c = src[i]
        if src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
        elif src.startswith("/*", i):
            i = src.find("*/", i)
            i = n if i < 0 else i + 2
        elif src.startswith('"""', i):
            i = skip_string(i + 3, True)
        elif c == '"':
            i = skip_string(i + 1, False)
        elif c == "'":
            i = src.find("'", i + (3 if src[i + 1] == "\\" else 2)) + 1
        else:
            if c in "([{":
                stack.append(c)
            elif c in PAIRS:
                if not stack or stack.pop() != PAIRS[c]:
                    return False
            i += 1
    return not stack


def test_kotlin_sources_present():
    names = {p.name for p in KOTLIN}
    for expected in ("MainActivity.kt", "ProxyService.kt", "WireGuardService.kt", "WireGuardEngine.kt",
                     "TlsIdentity.kt", "RoutePouWgKeys.kt", "RoutePouWgConfig.kt",
                     "RoutePouPairingPayload.kt", "RoutePouUpstream.kt", "AndroidUpstreamMonitor.kt"):
        assert expected in names


def test_brackets_balance():
    for path in KOTLIN:
        assert balanced(path.read_text(encoding="utf-8")), f"unbalanced brackets in {path.name}"


def test_balance_checker_detects_errors():
    assert balanced('fun a() { val s = "x${f("y")}z" }')
    assert not balanced("fun a() { ")


def test_no_underscore_catch_parameters():
    # `catch (_: Exception)` is not accepted by the pinned Kotlin (2.0.x); name the parameter.
    for path in KOTLIN:
        assert not re.search(r"catch\s*\(\s*_\s*:", path.read_text(encoding="utf-8")), path.name


def test_no_hardcoded_secrets_or_keystores():
    assert not [p for pat in ("*.p12", "*.jks", "*.keystore", "*.pfx") for p in ROOT.rglob(pat)]
    for path in KOTLIN:
        assert "routepou-alpha-keystore" not in path.read_text(encoding="utf-8")


def test_proxy_uses_per_install_tls_identity():
    service = (ROOT / "ProxyService.kt").read_text(encoding="utf-8")
    activity = (ROOT / "MainActivity.kt").read_text(encoding="utf-8")
    identity = (ROOT / "TlsIdentity.kt").read_text(encoding="utf-8")
    assert "TlsIdentity.sslContext()" in service
    assert "TlsIdentity.fingerprint()" in activity and "TlsIdentity.regenerate()" in activity
    assert "AndroidKeyStore" in identity


def test_full_tunnel_wiring():
    activity = (ROOT / "MainActivity.kt").read_text(encoding="utf-8")
    service = (ROOT / "WireGuardService.kt").read_text(encoding="utf-8")
    engine = (ROOT / "WireGuardEngine.kt").read_text(encoding="utf-8")
    assert "RoutePouWgKeys.generate()" in activity and "RoutePouWgConfig.serverIpc(keys)" in activity
    assert "WireGuardEngine.start(ipc, upstream)" in service and "WireGuardEngine.stop()" in service
    assert 'CLASS_NAME = "relaywg.Relaywg"' in engine
    # Every method looked up reflectively must exist in the Go bridge (mobile.go).
    mobile = (ROOT / "mobile.go").read_text(encoding="utf-8")
    for method in re.findall(r'getMethod\("(\w+)"', engine) + re.findall(r'metric\("(\w+)"\)', engine):
        assert re.search(rf"^func {method[0].upper()}{method[1:]}\(", mobile, re.M), f"{method} missing in mobile.go"


def test_manifest_declares_services_and_icon():
    manifest = (ROOT / "AndroidManifest.xml").read_text(encoding="utf-8")
    for needle in (".MainActivity", ".ProxyService", ".WireGuardService", "@mipmap/ic_launcher",
                   "FOREGROUND_SERVICE_DATA_SYNC", "POST_NOTIFICATIONS"):
        assert needle in manifest
    assert (ROOT / "res/mipmap-anydpi-v26/ic_launcher.xml").is_file()
    assert (ROOT / "res/drawable-nodpi/ic_launcher_foreground.png").is_file()


def test_every_source_is_in_the_app_package_and_no_stray_resource_files():
    """The Gradle build failed once because three files were in `com.pou.routepou.pairing` while MainActivity
    used them without an import."""
    for path in KOTLIN:
        match = re.search(r"^package\s+([\w.]+)", path.read_text(encoding="utf-8"), re.M)
        assert match and match.group(1) == "com.pou.routepou", path.name
    # an extensionless placeholder in res/ is not a valid resource
    for res in (ROOT / "res").rglob("*"):
        if res.is_file():
            assert res.suffix, f"resource without extension: {res}"


def test_cross_file_references_resolve_within_the_package():
    """Every top-level class/object the Kotlin files use unqualified must be declared in the same package."""
    declared = set()
    for path in KOTLIN:
        declared |= set(re.findall(r"^(?:data\s+)?(?:class|object)\s+(\w+)", path.read_text(encoding="utf-8"), re.M))
    activity = (ROOT / "MainActivity.kt").read_text(encoding="utf-8")
    for name in ("RoutePouWgKeys", "RoutePouWgConfig", "RoutePouPairingPayload", "RoutePouUpstream", "TlsIdentity",
                 "WireGuardEngine", "WireGuardService", "ProxyService"):
        assert name in activity and name in declared, name
    assert not re.search(r"^import com\.pou\.routepou\.\w+\.", activity, re.M)
