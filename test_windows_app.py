"""Static checks for the Windows app (it needs a display and winreg, so it is not imported)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_all_python_sources_parse():
    for name in ("routepou_windows.py", "pairing.py", "wg_provision.py", "wg_supervisor.py", "proxy_headers.py", "i18n.py"):
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
    workflow = (root / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
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
    workflow = (root / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert '"--selftest" in sys.argv' in source and "root.after(1500, root.destroy)" in source
    for module in ("tkinter.ttk", "cv2", "zxingcpp", "PIL.Image"):
        assert f'"{module}"' in source.split('"--selftest" in sys.argv', 1)[1]
    assert "'--selftest'" in workflow and "WaitForExit(60000)" in workflow
    # the selftest must come after the EXE is built and before it is uploaded
    assert workflow.index("pyinstaller @a") < workflow.index("'--selftest'") < workflow.index("name: RoutePou-Windows")


def _run_windows_app_with_stubbed_tk(tmp_path, monkeypatch, language="fa"):
    """Run routepou_windows.py with a fake tkinter/winreg so the module-level UI code executes on any machine."""
    import runpy
    import sys
    from unittest import mock

    monkeypatch.setenv("APPDATA", str(tmp_path))
    if language != "fa":
        (tmp_path / "RoutePou").mkdir()
        (tmp_path / "RoutePou" / "settings.json").write_text('{"language": "%s"}' % language, encoding="utf-8")
    fake_tk = mock.MagicMock(name="tkinter")
    for widget_class in ("Tk", "Label", "Button", "Frame", "LabelFrame", "Entry", "StringVar"):
        getattr(fake_tk, widget_class).side_effect = lambda *args, **kwargs: mock.MagicMock()   # every widget is its own object
    for name, module in (("tkinter", fake_tk), ("tkinter.ttk", fake_tk.ttk), ("tkinter.messagebox", fake_tk.messagebox),
                         ("tkinter.filedialog", fake_tk.filedialog), ("winreg", mock.MagicMock(name="winreg"))):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "argv", ["routepou_windows.py"])
    import i18n
    return fake_tk, runpy.run_path(str(ROOT / "routepou_windows.py")), i18n


def test_language_button_redraws_every_registered_text(tmp_path, monkeypatch):
    fake_tk, ns, i18n = _run_windows_app_with_stubbed_tk(tmp_path, monkeypatch)
    try:
        registry = ns["_translatable"]
        assert len(registry) >= 20, "every label and button text must be registered for the language button"
        assert all(option == "text" for _, option, _, _ in registry[:3])
        for widget, option, fa, en in registry:
            assert fa != en and any("؀" <= c <= "ۿ" for c in fa), fa
            assert not any("؀" <= c <= "ۿ" for c in en), en
            widget.configure.assert_any_call(**{option: fa})          # started in Persian
        ns["set_language"]()
        assert i18n.LANG == "en"
        for widget, option, fa, en in registry:
            widget.configure.assert_called_with(**{option: en})        # now English
        assert (tmp_path / "RoutePou" / "settings.json").read_text(encoding="utf-8") == '{"language": "en"}'
        ns["language_button"].configure.assert_called_with(text="فارسی")
        ns["set_status"](("آماده اتصال", "Ready to connect"), "idle")
        ns["status"].configure.assert_called_with(text="Ready to connect", fg=ns["COLORS"]["red"])
        ns["set_language"]()                                         # and back
        assert i18n.LANG == "fa"
        ns["status"].configure.assert_called_with(text="آماده اتصال", fg=ns["COLORS"]["red"])
    finally:
        i18n.set_language("fa")


def test_windows_app_starts_in_the_saved_language(tmp_path, monkeypatch):
    _, ns, i18n = _run_windows_app_with_stubbed_tk(tmp_path, monkeypatch, language="en")
    try:
        assert i18n.LANG == "en"
        for widget, option, fa, en in ns["_translatable"]:
            widget.configure.assert_any_call(**{option: en})
        ns["root"].title.assert_any_call("RoutePou | Phone to Windows")
    finally:
        i18n.set_language("fa")


def test_helper_messages_follow_the_language():
    import i18n
    from pairing import describe_connect_error
    try:
        i18n.set_language("en")
        message = describe_connect_error(TimeoutError("timed out"))
        assert "same Wi-Fi" in message and "AP isolation" in message
        assert not any("؀" <= c <= "ۿ" for c in message)
        i18n.set_language("fa")
        assert "وای‌فای" in describe_connect_error(TimeoutError("timed out"))
    finally:
        i18n.set_language("fa")


def test_no_persian_text_in_the_windows_app_is_left_untranslated():
    """Every Persian string must sit next to an English one: t(fa, en), tr(widget, fa, en), a (fa, en) pair."""
    import re
    persian = re.compile(r"[\u0600-\u06ff]")

    def strings(node):
        for part in ast.walk(node):
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                yield part.value

    for name in ("routepou_windows.py", "pairing.py", "wg_supervisor.py"):
        tree = ast.parse(read(name))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and persian.search(node.value)):
                continue
            if node.value == "فارسی" or (isinstance(parents.get(node), ast.Expr)):   # the language name, docstrings
                continue
            group = parents[node]
            while not isinstance(group, (ast.Call, ast.Tuple)):
                group = parents[group]
            siblings = [text for text in strings(group) if text != node.value]
            assert any(re.search("[A-Za-z]{3}", text) and not persian.search(text) for text in siblings), \
                f"{name}:{node.lineno}: no English twin for {node.value[:40]!r}"


def test_i18n_defaults_to_persian_and_survives_a_damaged_settings_file(tmp_path, monkeypatch):
    import i18n
    monkeypatch.setenv("APPDATA", str(tmp_path))
    try:
        assert i18n.load() == "fa"
        (tmp_path / "RoutePou").mkdir()
        (tmp_path / "RoutePou" / "settings.json").write_text("{not json", encoding="utf-8")
        assert i18n.load() == "fa"
        i18n.save("en")
        assert i18n.load() == "en" and i18n.t("الف", "A") == "A"
    finally:
        i18n.set_language("fa")
