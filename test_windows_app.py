"""Static checks for the Windows app (it needs a display and winreg, so it is not imported)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_all_python_sources_parse():
    for name in ("routepou_windows.py", "pairing.py", "wg_provision.py", "wg_supervisor.py", "proxy_headers.py"):
        ast.parse(read(name), filename=name)


def test_windows_app_wiring():
    source = read("routepou_windows.py")
    assert 'payload.startswith("routepou://p/")' in source       # full-tunnel QR
    assert "parse_qr_to_windows_ipc" in source
    assert "parse_pairing_payload" in source                      # proxy QR
    assert "def scan_qr_camera" in source and "def scan_qr_image" in source
    assert "connect_full_tunnel" in source and "disconnect_full_tunnel" in source
    assert 'line == "PEER-LOST"' in source and 'line == "PEER-BACK"' in source
    assert "relaywg-client.exe" in source
    assert "_restore_proxy_on_exit" in source                     # never strand the system proxy


def test_certificate_is_pinned():
    source = read("routepou_windows.py")
    assert "hashlib.sha256(wrapped.getpeercert(binary_form=True))" in source
    assert "hmac.compare_digest" in source
    assert "certificate fingerprint mismatch" in source


def test_supervisor_keeps_keys_in_memory():
    source = read("wg_supervisor.py")
    assert "CreateNamedPipeW" in source and "END-CONFIG" in source
    assert 'line == "READY"' in source and "ShellExecuteW" in source
    assert "-hold-on-loss=true" in source and "-block-leaks=true" in source
    assert "write_text" not in source and "open(" not in source


def test_worker_reports_peer_events_and_fails_closed():
    worker = read("winclient/main.go")
    assert 'peerLostLine = "PEER-LOST"' in worker and 'peerBackLine = "PEER-BACK"' in worker
    assert "refusing full tunnel because leak protection could not be installed" in worker


def test_modules_loaded_with_dunder_import_are_declared_as_pyinstaller_hidden_imports():
    """PyInstaller only follows plain `import` statements. routepou_windows.py once loaded tkinter.ttk with
    __import__(), and the built EXE stopped at start-up with "No module named 'tkinter.ttk'"."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent
    source = (root / "routepou_windows.py").read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    dynamic = set(re.findall(r"__import__\(\s*[\"']([\w.]+)[\"']", source))
    dynamic |= set(re.findall(r"importlib\.import_module\(\s*[\"']([\w.]+)[\"']", source))
    # tkinter.ttk is a plain import now (the built EXE once stopped with "No module named 'tkinter.ttk'")
    assert re.search(r"^from tkinter import ttk\b", source, re.M), "tkinter.ttk must be imported with a plain import"
    assert "tkinter.ttk" not in dynamic
    assert "'--hidden-import', 'tkinter.ttk'" in workflow  # and declared again, for safety
    for module in dynamic:
        top = module.split(".")[0]
        static = re.search(rf"^\s*(?:import|from)\s+{re.escape(module)}\b", source, re.M)
        declared = f"'--hidden-import', '{module}'" in workflow or f"'--collect-all', '{top}'" in workflow
        assert static or declared, f"{module} would be missing from the EXE"


def test_finished_exe_is_started_once_in_the_build():
    """The user cannot always test the EXE on a PC. The build starts the finished EXE with --selftest: the window
    opens and closes by itself, and any missing module makes the build fail instead of the user's PC."""
    from pathlib import Path
    root = Path(__file__).resolve().parent
    source = (root / "routepou_windows.py").read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert '"--selftest" in sys.argv' in source and "root.after(1500, root.destroy)" in source
    for module in ("tkinter.ttk", "cv2", "zxingcpp", "PIL.Image"):
        assert f'"{module}"' in source.split('"--selftest" in sys.argv', 1)[1]
    assert "'--selftest'" in workflow and "WaitForExit(60000)" in workflow
    # the selftest must come after the EXE is built and before it is uploaded
    assert workflow.index("pyinstaller @a") < workflow.index("'--selftest'") < workflow.index("name: RoutePou-Windows")
