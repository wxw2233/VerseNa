# Source Updates

VerseNa can update installations that were created with `git clone`. Packaged Windows builds and archived Termux releases do not use this update channel.

## First-Time Setup

Existing source installations must receive the updater once with a normal Git update:

```bash
cd ~/VerseNa
git pull --ff-only
bash scripts/setup-termux.sh  # Termux only
```

On other platforms, install changed dependencies and rebuild `frontend/dist` with the platform's normal source setup. Restart VerseNa after these commands. Later updates can be managed from **Settings -> Source Update**.

## Update Flow

The source updater performs the following fixed sequence:

1. Verify that VerseNa is running from a Git checkout with an upstream branch.
2. Fetch the configured upstream and compare commit history.
3. Refuse to continue if tracked files are modified or local history has diverged.
4. Fast-forward the current branch to its upstream.
5. Install Python or frontend dependencies only when their lock files changed.
6. Build the frontend into a temporary directory and replace `frontend/dist` only after a successful build.
7. Ask the user to restart VerseNa so the updated backend code is loaded.

Database files, access tokens, uploaded files, logs, and ignored runtime data are not modified. On Termux these files remain under `$HOME/.local/share/versena` by default.

## Requirements

- The checkout must have a configured upstream, normally `origin/master`.
- Git, Python, Node.js, and npm must be available on `PATH`.
- Termux source installations should be initialized with `bash scripts/setup-termux.sh`; daily startup uses `bash scripts/start-termux.sh`.
- Tracked source files must be clean. Untracked and ignored runtime files do not block updates.
- Git must be able to reach the configured remote. Existing Git proxy and credential settings are respected.

## Recovery

If source code was pulled but dependency installation or the frontend build failed, the updater keeps a pending marker under `.versena-update/`. Fix the reported dependency or network problem, then choose **Continue Update**. The previous `frontend/dist` is kept until a new frontend build succeeds.

The updater never resets, force-checks out, or deletes tracked user changes. Resolve a dirty or diverged checkout manually before retrying.
