"""Language of the RoutePou Windows app: Persian ("fa", the default) or English ("en").

Standard library only. The choice is stored in %APPDATA%\\RoutePou\\settings.json, so the next start uses it again.
`t(fa, en)` returns the text of the current language.
"""
import json
import os
from pathlib import Path

LANG = "fa"


def settings_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "RoutePou" / "settings.json"


def set_language(code: str) -> str:
    global LANG
    LANG = "en" if code == "en" else "fa"
    return LANG


def load() -> str:
    """Read the saved language. A missing or damaged file means Persian."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return set_language(str(data.get("language", "fa")))
    except (OSError, ValueError, AttributeError):
        return set_language("fa")


def save(code: str) -> None:
    set_language(code)
    try:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"language": LANG}), encoding="utf-8")
    except OSError:
        pass  # the choice then only lasts until the program is closed


def t(fa: str, en: str) -> str:
    """Persian text first, English text second."""
    return en if LANG == "en" else fa
