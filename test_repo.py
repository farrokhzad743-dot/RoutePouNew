"""Release-readiness guards: things that silently break a public build."""
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
WORKFLOW = ROOT / ".github/workflows/build.yml"


def test_version_is_consistent():
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", VERSION)
    gradle = (ROOT / "android-build.gradle.kts").read_text(encoding="utf-8")
    assert f'versionName = "{VERSION}"' in gradle
    minor = int(VERSION.split("-")[0].split(".")[1])
    assert f"versionCode = {minor}" in gradle
    assert f'APP_VERSION = "{VERSION}"' in (ROOT / "routepou_windows.py").read_text(encoding="utf-8")
    assert f"## {VERSION}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"`{VERSION}`" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_workflow_is_valid_and_references_existing_files():
    text = WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert set(data["jobs"]) == {"python-tests", "go-engine", "android", "windows", "release"}
    for step in (s for job in data["jobs"].values() for s in job["steps"]):
        assert "run" in step or "uses" in step
    for rel in re.findall(r"bash ([\w.-]+\.sh)", text):
        assert (ROOT / rel).is_file(), rel
    for rel in ("go.sum", "routepou.ico", "routepou_windows.py", "VERSION", "CHANGELOG.md", "winclient"):
        assert (ROOT / rel).exists(), rel
    assert "needs: [python-tests, android, windows]" in text
    assert "PYTHONUTF8" in text


def test_shell_scripts_are_valid_and_invoked_through_bash():
    """Web uploads drop the executable bit, so the workflow must call `bash script.sh`."""
    for script in ROOT.glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True)
        assert b"\r\n" not in script.read_bytes(), f"{script.name} has CRLF line endings"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"run:\s*\./\S+\.sh", text)
    assert "bash build-aar.sh" in text and "bash stage-android.sh" in text


def test_stage_script_produces_a_standard_android_project(tmp_path):
    out = tmp_path / "stage"
    subprocess.run(["bash", str(ROOT / "stage-android.sh"), str(out)], check=True, capture_output=True)
    java = out / "src/main/java/com/pou/routepou"
    assert len(list(java.glob("*.kt"))) == len(list(ROOT.glob("*.kt")))
    for rel in ("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "proguard-rules.pro",
                "src/main/AndroidManifest.xml", "src/main/res/mipmap-anydpi-v26/ic_launcher.xml",
                "src/main/res/drawable-nodpi/ic_launcher_foreground.png", "src/main/res/values/styles.xml"):
        assert (out / rel).is_file(), rel


def test_every_kotlin_package_matches_the_namespace():
    for kt in ROOT.glob("*.kt"):
        pkg = re.search(r"^package\s+([\w.]+)", kt.read_text(encoding="utf-8"), re.M)
        # stage-android.sh copies every file into one folder and MainActivity uses the other classes without
        # imports, so a different package (such as `.pairing`) breaks the Gradle build with "Unresolved reference".
        assert pkg and pkg.group(1) == "com.pou.routepou", kt.name


def test_go_layout_is_one_module():
    assert not list(ROOT.rglob("go.mod")) == [] and len(list(ROOT.rglob("go.mod"))) == 1
    for go in ROOT.glob("*.go"):
        assert re.search(r"^package relaywg$", go.read_text(encoding="utf-8"), re.M), go.name
    mod = (ROOT / "go.mod").read_text(encoding="utf-8")
    sums = (ROOT / "go.sum").read_text(encoding="utf-8")
    for path, version in re.findall(r"^\s*(\S+\.\S+/?\S*)\s+(v\S+)", mod, re.M):
        assert f"{path} {version}/go.mod h1:" in sums, f"go.sum lacks {path} {version}"
    # Windows tests must not import the engine from an undeclared remote path.
    module = re.search(r"^module (\S+)", mod, re.M).group(1)
    for go in (ROOT / "winclient").glob("*.go"):
        for imp in re.findall(r'"(github\.com/[^"]+)"', go.read_text(encoding="utf-8")):
            assert imp.startswith(module) or imp.split("/")[0] != "github.com" or imp in mod, (go.name, imp)


def test_repo_has_no_stray_files_and_stays_flat():
    allowed_dirs = {".github", "res", "winclient", "build", "__pycache__", ".pytest_cache", ".git"}
    assert {p.name for p in ROOT.iterdir() if p.is_dir()} <= allowed_dirs
    for name in ("LICENSE", "README.md", "README.fa.md", "PUBLISHING.md", "SECURITY.md", "TESTING.md",
                 "THIRD_PARTY_NOTICES.md", "FONT_LICENSES.txt", "logo.png", ".gitignore", "index.html", "site.css",
                 "site.js", "CNAME", ".nojekyll", "hero.png", "og-image.png", "set-repo.py"):
        assert (ROOT / name).is_file(), name
    assert "GNU GENERAL PUBLIC LICENSE" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("build/", "*.jks", "*.p12", "__pycache__/"):
        assert pattern in ignore


def test_workflows_folder_contains_exactly_one_workflow():
    """A stale `build.xml` copy once sat next to build.yml. GitHub ignores it, but it shows an older build."""
    files = sorted(p.name for p in (ROOT / ".github" / "workflows").iterdir())
    assert files == ["build.yml"], files


def test_workflow_cleanup_step_covers_every_file_removed_from_the_project():
    """GitHub's web upload never deletes files. The CI jobs remove these leftovers in their own checkout, and
    PUBLISHING.md tells the owner to delete them from the repository."""
    removed = ["test_pwa.py", "app.js", "app.css", "strings.js", "sw.js", "manifest.webmanifest", "icon-512.png",
               "icon-maskable-512.png", "btn-web.png", ".github/workflows/build.xml", "res/drawable-nodpi/none",
               "Estedad-Regular.woff2", "Estedad-Medium.woff2", "Estedad-Bold.woff2", "Estedad-ExtraBold.woff2",
               "Inter-Regular.woff", "Inter-SemiBold.woff", "Inter-Bold.woff", "Inter-ExtraBold.woff"]
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    publishing = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")
    for name in removed:
        assert workflow.count(name) == 2, f"{name}: must be removed in both the python-tests and the android job"
        assert name in publishing, f"{name}: missing from the delete list in PUBLISHING.md"
        assert not (ROOT / name).exists(), f"{name} is part of the project again"


def test_stage_script_leaves_out_files_that_are_not_valid_android_resources(tmp_path):
    """AGP stops with "The file name must end with .xml or .png" on an extensionless file in res/ (for example the
    `none` placeholder that was created in the GitHub web editor). The stage script drops such files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for item in ROOT.iterdir():
        if item.name in {".git", "build", "__pycache__", ".pytest_cache"}:
            continue
        if item.is_dir():
            subprocess.run(["cp", "-r", str(item), str(repo / item.name)], check=True)
        else:
            subprocess.run(["cp", str(item), str(repo / item.name)], check=True)
    (repo / "res/drawable-nodpi/none").write_text("none\n")
    (repo / "res/values/.DS_Store").write_text("x")
    out = tmp_path / "stage"
    result = subprocess.run(["bash", str(repo / "stage-android.sh"), str(out)], check=True, capture_output=True, text=True)
    staged = {p.name for p in (out / "src/main/res").rglob("*") if p.is_file()}
    assert "none" not in staged and ".DS_Store" not in staged
    assert {"ic_launcher_foreground.png", "ic_launcher.xml", "styles.xml", "colors.xml"} <= staged
    assert "left out of the build" in result.stdout


def test_release_can_be_started_with_a_button_and_is_not_blocked_by_the_tests():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = data.get("on", data.get(True))
    assert triggers["workflow_dispatch"]["inputs"]["publish"]["type"] == "boolean"
    condition = data["jobs"]["release"]["if"]
    assert "workflow_dispatch" in condition and "refs/tags/v" in condition
    assert "needs.windows.result == 'success'" in condition
    assert "python-tests.result" not in condition, "a red test must not keep the working EXE from being published"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "tag_name: v${{ env.VERSION }}" in text
    assert 'git push -f origin "refs/tags/v${VERSION}"' in text


def test_publishing_guide_explains_the_button_release_and_the_old_fonts():
    text = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")
    assert "Run workflow" in text and "Publish the finished builds" in text
    for name in ("Estedad-Regular.woff2", "Inter-Regular.woff"):
        assert name in text


def test_android_job_uses_the_sdk_on_the_runner_and_a_fixed_image():
    """The helper action android-actions/setup-android@v3 stopped the job with "Failed to find package 'tools'"
    (sdkmanager no longer has that package). The runner image already contains the SDK, so sdkmanager is called directly."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["android"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert not any("android-actions" in str(step.get("uses", "")) for step in job["steps"])
    install = next(step for step in job["steps"] if step.get("name", "").startswith("Install Android platform"))
    for needle in ('platforms;android-${ANDROID_COMPILE_SDK}', 'build-tools;${ANDROID_BUILD_TOOLS}',
                   'ndk;${ANDROID_NDK_VERSION}', "ANDROID_HOME=$SDK", "--licenses"):
        assert needle in install["run"], needle
    assert "packages: tools" not in WORKFLOW.read_text(encoding="utf-8")
