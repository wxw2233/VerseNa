# Tool Safety and Workspace

VerseNa exposes four primary Agent tools: `code_exec`, `file_manager`, `web_search`, and `web_fetch`.

## Tool Workspace

Local tool operations use a dedicated workspace instead of the backend process directory. The default is:

```text
<VerseNa data directory>/workspace
```

Set a different root before starting VerseNa when the Agent should manage another directory:

```bash
export VERSENA_TOOL_WORKSPACE="$HOME/VerseNaWorkspace"
```

```powershell
$env:VERSENA_TOOL_WORKSPACE = "D:\VerseNaWorkspace"
```

Relative paths supplied to `file_manager` and the `cwd` supplied to `code_exec` are resolved inside this workspace. Paths that escape the workspace, credential files, environment files, access tokens, and databases are rejected by `file_manager`.

## Confirmation Rules

- `code_exec` requires explicit confirmation unless automatic approval is enabled for the session.
- Automatic approval applies to workspace-scoped file actions and command execution.
- Confirmation is internal state. Tool arguments supplied by the model cannot mark an operation as confirmed.
- Local execution and file tools are not exposed through the QQ channel.

`code_exec` starts each command as a new process, removes common secret-bearing environment variables, limits captured output, and terminates the process tree on timeout or Stop. It is not an operating-system sandbox: inspect the displayed command before approving it.

## Web Tools

`web_fetch` accepts only public HTTP and HTTPS destinations. Loopback, private, link-local, reserved, credential-bearing, and non-HTTP URLs are rejected on every redirect. Response bodies are limited to 1 MB before text extraction.

Search and fetched page content is untrusted external data. The Agent prompt instructs models to extract information from it without following embedded instructions.
