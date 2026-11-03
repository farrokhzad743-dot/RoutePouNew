"""The web app (GitHub Pages) must be self-consistent: files exist, copy is complete in both languages, nothing inline."""
import json
import re
import shutil
import struct
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def png_size(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path.name
    return struct.unpack(">II", data[16:24])


def strings():
    text = (ROOT / "strings.js").read_text(encoding="utf-8")
    body = text[text.index("{"): text.rindex("}") + 1]
    return json.loads(body)


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local, self.inline_scripts, self.i18n, self.i18n_aria = [], 0, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and not a.get("src"):
            self.inline_scripts += 1
        for key in ("src", "href"):
            v = a.get(key)
            if v and not re.match(r"^(https?:|#|data:|mailto:)", v) and tag in ("script", "link", "img", "image"):
                self.local.append(v)
        if "data-i18n" in a:
            self.i18n.append(a["data-i18n"])
        if "data-i18n-aria" in a:
            self.i18n_aria.append(a["data-i18n-aria"])


def parsed():
    p = Refs()
    p.feed(INDEX)
    return p


def test_every_local_file_the_page_uses_exists():
    for ref in parsed().local:
        assert (ROOT / ref.split("?")[0]).is_file(), ref


def test_page_has_no_inline_script_and_a_strict_csp():
    assert parsed().inline_scripts == 0
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', INDEX).group(1)
    assert "script-src 'self'" in csp and "object-src 'none'" in csp and "unsafe-inline" not in csp
    # the only outside hosts the page may talk to are the two IP lookup services
    hosts = set(re.findall(r"https://([a-z.]+)", csp))
    assert hosts == {"api.ipify.org", "ipwho.is"}


def test_persian_and_english_copy_are_complete_and_cover_every_key_used():
    s = strings()
    assert set(s["fa"]) == set(s["en"])
    p = parsed()
    for key in set(p.i18n) | set(p.i18n_aria):
        assert key in s["fa"], key
    for lang in ("fa", "en"):
        assert all(v.strip() for v in s[lang].values()), lang
    # app.js looks these up by name
    js = (ROOT / "app.js").read_text(encoding="utf-8")
    for key in set(re.findall(r'"((?:check|inst|nav)\.[a-z.]+)"', js)):
        assert key in s["fa"], key
    # the page itself is rendered in Persian: its text must equal the fa copy
    for key in ("hero.title", "how.1.t", "faq.6.q"):
        assert s["fa"][key].replace("&", "&amp;") in INDEX or s["fa"][key] in INDEX


def test_manifest_icons_exist_with_the_declared_size():
    m = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["display"] == "standalone" and m["start_url"] == "./" and m["scope"] == "./"
    purposes = set()
    for icon in m["icons"]:
        w, h = png_size(ROOT / icon["src"])
        assert f"{w}x{h}" == icon["sizes"], icon
        purposes.add(icon["purpose"])
    assert purposes == {"any", "maskable"}
    assert {i["sizes"] for i in m["icons"]} >= {"192x192", "512x512"}


def test_service_worker_precaches_existing_files_and_ignores_other_origins():
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    files = re.findall(r'"([^"]+)"', re.search(r"var FILES = \[(.*?)\];", sw, re.S).group(1))
    for f in files:
        assert f == "./" or (ROOT / f).is_file(), f
    assert "url.origin !== self.location.origin" in sw  # never cache or intercept the IP lookups
    assert ".nojekyll" in {p.name for p in ROOT.iterdir()}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("name", ["app.js", "sw.js", "strings.js"])
def test_javascript_parses(name):
    subprocess.run(["node", "--check", str(ROOT / name)], check=True, capture_output=True)


def test_readme_download_buttons_match_the_names_the_workflow_publishes():
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = (ROOT / "app.js").read_text(encoding="utf-8")
    for name in ("RoutePou-android.apk", "RoutePou-windows-x64.exe"):
        assert name in workflow and name in readme and name in page, name
        assert f"releases/latest/download/{name}" in readme
        assert f"releases/latest/download/{name}" in INDEX
    assert "prerelease: false" in workflow and "make_latest: true" in workflow
    for img in re.findall(r'src="([^"]+\.png)"', readme):
        if not img.startswith("http"):
            assert (ROOT / img).is_file(), img
    assert (ROOT / "og-image.png").is_file() and png_size(ROOT / "og-image.png") == (1200, 630)


def test_set_repo_rewrites_every_link(tmp_path):
    for name in ("README.md", "README.fa.md", "index.html", "app.js", "set-repo.py"):
        shutil.copy(ROOT / name, tmp_path / name)
    subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "Someone/Other-Repo"], check=True, capture_output=True)
    for name in ("README.md", "README.fa.md", "index.html", "app.js"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "Mahdi-mortazavi" not in text and "mahdi-mortazavi" not in text, name
    assert "someone.github.io/Other-Repo" in (tmp_path / "README.md").read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "not a slug"], capture_output=True)
    assert bad.returncode == 2


def test_page_shows_the_release_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert f'id="ver">{version}<' in INDEX
