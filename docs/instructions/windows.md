# Windows and PowerShell

[← README](../../README.md) · [All documentation](../../README.md#documentation) · [Quickstart](quickstart.md)

The guides show commands for Bash, the shell of Linux and macOS. On Windows you can follow them in one of three ways:

| Way | When to use it |
| --- | --- |
| **PowerShell 7** (`pwsh`) | Everyday work. The equivalents below are written for it. |
| **Git Bash** | Installed with [Git for Windows](https://git-scm.com/downloads/win). Bash commands from the guides work as written, with `.venv/Scripts/python.exe` instead of `.venv/bin/python`. |
| **WSL 2** | A Linux distribution inside Windows. Clone the project inside WSL (for example in `~/amoCRM`), not under `/mnt/c`, and follow the Linux instructions. |

Windows PowerShell 5.1 decodes JSON responses without an explicit charset as ISO-8859-1, so Russian text from the API can look broken. Use PowerShell 7 for API calls.

> **Not verified on Windows.** The project is checked on macOS; the Docker image is Linux. The commands on this page follow the PowerShell documentation but were not run: no Windows machine or `pwsh` was available. Report differences in the [development log](../DEVELOPMENT_LOG.md).

## Install the tools

1. Python 3.12 from [python.org](https://www.python.org/downloads/windows/) with the «py launcher» option, or `winget install Python.Python.3.12`.
2. [Git for Windows](https://git-scm.com/downloads/win).
3. For the container run — [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with the WSL 2 backend.

## Prepare a PowerShell session

Run once per window so that Russian text from scripts and the API is shown correctly:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location path\to\amoCRM
```

Replace `path\to\amoCRM` with the folder that contains `requirements.txt`.

## Bash constructs and their PowerShell equivalents

| Bash | PowerShell 7 |
| --- | --- |
| `python3.12 -m venv .venv` | `py -3.12 -m venv .venv` |
| `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |
| `.venv/bin/python …` | `.venv\Scripts\python.exe …` |
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `NAME=value command` (one command only) | `$env:NAME = 'value'; command; Remove-Item Env:NAME` |
| `export NAME=value` | `$env:NAME = 'value'` |
| Line continuation `\` | Backtick `` ` `` at the end of the line, or one long line |
| `curl …` | `curl.exe …` (plain `curl` is an alias of `Invoke-WebRequest` in Windows PowerShell) or `Invoke-RestMethod` |
| `curl -u manager:password …` | `curl.exe -u manager:password …` |
| `$(date +%s)` | `[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()` |
| `$(date +%Y%m%d-%H%M%S)` | `$(Get-Date -Format yyyyMMdd-HHmmss)` |
| `/tmp/file.py` | `"$env:TEMP\file.py"` |
| `unzip -l dist/widget.zip` | `tar -tf dist\widget.zip` |
| `grep 'text' file` | `Select-String 'text' file` |
| `cat file` | `Get-Content file` |

`git`, `docker` and `docker compose` commands are the same in both shells.

## Typical commands

Prepare the environment and run all checks:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\python.exe -m ruff check app tests scripts evals
.venv\Scripts\python.exe -m mypy app evals
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\run_evals.py retrieval
.venv\Scripts\python.exe scripts\check_docs.py
.venv\Scripts\python.exe scripts\build_widget.py
```

Start the server:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Start the stub model and the app pointed at it ([Testing](testing.md#manual-check-without-an-llm-key)), each in its own window:

```powershell
.venv\Scripts\python.exe -m uvicorn --app-dir $env:TEMP stub_llm:app --port 9100
```

```powershell
$env:LLM_BASE_URL = 'http://127.0.0.1:9100/v1'
$env:LLM_MODEL = 'stub'
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Docker:

```powershell
docker compose up --build
```

## JSON requests to the API

Send the body as UTF-8 bytes so that Russian text arrives intact:

```powershell
$body = @{ message = 'Сколько стоит монтаж?'; client_name = 'Анна' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/suggest `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

With the manager login enabled ([Access protection](access.md)):

```powershell
$credential = Get-Credential manager
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/suggest `
  -Authentication Basic -Credential $credential -AllowUnencryptedAuthentication `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

`-AllowUnencryptedAuthentication` is needed only for `http://127.0.0.1`; on a server use `https://` and drop it.

## Backup copies

The commands from [Резервное копирование](backup.md):

```powershell
New-Item -ItemType Directory -Force "$HOME\amocrm-backups" | Out-Null
Copy-Item data\knowledge_base.json "$HOME\amocrm-backups\knowledge_base-$(Get-Date -Format yyyyMMdd-HHmmss).json"
Get-ChildItem "$HOME\amocrm-backups"
```

Restore:

```powershell
Copy-Item "$HOME\amocrm-backups\<file name>.json" data\knowledge_base.json
curl.exe -s http://127.0.0.1:8000/health
```

## What is checked on Windows

Nothing yet. CI runs on Ubuntu only, and no local Windows run was performed. If you use Windows, run the checks from [Typical commands](#typical-commands) and record the result in [VERIFICATION.md](../VERIFICATION.md).
