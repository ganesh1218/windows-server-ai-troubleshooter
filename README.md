# Windows Server Health Check

ServerScope is a Windows Server health-check dashboard for administrators working on a trusted management network. Enter a server name or IP address, authenticate with a Windows account, and collect a fresh read-only health snapshot through WinRM with WMI/DCOM fallback.

Built with **Windows PowerShell 5.1**, **Python FastAPI** and **React**. No model service or cloud analysis is required.

## Health information

| Check | Details |
| --- | --- |
| CPU | Point-in-time processor utilization |
| Memory | Used and total physical RAM, with utilization percentage |
| Storage | Every logical drive, with C: first and free/total capacity |
| Remote Desktop | Enablement, TermService state, NLA and TCP 3389 reachability |
| Windows updates | QFE installation history and installation accounts when available |
| Services | Current state and startup mode |
| Event logs | Recent System and Application warnings and errors |
| Reboots and shutdowns | Event timestamps, planned/unexpected evidence and initiating accounts when available |

Missing measurements are shown as **Unknown**. Health findings use fixed thresholds: CPU and RAM at 85% utilization, and disks at 85% capacity used. These findings indicate what to investigate; they do not certify availability or compliance.

## Requirements

Use a Windows management workstation with:

- Windows PowerShell 5.1 and its CIM/WMI commands.
- Python 3.11 or later, Node.js 22 or later, and Git.
- Network or VPN access to the Windows Server targets.
- A Windows account with the required remote CIM/WMI, service and event-log read permissions.
- WinRM or DCOM configured by your administrators and allowed through the private management network.

The application does not enable remote management, change firewall rules or grant remote permissions.

## Installation

```powershell
git clone https://github.com/ganesh1218/windows-server-health-check.git
cd windows-server-health-check
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd ci
npm.cmd run build
```

## Start and connect

Double-click **Start-HealthCheck.cmd**. It starts the local service and opens **http://127.0.0.1:8000/**. Keep the terminal open while using the application. Press **Ctrl+C** in that terminal to stop it.

Alternatively, start the service from a terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Open the local address, then:

1. Enter the server's DNS name or IP address.
2. Enter a Windows username such as `DOMAIN\username` and its password.
3. Choose the appropriate WinRM connection option.
4. Click **Connect & check health**.
5. Review the fresh snapshot, collection errors and supporting event records.

The browser establishes its local API session automatically. A collection can take up to 180 seconds. Only one collection runs at a time. Reconnect with credentials to collect another fresh snapshot; reloading collected reports only displays existing snapshots.

WinRM HTTPS on port 5986 is selected by default. Use domain-managed WinRM/Negotiate on port 5985 only when appropriate for your management network. A domain hostname is preferred for Kerberos. IP-based connections may require an appropriately configured HTTPS listener and matching certificate. If WinRM fails, collection attempts WMI/DCOM.

**Use the local Windows application for actual servers.** A hosted static preview cannot reach your management network and does not run the collection API.

## Credentials and report privacy

Passwords are masked in the connection form and cleared after submission. The local API passes credentials to a fixed PowerShell script through stdin, never through command arguments or report files. Plaintext credentials necessarily exist transiently in browser and process memory; this is not protection against a compromised workstation.

New web collections stay in backend/browser memory unless explicitly exported. Exported reports can contain sensitive hostnames, accounts and event messages. Protect them according to your organization's retention and access policies. Do not commit real diagnostics or credentials to GitHub.

FastAPI binds to **127.0.0.1:8000**. API calls require a per-process token; Host/Origin checks and a loopback-client check reject unexpected access. The token is supplied only to the local dashboard HTML, not to URLs or persistent browser storage. Access logs are disabled and responses use `Cache-Control: no-store`.

Keep FastAPI, WinRM and DCOM private. Do not expose the application through a public proxy or tunnel. Do not disable certificate validation, broaden TrustedHosts or enable insecure authentication to fix a connection. See [SECURITY.md](SECURITY.md).

## Optional console collection

From Windows PowerShell 5.1:

```powershell
.\scripts\Collect-Diagnostics.ps1 -ComputerName 'server01.example.internal','server02.example.internal' -UseSSL -Days 7
```

The console workflow uses `Get-Credential` and saves JSON to the Git-ignored `private-data/` directory. Its dedicated directory ACL grants the operator and SYSTEM access and removes inherited access. Review existing explicit ACLs when choosing another output directory. The dashboard workflow uses `-NoPersist` and does not create those files.

Use **Load previously saved console reports** in the dashboard to read console results. To select another private report directory before starting the service:

```powershell
$env:DIAGNOSTIC_DIR = 'D:\RestrictedReports'
```

`APP_TOKEN` can supply a strong process token for managed deployments; never commit it or an environment file.

## Troubleshooting connections

| Result | What to verify |
| --- | --- |
| Server not reachable | DNS resolution, target address and network/VPN route |
| WinRM fails | Listener, certificate, authentication, account rights and private firewall policy |
| DCOM fallback fails | RPC 135, your organization's RPC dynamic-port policy and remote WMI rights |
| Script does not run | Windows PowerShell 5.1 availability and organization-approved execution policy |
| Some sections are unavailable | Provider availability and service/event-log/namespace permissions |
| Collection times out | Connectivity, server load and event-log volume; use a shorter console `-Days` window |

The application does not bypass execution policy or modify remote security settings.

## Interpreting the snapshot

- CPU and RAM are single samples, not utilization trends.
- RDP TCP reachability does not prove interactive login or effective firewall-policy correctness. Custom RDP ports need separate checks.
- QFE history does not include every update type and is not a patch-compliance scan.
- Automatic services can legitimately be stopped, including trigger-start services.
- Event 41 and 6008 records may describe the same incident and do not identify a root cause on their own.
- Event timestamps are normalized to UTC and represent record creation, not necessarily the exact shutdown time. Initiating accounts are shown only when supplied by the available evidence.
- Event collection defaults to seven days and returns up to 100 records per event category. Console collection supports `-Days 1` through `-Days 30`.

Real-server WinRM/DCOM connectivity must be validated in your environment. Automated tests do not substitute for that integration check.

## Development and tests

```powershell
npm.cmd test
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest tests\test_api.py -q
powershell.exe -NoProfile -File tests\Test-Collector.ps1
```

Tests cover drive ordering, threshold boundaries, unknown measurements, API authentication, Host/Origin restrictions, credential redaction, target validation, subprocess arguments, timeouts and collection failures. PowerShell checks validate parser compatibility and collector safety contracts. GitHub Actions runs the checks on Windows.

`npm.cmd run dev` serves the frontend with fictional UI-preview fixtures. For actual connections, build the frontend and serve it through FastAPI at port 8000. Files in `src/sample.js` and `samples/diagnostics.simulated.json` are intentionally fictional and must never be replaced with real diagnostic data.

## Source layout

| Path | Purpose |
| --- | --- |
| `Start-HealthCheck.cmd` | One-click local Windows launcher |
| `backend/app.py` | Authenticated connection/report API and dashboard serving |
| `scripts/Collect-Diagnostics.ps1` | Read-only WinRM/DCOM health collector |
| `scripts/Invoke-HealthCheck.ps1` | Private stdin bridge between FastAPI and PowerShell |
| `src/` | Dashboard, deterministic findings and preview fixtures |
| `tests/` | JavaScript, API and PowerShell checks |

## Documentation and license

[Microsoft CIM sessions and DCOM](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/new-cimsession?view=powershell-5.1) · [Microsoft reboot investigation](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-unexpected-reboots-system-event-logs)

[MIT License](LICENSE). Provided without warranty.
