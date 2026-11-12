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


def webp_size(path: Path):
    """Width and height of a WebP file, read from its header (no imaging library needed)."""
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", path.name
    kind = data[12:16]
    if kind == b"VP8X":
        return (int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1)
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if kind == b"VP8 ":
        return (struct.unpack("<H", data[26:28])[0] & 0x3FFF, struct.unpack("<H", data[28:30])[0] & 0x3FFF)
    raise AssertionError(f"{path.name}: unknown WebP type {kind!r}")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local, self.inline_scripts, self.inline_styles, self.links = [], 0, 0, []
        self.fa, self.en, self.ids = 0, 0, set()
        self.text, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and not a.get("src"):
            self.inline_scripts += 1
        if tag == "style" or "style" in a:
            self.inline_styles += 1
        for key in ("src", "href"):
            v = a.get(key)
            if v and not re.match(r"^(https?:|#|data:|mailto:|\./?$)", v) and tag in ("script", "link", "img"):
                self.local.append(v)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("script", "style"):
            self._skip += 1
        if tag != "html" and a.get("lang") == "fa":
            self.fa += 1
        if tag != "html" and a.get("lang") == "en":
            self.en += 1
        if "id" in a:
            self.ids.add(a["id"])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


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


def test_download_links_point_at_files_next_to_the_page():
    # the two files are put beside index.html on the web host by hand; the buttons link to them directly
    links = page().links
    assert "RoutePou-windows-x64.exe" in links
    assert "RoutePou-android.apk" in links
    for href in links:
        if "github.com" in href:
            assert href.startswith(f"https://github.com/{SLUG}"), href


def test_back_link_to_the_main_site():
    assert "https://pouone.ir" in page().links
    assert "بازگشت به سایت pouone.ir" in INDEX and "Back to pouone.ir" in INDEX


def test_no_foreign_names_in_the_site_files():
    for name in ("index.html", "site.css", "site.js", "README.md", "README.en.md", "PUBLISHING.md", "set-repo.py"):
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "mahdi" not in text and "mortazavi" not in text, name


def test_page_shows_no_github_beta_or_version_wording():
    """The owner wants the page to read like a company site: no GitHub wording, no beta badge, no version text.
    (The download links themselves still point at the release files.)"""
    visible = " ".join(page().text).lower()
    for word in ("github", "beta", "alpha", "آلفا", "بتا", "gpl-3.0 license text", "pull request", "issue"):
        assert word not in visible, word
    assert not re.search(r"\b\d+\.\d+\.\d+\b", visible)
    assert "btn-web" not in INDEX and "Open the web app" not in INDEX


def test_page_has_the_sections_the_owner_asked_for():
    ids = page().ids
    assert {"download", "how", "app", "security", "license"} <= ids
    for word in ("TLS", "WireGuard", "GPL", "Vazirmatn", "SIL OFL", "MIT", "Apache-2.0"):
        assert word in INDEX, word


def test_in_page_anchors_exist():
    p = page()
    for href in p.links:
        if href.startswith("#") and len(href) > 1:
            assert href[1:] in p.ids, href


def test_custom_domain_files():
    assert (ROOT / "CNAME").read_text(encoding="utf-8").strip() == DOMAIN
    assert (ROOT / ".nojekyll").is_file()
    assert f"https://{DOMAIN}/" in INDEX


def test_one_font_only_small_and_bundled_with_its_license():
    """Two weights of Vazirmatn, reduced to the characters the page needs (about 23 KB each)."""
    for name in ("Vazirmatn-Regular.woff", "Vazirmatn-Bold.woff"):
        size = (ROOT / name).stat().st_size
        assert 10_000 < size < 40_000, (name, size)
        assert (ROOT / name).read_bytes()[:4] == b"wOFF", name
        assert f'href="{name}" as="font"' in INDEX and "crossorigin" in INDEX, "fonts must be preloaded"
    assert not list(ROOT.glob("Vazirmatn-*.woff2")), "the old full-size font files are not used any more"
    lic = (ROOT / "FONT_LICENSES.txt").read_text(encoding="utf-8")
    assert "Vazirmatn" in lic and "SIL OPEN FONT LICENSE" in lic
    families = set(re.findall(r'font-family:\s*"?([A-Za-z]+)"?', CSS))
    assert families == {"Vazirmatn"}, families   # "system-ui" in the stack is only the fallback
    assert "Estedad" not in CSS and "Inter" not in CSS
    assert "font-display: swap" in CSS


def test_style_is_plain_white_and_red():
    for effect in ("gradient", "box-shadow", "text-shadow", "blur(", "neon", "filter: drop-shadow"):
        assert effect not in CSS, effect
    assert "--red:" in CSS and "#d01f2f" in CSS.lower()


def luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def theme_colors():
    light = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", CSS.split(':root[data-theme="dark"]')[0]))
    dark_block = CSS.split(':root[data-theme="dark"]')[1].split("}")[0]
    dark = {**light, **dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", dark_block))}
    return light, dark


def test_page_has_a_light_and_a_dark_theme_with_readable_text():
    assert "color-scheme: light" in CSS and "color-scheme: dark" in CSS
    assert ':root[data-theme="dark"]' in CSS
    assert "prefers-color-scheme: dark" in CSS and ":root:not([data-theme])" in CSS, "no-JavaScript visitors follow the system"
    assert "prefers-reduced-motion: reduce" in CSS
    light, dark = theme_colors()
    for name, colors in (("light", light), ("dark", dark)):
        for text in ("ink", "muted", "red-text"):
            assert contrast(colors[text], colors["bg"]) >= 4.5, f"{name}: {text} on the background"
        assert contrast(colors["muted"], colors["soft"]) >= 4.5, f"{name}: muted on soft"
        assert contrast("#ffffff", colors["red"]) >= 4.5, f"{name}: white on the red button"
    init = (ROOT / "init.js").read_text(encoding="utf-8")
    assert 'setAttribute("data-theme"' in init and "prefers-color-scheme: dark" in init
    assert "routepou.site.theme" in init and "routepou.site.lang" in init
    js = (ROOT / "site.js").read_text(encoding="utf-8")
    assert 'id="themeBtn"' in INDEX and "themeBtn" in js and 'id="langBtn"' in INDEX and "langBtn" in js


def test_sections_open_in_layers_and_each_button_has_its_layer():
    html = page()
    buttons = re.findall(r'<button class="topic" type="button" data-open="(\w+)"', INDEX)
    assert buttons == ["how", "app", "security", "license"]
    for name in buttons:
        assert re.search(rf'<dialog class="layer" id="{name}" aria-labelledby="{name}-h">', INDEX), name
        assert f'id="{name}-h"' in INDEX
    assert INDEX.count("<dialog") == INDEX.count("</dialog>") == 4 and INDEX.count("data-close") == 4
    assert "showModal" in (ROOT / "site.js").read_text(encoding="utf-8")
    assert '<noscript><link rel="stylesheet" href="nojs.css"></noscript>' in INDEX and (ROOT / "nojs.css").is_file()
    # the home page itself has no long explanations: they live in the layers
    home = INDEX.split("<dialog", 1)[0]
    assert "TLS" not in home and "GPL" not in home and "WireGuard" not in home


def test_app_pictures_follow_the_theme_and_are_not_loaded_up_front():
    for name in ("app-android", "app-windows"):
        light, dark = ROOT / f"{name}.webp", ROOT / f"{name}-dark.webp"
        assert webp_size(light) == webp_size(dark) == ((688, 1520) if name == "app-android" else (1560, 1468)), name
        assert light.stat().st_size < 60_000 and dark.stat().st_size < 60_000, "pictures must stay small"
        assert f'data-shot="{name}"' in INDEX
    js = (ROOT / "site.js").read_text(encoding="utf-8")
    assert '"-dark"' in js and 'data-shot' in js
    assert re.findall(r"<img[^>]*data-shot[^>]*>", INDEX) and all('loading="lazy"' in tag for tag in re.findall(r"<img[^>]*data-shot[^>]*>", INDEX))
    # the pictures sit inside a layer, never on the home page
    assert "<dialog" in INDEX.split("data-shot", 1)[0]


def test_teaser_video_is_lazy_and_allowed_by_the_policy():
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', INDEX).group(1)
    assert "media-src 'self'" in csp and "unsafe-inline" not in csp
    tag = re.search(r"<video[^>]*>", INDEX).group(0)
    assert 'src="RoutePou-teaser.mp4"' in tag and 'preload="none"' in tag and "autoplay" not in tag and "controls" in tag
    assert ' poster=' not in tag and 'data-poster="teaser-poster.webp"' in tag, "the cover loads only when the layer opens"
    assert INDEX.index('id="how"') < INDEX.index("<video") < INDEX.index('id="app"'), "the video lives in the how-it-works layer"
    assert (ROOT / "RoutePou-teaser.mp4").stat().st_size < 4_000_000
    assert webp_size(ROOT / "teaser-poster.webp") == (1280, 720) and (ROOT / "teaser-poster.webp").stat().st_size < 60_000
    assert "data-poster" in (ROOT / "site.js").read_text(encoding="utf-8")


def test_first_view_is_small():
    """Everything the browser must fetch before the page is usable. The owner asked for a fast page."""
    needed = ["index.html", "init.js", "site.css", "site.js", "Vazirmatn-Regular.woff", "Vazirmatn-Bold.woff", "logo-small.webp"]
    total = sum((ROOT / name).stat().st_size for name in needed)
    assert total < 100_000, f"first view is {total} bytes"
    assert (ROOT / "site.css").stat().st_size < 12_000 and (ROOT / "site.js").stat().st_size < 8_000
    assert webp_size(ROOT / "logo-small.webp") == (72, 72) and (ROOT / "logo-small.webp").stat().st_size < 4_000
    assert 'src="logo-small.webp"' in INDEX and 'src="logo.png"' not in INDEX
    assert '<script src="site.js" defer></script>' in INDEX, "the main script must not block drawing"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_parses():
    for name in ("site.js", "init.js"):
        subprocess.run(["node", "--check", str(ROOT / name)], check=True, capture_output=True)


def test_images_exist_with_the_expected_size():
    assert png_size(ROOT / "og-image.png") == (1200, 630)
    assert png_size(ROOT / "hero.png") == (1600, 640)
    for name in ("btn-windows", "btn-android", "btn-guide", "btn-guide-en", "btn-windows-fa", "btn-android-fa"):
        assert png_size(ROOT / f"{name}.png") == (600, 128), name
    assert not (ROOT / "btn-web.png").exists()


def test_readme_download_buttons_match_the_names_the_workflow_publishes():
    workflows = {name: (ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8") for name in ("windows", "android")}
    publish = (ROOT / "publish-release.sh").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")
    for name, workflow in (("RoutePou-android.apk", workflows["android"]), ("RoutePou-windows-x64.exe", workflows["windows"])):
        assert name in workflow
        for doc in (readme, readme_en):
            assert f"{RELEASE}/{name}" in doc, name
        assert f'href="{name}" download' in INDEX, name  # the site links to the file beside it
    assert "--prerelease=false" in publish and "--latest" in publish
    for doc in (readme, readme_en):
        for img in re.findall(r'src="([^"]+\.png)"', doc):
            if not img.startswith("http"):
                assert (ROOT / img).is_file(), img
    assert "btn-web" not in readme and "Open the web app" not in readme


def test_set_repo_rewrites_every_link(tmp_path):
    import sys
    for name in ("README.md", "README.en.md", "index.html", "site.js", "PUBLISHING.md", "set-repo.py"):
        shutil.copy(ROOT / name, tmp_path / name)
    subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "Someone/Other-Repo"], check=True, capture_output=True)
    for name in ("README.md", "README.en.md", "index.html", "site.js", "PUBLISHING.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "farrokhzad743-dot/RoutePouNew" not in text, name
    assert "github.com/Someone/Other-Repo/releases" in (tmp_path / "README.md").read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(tmp_path / "set-repo.py"), "not a slug"], capture_output=True)
    assert bad.returncode == 2


def test_page_shows_no_stale_version_text():
    # the page deliberately shows no version number: the download links always point at the latest release
    assert not re.search(r"\b0\.\d+\.\d+-beta\b", INDEX)


def test_readme_is_persian_and_the_english_guide_is_one_button_away():
    persian = re.compile(r"[؀-ۿ]")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README.en.md").read_text(encoding="utf-8")
    assert 'href="README.en.md"' in readme and 'src="btn-guide-en.png"' in readme and 'alt="English guide"' in readme
    assert 'src="btn-windows-fa.png"' in readme and 'src="btn-android-fa.png"' in readme
    assert 'btn-guide.png' not in readme, "the Persian-guide button belongs on the English page"
    assert 'href="README.md"' in english and 'src="btn-guide.png"' in english and 'src="btn-windows.png"' in english
    body = re.sub(r"<[^>]+>|`[^`]*`|\[[^\]]*\]\([^)]*\)|https?://\S+", " ", readme)
    words = re.findall(r"[A-Za-z]{4,}", body)
    assert len(words) < 40, f"README.md should be Persian; English words found: {words[:20]}"
    english_body = re.sub(r'<img[^>]*>', " ", english)
    assert not persian.search(re.sub(r"<[^>]+>", " ", english_body)), "README.en.md should be English only"
    assert not (ROOT / "README.fa.md").exists()
