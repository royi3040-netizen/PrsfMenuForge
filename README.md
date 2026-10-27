# PrsfMenuForge — Python Edition

**New codebase (v1.0)**. A clean Windows context-menu manager written from scratch in **Python 3.11+ and PySide6 (Qt)**. The old PowerShell interface is not used.

## Features

- Modern dark/light interface, original SVG icons, native program icons when Windows can extract them.
- Hebrew and English language switching **independent** of RTL/LTR layout.
- Categories: Desktop, Folders, Files, Drives; case-insensitive search and item details.
- Scans classic `shell` commands and `shellex\\ContextMenuHandlers` from `HKCU` and `HKLM`.
- Hide / restore standard commands; manage classic COM handler block entries (with warnings).
- Add EXE programs to one or more menu contexts under **HKCU only**.
- Delete a **specific context-menu registration**, never uninstall the actual program.
- Built-in protection of common Windows commands, confirmation for deletions and `.reg` backups before modifying existing registry keys.
- Elevation uses normal Windows UAC only when selected by the user; ordinary browsing and additions don't require admin.
- Keeps persistent user data under `%LOCALAPPDATA%\\PrsfMenuForge` instead of Temp.

## Run on Windows

1. Install Python 3.11+ x64 (enable **Add Python to PATH** if needed).
2. Extract the ZIP to any folder.
3. Run **`install.bat`** once while connected to the internet. It creates a private `TOOLS/venv` environment and installs PySide6 there (without changing your global Python packages).
4. Double-click **`PrsfMenuForge.bat`** to launch silently from `TOOLS/venv`, or run `TOOLS\venv\Scripts\python main.py` for debugging.

From a terminal, advanced users can instead do:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Notes and limitations

- **Classic registry context-menu entries only**: some new Windows 11 compact-menu / packaged dynamic commands do not have traditional shell registration and won't show here. Do not assume the list is the exact live Windows menu.
- A particular shell extension CLSID can be used in multiple locations. Blocking it may hide it in all locations. The app asks for confirmation and records the previous state.
- Hiding and deleting machine-wide (`HKLM`) commands requires an explicit **Run as administrator** action, sometimes further registry permissions.
- Deleting an item means **deleting its registry registration** (not uninstalling its program). Restoring a deleted registration requires manually importing its `.reg` backup. A backup export failing aborts the deletion.
- Certain Microsoft items are protected; no program can guarantee all third-party extensions are harmless to modify.
- The backup for COM blocking includes a `.json` state record and, if the blocked-list key previously existed, a `.reg` export of that list.
- You may need to restart Windows Explorer manually to see shell-menu changes; the app does **not** force-restart Explorer.
- The Python source can be statically tested outside Windows; GUI startup and registry integration need on-device testing with Windows + PySide6.

## Source structure

```text
main.py                     Entry point
app/ui.py                   Qt interface and interaction
app/theme.py                Color palette, QSS, translations
app/icons.py                SVG icon renderer
assets/icons/*.svg          Editable standalone original icons
app/registry_backend.py     Windows registry reads/writes and backups
app/models.py               Shared types
app/settings.py             Persistent configuration
requirements.txt            GUI dependency
install.bat                 First-time dependency setup
PrsfMenuForge.bat            Run from local TOOLS/venv without lingering CMD window
PrsfMenuForge.pyw            Optional no-console Python launch with a global PySide6 install
tests/                      Python unittest suite
```

### Run tests

```powershell
python -m unittest discover -s tests -v
```

## Build optional EXE locally

No GitHub Actions time is required. For an optional standalone EXE on Windows after validating the Python version:

```powershell
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --onefile --windowed --name PrsfMenuForge main.py
```

The generated executable is under `dist/`. The source ZIP contains **source code**, not a precompiled `.exe`.
