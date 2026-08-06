# VerseNa Packaging

This project supports two release formats:

- Windows desktop package with an embedded Python runtime.
- Termux archive with prebuilt frontend assets.

These package formats do not currently receive automatic updates. The maintained update channel is for Git source checkouts; see [Source Updates](SOURCE_UPDATES.md).

## Windows

### 本地开发启动

源码模式运行 Electron 桌面客户端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-electron.ps1
```

它会启动前端开发服务器，再启动 Electron。开发完成后需要通过 VerseNa 托盘菜单的“退出”结束应用，脚本随后会清理由它启动的 Vite 进程。

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

Runtime data is stored under `$HOME/.local/share/versena` by default. This keeps the SQLite database and access token on Termux's private filesystem, where file locking and atomic writes work reliably. Existing data under `backend/data` is migrated automatically when the private data directory is empty. Set `VERSENA_DATA_DIR` before startup to choose another private, writable location.

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

Do not place `VERSENA_DATA_DIR` under `/sdcard`, `~/storage`, or another Android shared-storage path. SQLite writes and file locking are not reliable there. The project source or release archive may live in shared storage, but runtime data should remain in Termux's private filesystem.

If Windows packaging reports a corrupt Python archive, rerun the packaging script. The script downloads to a temporary file first and replaces the cache only after the archive looks valid.

If `electron-builder` tries to download signing helpers and the network fails, retry after GitHub access is available. Local unsigned builds have Windows executable signing disabled in the project config; a future signed release should add a proper certificate pipeline explicitly.

If a sandboxed terminal reports `spawn EPERM` while running Vite or electron-builder, rerun the command from a normal PowerShell terminal. The build tools need to start native child processes.
