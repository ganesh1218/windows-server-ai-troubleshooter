# ServerScope — Windows Server Health Check

PowerShell 5.1 remote diagnostics, a private FastAPI service, and a React Server Health Check dashboard with deterministic threshold checks. The public demo contains **fictional health data only**. It has no remote-management backend.

[Public simulated demo](https://windows-server-ai-troubleshooter.politerose12.chatgpt.site)

The existing repository and demo addresses are retained for continuity. The application is now a Server Health Check and has no model dependency.

## Install locally on Windows

Use a trusted Windows management workstation with Windows PowerShell 5.1, Python 3.11+, Node.js 22+ and Git. Remote targets should be supported Windows Server installations with appropriate CIM/WMI providers. Remote execution has not been verified against a real Windows Server during development.

```powershell
git clone https://github.com/ganesh1218/windows-server-ai-troubleshooter.git
cd windows-server-ai-troubleshooter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd ci
npm.cmd run build
```

From **Windows PowerShell 5.1** on the management workstation:

```powershell
.\scripts\Collect-Diagnostics.ps1 -ComputerName 'server01.example.internal','server02.example.internal' -UseSSL
```

The collector prompts using `Get-Credential`. Do not pass passwords on the command line. It tries WinRM/CIM first, then CIM over WMI/DCOM. Without `-UseSSL`, WinRM uses Negotiate on the trusted management network; domain Kerberos is preferred. Do not weaken TrustedHosts, disable certificate validation, enable Basic authentication, or open management ports to the internet to make collection work.

The default report directory is `private-data/` (ignored by Git), protected with ACLs for the operator and SYSTEM. Existing inherited access is removed from this dedicated directory. Choose only a directory dedicated to these reports if overriding `-OutputDirectory`; review its existing explicit ACLs. No credentials are serialized. The application does not change the remote server or open its firewall.

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Open **http://127.0.0.1:8000/?local=1**, enter the session token printed in the terminal, and click **Load private reports**. Select a server to review CPU, RAM, every drive, RDP, patches, services, event logs and reboot evidence. Health findings are computed automatically from the snapshot. Tokens and reports are held in browser memory, never localStorage. A new random token is generated each launch. The terminal token is sensitive; do not share terminal captures.

Optional configuration before starting the backend:

```powershell
$env:DIAGNOSTIC_DIR = 'D:\RestrictedReports'
```

`APP_TOKEN` can provide a strong session token from the process environment for managed deployments; never commit an environment file. 

## What it collects

* CPU utilization and total/used physical RAM (single snapshots, not historical trends).
* All logical drives, with C: first. Unmounted/empty media keep unknown capacity instead of zero.
* RDP enablement, TermService state, NLA requirement and TCP 3389 reachability. Custom RDP ports, effective firewall rules and interactive authentication need separate verification.
* Win32_QuickFixEngineering patch history with installation date/account when supplied. QFE is not a complete update inventory or a compliance scan.
* Windows services and startup modes. Stopped automatic services are signals; trigger-start services may legitimately be stopped.
* Last 7 days of System/Application warnings and errors, capped at 100 returned records per report category. `-Days` supports 1–30 days.
* Reboot/shutdown evidence: USER32 1074, EventLog 6005/6006/6008, Kernel-Power 41 and lifecycle 12/13. 1074 insertion strings provide the initiating account when available. Other records may have no account. Event creation timestamps are normalized to UTC, not presented as precise shutdown times. Multiple records can describe the same incident; no cause is inferred from 41/6008 alone.

Collection failures are explicit per section. An unavailable value is **unknown**, never healthy. Queries may be expensive on large event logs; use short windows and least-privilege accounts with remote CIM and event-log read rights. The collector does not perform remediation. Health findings are advisory and require operator review.

## Network and privacy boundary

```text
Trusted operator workstation
  PowerShell secure prompt -> private WinRM -> Windows Server
                           -> private DCOM fallback
  private-data/*.json -> loopback FastAPI -> local browser

Public static demo -> bundled simulated fixtures only
```

Keep FastAPI on `127.0.0.1:8000`. Do not publish the local API through a reverse proxy or tunnel. API requests require a Bearer token; remote clients, unexpected Host headers, and cross-origin browser requests are rejected. No CORS wildcard, upload, shell execution or remote collection route exists. Access logs are disabled and report responses use `Cache-Control: no-store`.

Within the private network, scope WinRM HTTPS (5986), or domain WinRM (5985), to the management workstation. DCOM requires RPC 135 and the organization's restricted RPC dynamic-port policy; it is not a firewall bypass. Domain policy and least-privilege permissions must be configured by your administrators. Remote UAC, provider availability, firewall policy and authentication can prevent collection. The app does not modify those settings.

Reports contain hostnames, account names and event messages. Protect them at rest, apply your retention policy, and review exported JSON before sharing. `.gitignore` helps avoid accidental commits; it is not an access-control mechanism. Never replace public fixture files with actual reports. Report messages are displayed as text and never executed. Health checks use fixed thresholds: CPU and RAM at 85% used, and drive capacity at 85% used. Missing metrics are shown as unknown.

## Demo and development

```powershell
npm.cmd ci
npm.cmd run dev
```

The Vite development UI uses simulated reports. The private mode must be served by FastAPI at port 8000 after `npm run build`; it deliberately rejects other origins. The default landing view remains a clearly labeled demo even when served locally; the backend prints the private-mode URL.

`src/sample.js` and `samples/diagnostics.simulated.json` contain three fictional LAB servers. KB identifiers are deliberately fictional. The dashboard requires no model download or model service. The demo supports server selection, section navigation, filtering, JSON export, the collection guide and automatic health checks.

## Tests

```powershell
npm.cmd test
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest tests\test_api.py -q
powershell.exe -NoProfile -File tests\Test-Collector.ps1
```

JavaScript tests cover drive sorting, unknown capacity, findings and simulated fixtures. Python tests cover token/Host/Origin boundaries, parsing, missing reports, the report-only API boundary and health endpoint. PowerShell checks parser compatibility and collector safety contracts. CI runs these on Windows, using Windows PowerShell for the collector checks. Real remote WinRM/DCOM requires your environment and is not covered by these tests.

## Architecture

* `scripts/Collect-Diagnostics.ps1`: PowerShell 5.1 console-only collection and private JSON output.
* `backend/app.py`: local report API and static production frontend.
* `src/`: React UI, simulated fixtures and deterministic threshold findings.
* `tests/`: automated data, backend and collector contract checks.
* `.openai/hosting.json`: public static demo deployment metadata; only `dist/` is hosted.

See [SECURITY.md](SECURITY.md) for limitations. MIT licensed. No warranty.

## References

[Microsoft CIM sessions and DCOM fallback](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/new-cimsession?view=powershell-5.1), [Microsoft unexpected reboot investigation](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-unexpected-reboots-system-event-logs).
