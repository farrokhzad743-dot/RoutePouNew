"""The download website (GitHub Pages, routepou.pouone.ir) must be self-consistent:
files exist, both languages are complete, nothing is inline, and every download link points at this repository."""
import re
import struct
import subprocess
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "site.css").read_text(encoding="utf-8")
SLUG = "farrokhzad743-dot/RoutePouNew"
RELEASE = f"https://github.com/{SLUG}/releases/latest/download"
DOMAIN = "routepou.pouone.ir"


def png_size(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path.name
    return struct.unpack(">II", data[16:24])


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local, self.inline_scripts, self.inline_styles, self.links = [], 0, 0, []
        self.fa, self.en, self.ids = 0, 0, set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and not a.get("src"):
            self.inline_scripts += 1
        if tag == "style" or "style" in a:
            self.inline_styles += 1
        for key in ("src", "href"):
            v = a.get(key)
            if v and not re.match(r"^(https?:|#|data:|mailto:)", v) and tag in ("script", "link", "img"):
                self.local.append(v)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if a.get("data-l") == "fa":
            self.fa += 1
        if a.get("data-l") == "en":
            self.en += 1
        if "id" in a:
            self.ids.add(a["id"])


def page():
    p = Page()
    p.feed(INDEX)
    return p


def test_every_local_file_the_page_uses_exists():
    for ref in page().local:
        assert (ROOT / ref.split("?")[0]).is_file(), ref
    for ref in re.findall(r'url\("([^"]+)"\)', CSS):
        assert (ROOT / ref).is_file(), ref


def test_page_has_no_inline_script_or_style_and_a_strict_csp():
    p = page()
    assert p.inline_scripts == 0 and p.inline_styles == 0
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', INDEX).group(1)
    assert "script-src 'self'" in csp and "default-src 'none'" in csp and "unsafe-inline" not in csp
    assert not re.search(r"https?://", csp), "the page must not load anything from other hosts"


def test_persian_and_english_copy_are_paired():
    p = page()
    assert p.fa == p.en and p.fa > 30
    assert 'lang="fa" dir="rtl"' in INDEX  # Persian is the default


def test_download_links_point_at_this_repository():
    links = page().links
    assert f"{RELEASE}/RoutePou-windows-x64.exe" in links
    assert f"{RELEASE}/RoutePou-android.apk" in links
    for href in links:
        if "github.com" in href:
            assert href.startswith(f"https://github.com/{SLUG}"), href


def test_back_link_to_the_main_site():
    assert "https://pouone.ir" in page().links
    assert "بازگشت به سایت pouone.ir" in INDEX and "Back to pouone.ir" in INDEX


def test_no_foreign_names_in_the_site_files():
    for name in ("index.html", "site.css", "site.js", "README.md", "README.fa.md", "PUBLISHING.md", "set-repo.py"):
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "mahdi" not in text and "mortazavi" not in text, name


def test_in_page_anchors_exist():
    p = page()
    for href in p.links:
        if href.startswith("#") and len(href) > 1:
            assert href[1:] in p.ids, href


def test_custom_domain_files():
    assert (ROOT / "CNAME").read_text(encoding="utf-8").strip() == DOMAIN
    assert (ROOT / ".nojekyll").is_file()
    assert f"https://{DOMAIN}/" in INDEX


def test_fonts_are_bundled_with_their_license():
    for name in ("Estedad-Regular.woff2", "Estedad-Medium.woff2", "Estedad-Bold.woff2", "Estedad-ExtraBold.woff2",
                 "Inter-Regular.woff", "Inter-SemiBold.woff", "Inter-Bold.woff", "Inter-ExtraBold.woff"):
        assert (ROOT / name).stat().st_size > 10_000, name
    lic = (ROOT / "FONT_LICENSES.txt").read_text(encoding="utf-8")
    assert "Estedad" in lic and "Inter" in lic and "SIL OPEN FONT LICENSE" in lic
    assert "Estedad" in CSS and "Inter" in CSS


def test_page_is_light_and_respects_reduced_motion():
    assert "color-scheme: light" in CSS
    assert "prefers-reduced-motion: reduce" in CSS
    assert "prefers-color-scheme: dark" not in CSS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_parses():
    subprocess.run(["node", "--check", str(ROOT / "site.js")], check=True, capture_output=True)


def test_images_exist_with_the_expected_size():
    assert png_size(ROOT / "og-image.png") == (1200, 630)
    assert png_size(ROOT / "hero.png") == (1600, 640)
    for name in ("btn-windows", "btn-android", "btn-guide", "btn-windows-fa", "btn-android-fa"):
        assert png_size(ROOT / f"{name}.png") == (600, 128), name
    assert not (ROOT / "btn-web.png").exists()


def test_readme_download_buttons_match_the_names_the_workflow_publishes():
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_fa = (ROOT / "README.fa.md").read_text(encoding="utf-8")
    for name in ("RoutePou-android.apk", "RoutePou-windows-x64.exe"):
        assert name in workflow
        for doc in (readme, readme_fa, INDEX):
            assert f"{RELEASE}/{name}" in doc, name
    assert "prerelease: false" in workflow and "make_latest: true" in workflow
    for doc in (readme, readme_fa):
        for img in re.findall(r'src="([^"]+\.png)"', doc):
            if not img.startswith("http"):
                assert (ROOT / img).is_file(), img
    assert "btn-web" not in readme and "Open the web app" not in readme


def test_set_repo_rewrites_every_link(tmp_path):
    import sys
    for name in ("README.md", "README.fa.md", "index.html", "site.js", "PUBLISHING.md", "set-repo.py"):
        shutil.copy(ROOT / name, tmp_path / name)
    subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "Someone/Other-Repo"], check=True, capture_output=True)
    for name in ("README.md", "README.fa.md", "index.html", "site.js", "PUBLISHING.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "farrokhzad743-dot/RoutePouNew" not in text, name
    assert "github.com/Someone/Other-Repo/releases" in (tmp_path / "README.md").read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "not a slug"], capture_output=True)
    assert bad.returncode == 2


def test_page_shows_no_stale_version_text():
    # the page deliberately shows no version number: the download links always point at the latest release
    assert not re.search(r"\b0\.\d+\.\d+-beta\b", INDEX)
