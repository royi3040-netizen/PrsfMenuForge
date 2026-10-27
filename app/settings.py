"""Small, dependency-free persistent UI settings."""
from __future__ import annotations
import json
import os
from pathlib import Path

DEFAULTS = {'theme': 'dark', 'language': 'he', 'layout': 'rtl', 'geometry': None}


def data_directory() -> Path:
    # The user data belongs in a persistent directory, not in TEMP.
    root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share')
    return root / 'PrsfMenuForge'


def read_settings() -> dict:
    out = DEFAULTS.copy()
    try:
        saved = json.loads((data_directory() / 'settings.json').read_text(encoding='utf-8'))
        if isinstance(saved, dict):
            out.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError, TypeError):
        pass
    for field, permitted in (('theme', {'dark', 'light'}), ('language', {'he', 'en'}), ('layout', {'rtl', 'ltr'})):
        if out[field] not in permitted:
            out[field] = DEFAULTS[field]
    return out


def write_settings(settings: dict) -> None:
    dest = data_directory()
    dest.mkdir(parents=True, exist_ok=True)
    import tempfile
    path = dest / 'settings.json'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.tmp', dir=dest, delete=False) as temp:
        json.dump({key: settings.get(key) for key in DEFAULTS}, temp, ensure_ascii=False, indent=2)
        tmp = Path(temp.name)
    tmp.replace(path)
