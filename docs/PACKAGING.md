# VerseNa Packaging

This project supports two release formats:

- Windows desktop package with an embedded Python runtime.
- Termux archive with prebuilt frontend assets.

## Windows

Build an unpacked desktop package:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -Target dir
```

Build an installer:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -Target installer
```

Output is written under:

```text
dist-electron/
```

The Windows package includes:

- `resources/python/` - Python 3.11 embeddable runtime and backend dependencies.
- `resources/backend/` - backend source without user data or tests.
- `resources/frontend/dist/` - production frontend build.
- `resources/personas/`, `resources/themes/`, `resources/themepacks/` - bundled editable content templates.

On first packaged launch, Electron copies bundled personas, themes, and theme packs into the app user data directory. User-edited content, skills, database files, uploaded files, and access tokens live outside `Program Files`, so reinstalling does not overwrite them.

## Termux

Create a Termux archive from Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package-termux.ps1
```

Output is written under:

```text
release/VerseNa-<version>-termux.tar.gz
```

On Android, extract the archive and install runtime dependencies once:

```bash
pkg update
pkg install python
python -m pip install -r backend/requirements-termux.txt
termux-setup-storage
bash scripts/start-termux.sh
```

The Termux archive includes `frontend/dist`, so Android does not need Node.js for normal use.

## Fresh Clone Test

After cloning the repository on Windows:

```powershell
git clone https://github.com/wxw2233/VerseNa.git
cd VerseNa
powershell -ExecutionPolicy Bypass -File scripts/package-windows.ps1 -Target dir
.\dist-electron\win-unpacked\VerseNa.exe
```

To prepare the Android package from the same clone:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package-termux.ps1
```

Copy `release/VerseNa-<version>-termux.tar.gz` to Termux, extract it, then run:

```bash
python -m pip install -r backend/requirements-termux.txt
bash scripts/start-termux.sh
```

## LAN Access Token

LAN mode is protected by an access token. The backend prints the token on first startup when it creates one automatically. After login, it can be changed from Settings -> Access Security.

The minimum token length is 6 characters. For LAN use, prefer a longer random token when possible.

## Common Issues

If Windows packaging reports a corrupt Python archive, rerun the packaging script. The script downloads to a temporary file first and replaces the cache only after the archive looks valid.

If `electron-builder` tries to download signing helpers and the network fails, retry after GitHub access is available. Local unsigned builds have Windows executable signing disabled in the project config; a future signed release should add a proper certificate pipeline explicitly.

If a sandboxed terminal reports `spawn EPERM` while running Vite or electron-builder, rerun the command from a normal PowerShell terminal. The build tools need to start native child processes.
