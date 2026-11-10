"""Release-readiness guards: things that silently break a public build."""
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOWS = {name: WORKFLOW_DIR / f"{name}.yml" for name in ("tests", "windows", "android", "cleanup")}


def workflow_text(name):
    return WORKFLOWS[name].read_text(encoding="utf-8")


def triggers_of(name):
    data = yaml.safe_load(workflow_text(name))
    return data.get("on", data.get(True))


def test_version_is_consistent():
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", VERSION)
    gradle = (ROOT / "android-build.gradle.kts").read_text(encoding="utf-8")
    assert f'versionName = "{VERSION}"' in gradle
    minor = int(VERSION.split("-")[0].split(".")[1])
    assert f"versionCode = {minor}" in gradle
    assert f'APP_VERSION = "{VERSION}"' in (ROOT / "routepou_windows.py").read_text(encoding="utf-8")
    assert f"## {VERSION}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"`{VERSION}`" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_workflows_are_valid_and_reference_existing_files():
    expected_jobs = {"tests": {"python-tests", "go-engine"}, "windows": {"build", "publish"},
                     "android": {"build", "publish"}, "cleanup": {"remove"}}
    for name, path in WORKFLOWS.items():
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert set(data["jobs"]) == expected_jobs[name], name
        for step in (s for job in data["jobs"].values() for s in job["steps"]):
            assert "run" in step or "uses" in step
        for rel in re.findall(r"bash ([\w.-]+\.sh)", text):
            assert (ROOT / rel).is_file(), rel
        assert "PYTHONUTF8" in text or name in ("windows", "cleanup")
    for rel in ("go.sum", "routepou.ico", "routepou_windows.py", "VERSION", "CHANGELOG.md", "winclient",
                "publish-release.sh", "release-notes.sh", "old-files.txt"):
        assert (ROOT / rel).exists(), rel
    for name in ("windows", "android"):
        assert yaml.safe_load(workflow_text(name))["jobs"]["publish"]["needs"] == "build"


def test_windows_and_android_are_separate_workflows_that_do_not_wait_for_each_other():
    """One combined workflow hid which half failed. Each platform now builds and publishes on its own."""
    for name in ("windows", "android"):
        data = yaml.safe_load(workflow_text(name))
        text = workflow_text(name)
        assert "needs: [" not in text and "python-tests" not in text and "go-engine" not in text
        other = "gradle" if name == "windows" else "pyinstaller"
        assert other not in text.lower(), f"{name}.yml must not build the other platform"
        assert data["jobs"]["publish"]["permissions"] == {"contents": "write"}
        assert data["permissions"] == {"contents": "read"}
        assert "bash publish-release.sh" in text
        assert data["concurrency"]["cancel-in-progress"] is False, "a running publish must not be cancelled"
    assert "windows-latest" in workflow_text("windows") and "ubuntu-24.04" in workflow_text("android")
    assert "RoutePou-windows-x64.exe" in workflow_text("windows")
    assert "RoutePou-android.apk" in workflow_text("android")
    tests = yaml.safe_load(workflow_text("tests"))
    assert tests["permissions"] == {"contents": "read"}, "the test workflow must not be able to publish"
    assert "gh release" not in workflow_text("tests") and "publish-release" not in workflow_text("tests")


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


def test_workflows_folder_contains_exactly_the_four_workflows():
    """A stale `build.xml` and the old single `build.yml` once sat in this folder. These files replace them."""
    files = sorted(p.name for p in WORKFLOW_DIR.iterdir())
    assert files == ["android.yml", "cleanup.yml", "tests.yml", "windows.yml"], files


def old_files():
    lines = (ROOT / "old-files.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_old_files_are_listed_once_and_are_not_part_of_the_project():
    """GitHub's web upload never deletes files. old-files.txt names the leftovers: the CI jobs remove them in their
    own checkout, the "Remove old files" workflow removes them from the repository, PUBLISHING.md lists them."""
    names = old_files()
    assert len(names) == len(set(names)) >= 20
    publishing = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")
    for name in ("test_pwa.py", "app.js", "btn-web.png", "Estedad-Regular.woff2", "Inter-Regular.woff",
                 "res/drawable-nodpi/none", ".github/workflows/build.yml", ".github/workflows/build.xml"):
        assert name in names, name
    for name in names:
        assert not name.startswith("/") and ".." not in name, name
        assert not (ROOT / name).exists(), f"{name} is part of the project again"
        assert name in publishing, f"{name}: missing from the delete list in PUBLISHING.md"
    for workflow in ("tests", "android"):
        assert "old-files.txt" in workflow_text(workflow) and "xargs -r rm -f --" in workflow_text(workflow), workflow
        assert "Remove leftovers from older versions" in workflow_text(workflow)


def test_remove_old_files_workflow_deletes_only_listed_files_and_commits(tmp_path):
    """Run the workflow's script against a throw-away repository."""
    import os
    data = yaml.safe_load(workflow_text("cleanup"))
    script = [step["run"] for step in data["jobs"]["remove"]["steps"] if "run" in step][0]
    assert "workflow_dispatch" in triggers_of("cleanup") and "push" not in triggers_of("cleanup"), "manual only"
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    work.mkdir()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, check=True)
    (work / "old-files.txt").write_text("# comment\ntest_pwa.py\r\n../evil\n.github/workflows/build.yml\nmissing.txt\n", encoding="utf-8")
    (work / ".github/workflows").mkdir(parents=True)
    for name in ("test_pwa.py", "keep.py", ".github/workflows/build.yml"):
        (work / name).write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run([*git, "commit", "-qm", "x"], cwd=work, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=work, check=True)
    subprocess.run(["git", "push", "-q", "-u", "origin", "main"], cwd=work, check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    first = subprocess.run(["bash", "-e", "-c", script], cwd=work, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert not (work / "test_pwa.py").exists() and (work / "keep.py").exists()
    assert (work / ".github/workflows/build.yml").exists(), "workflow files must be left for the owner to delete"
    assert "must be deleted by hand" in first.stdout and "unsafe path" in first.stdout
    tree = subprocess.run(["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main"], check=True, capture_output=True, text=True).stdout
    assert "test_pwa.py" not in tree and "keep.py" in tree
    again = subprocess.run(["bash", "-e", "-c", script], cwd=work, env=env, capture_output=True, text=True)
    assert again.returncode == 0 and "Nothing to remove" in again.stdout


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


def test_each_platform_publishes_by_itself_and_can_be_started_with_a_button():
    for name in ("windows", "android"):
        data = yaml.safe_load(workflow_text(name))
        triggers = triggers_of(name)
        assert triggers["workflow_dispatch"]["inputs"]["publish"]["type"] == "boolean"
        assert triggers["push"]["branches"] == ["main", "master"]
        assert triggers["push"]["paths"], "a push that touches only the site must not rebuild the app"
        assert f".github/workflows/{name}.yml" in triggers["push"]["paths"], "editing the workflow must rebuild"
        assert "VERSION" in triggers["push"]["paths"]
        condition = data["jobs"]["publish"]["if"]
        assert "github.event_name == 'push'" in condition and "inputs.publish" in condition and "success()" in condition
        assert "python-tests" not in condition, "a red test must not keep a working build from being published"
    assert "'*.kt'" in workflow_text("android") and "res/**" in workflow_text("android")
    assert "routepou_windows.py" in workflow_text("windows") and "winclient/**" in workflow_text("windows")


def test_publish_script_moves_the_tag_and_attaches_files_to_the_latest_release(tmp_path):
    """publish-release.sh runs in both workflows. Run it here against a fake `gh` and a local git remote."""
    work = tmp_path / "work"
    work.mkdir()
    for name in ("publish-release.sh", "release-notes.sh", "VERSION", "CHANGELOG.md"):
        (work / name).write_bytes((ROOT / name).read_bytes())
    remote = tmp_path / "remote.git"
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, check=True)
    subprocess.run([*git, "add", "."], cwd=work, check=True)
    subprocess.run([*git, "commit", "-qm", "x"], cwd=work, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=work, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=work, check=True, capture_output=True, text=True).stdout.strip()
    (work / "dist").mkdir()
    (work / "dist/RoutePou-android.apk").write_bytes(b"apk-bytes")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    fake = bin_dir / "gh"
    # `gh release view` fails the first time (no release yet), like a fresh repository
    fake.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {log}
if [ "$1 $2" = "release view" ] && [ ! -f {tmp_path}/created ]; then exit 1; fi
if [ "$1 $2" = "release create" ]; then touch {tmp_path}/created; fi
exit 0
""")
    fake.chmod(0o755)
    import os
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "GITHUB_SHA": sha, "GITHUB_STEP_SUMMARY": str(tmp_path / "sum.md")}
    for _ in range(2):  # the second run is a rebuild: the release exists and is edited, files are replaced
        subprocess.run(["bash", "publish-release.sh", "dist/RoutePou-android.apk"], cwd=work, check=True, env=env, capture_output=True)
    calls = log.read_text(encoding="utf-8")
    assert f"release create v{VERSION} --verify-tag" in calls and "--latest" in calls
    assert f"release edit v{VERSION}" in calls and "--prerelease=false" in calls and "--draft=false" in calls
    assert f"release upload v{VERSION} dist/RoutePou-android.apk dist/RoutePou-android.apk.sha256 --clobber" in calls
    assert (work / "dist/RoutePou-android.apk.sha256").read_text().split()[1] == "RoutePou-android.apk"
    tags = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", f"refs/tags/v{VERSION}"], check=True, capture_output=True, text=True)
    assert tags.stdout.strip() == sha
    missing = subprocess.run(["bash", "publish-release.sh", "dist/none.apk"], cwd=work, env=env, capture_output=True, text=True)
    assert missing.returncode != 0


def test_release_notes_are_persian_and_include_the_changelog_section():
    notes = subprocess.run(["bash", "release-notes.sh"], cwd=ROOT, check=True, capture_output=True, text=True,
                           encoding="utf-8").stdout
    assert "RoutePou-android.apk" in notes and "RoutePou-windows-x64.exe" in notes and "دانلود" in notes
    assert "Clean rebuild" not in notes or "### Changes" in notes
    assert "Fixed (build-breaking)" in notes


def test_publishing_guide_explains_the_workflows_and_the_old_files():
    text = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")
    assert "Run workflow" in text and "windows.yml" in text and "android.yml" in text and "tests.yml" in text
    assert "Remove old files" in text and "old-files.txt" in text
    for name in ("Estedad-Regular.woff2", "Inter-Regular.woff", ".github/workflows/build.yml"):
        assert name in text


def test_android_job_uses_the_sdk_on_the_runner_and_a_fixed_image():
    """The helper action android-actions/setup-android@v3 stopped the job with "Failed to find package 'tools'"
    (sdkmanager no longer has that package). The runner image already contains the SDK, so sdkmanager is called directly."""
    data = yaml.safe_load(workflow_text("android"))
    job = data["jobs"]["build"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert not any("android-actions" in str(step.get("uses", "")) for step in job["steps"])
    install = next(step for step in job["steps"] if step.get("name", "").startswith("Install Android platform"))
    for needle in ('platforms;android-${ANDROID_COMPILE_SDK}', 'build-tools;${ANDROID_BUILD_TOOLS}',
                   'ndk;${ANDROID_NDK_VERSION}', "ANDROID_HOME=$SDK", "--licenses"):
        assert needle in install["run"], needle
    assert "packages: tools" not in workflow_text("android")
