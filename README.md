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

Start the local application:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Open **http://127.0.0.1:8000/?local=1**. In **Connect to a server**, enter the local session token printed in the terminal, your server name or IP, and a Windows account/password with remote diagnostic permissions. Click **Connect & check health**. The app immediately collects fresh details and displays CPU, RAM, all drives, RDP, patches, services, events and reboot evidence. A run can take up to 180 seconds. Connection failures and partial collection are explicitly reported.

WinRM HTTPS (5986) is selected by default. Clear the checkbox only for domain-managed WinRM/Negotiate (5985) on your trusted management network. The collector tries WinRM first, then WMI/DCOM. IP-based WinRM authentication may require an appropriately configured HTTPS listener/certificate; prefer a domain hostname for Kerberos. Do not disable certificate validation, broaden TrustedHosts, enable Basic authentication, or expose management ports to the internet to make a connection work. Execution policy must permit the included scripts under your organization's policy; the app does not bypass it.

The password is masked in the local form, cleared after submission, sent only to the loopback API and passed to the fixed PowerShell bridge through stdin. It is never written to report files, command-line arguments, source or access logs. Plaintext credentials necessarily exist transiently in local process memory; this does not protect against a compromised workstation. Fresh reports are held in backend/browser memory until restart/reload unless explicitly exported. Reconnect with credentials to take another fresh snapshot. **Reload collected reports** reads the last collected snapshots; it does not poll servers.

The public website is only a simulated demo. Use **LAB-APP-01 / 192.0.2.10**, **LAB-DB-01 / 192.0.2.20** or **LAB-WEB-01 / 192.0.2.30** to try the form. It does not request credentials, contact real servers or submit typed targets to a backend. Run the local Windows app to connect to your own infrastructure.

### Optional console collection

```powershell
.\scripts\Collect-Diagnostics.ps1 -ComputerName 'server01.example.internal','server02.example.internal' -UseSSL
```

The console collector prompts using `Get-Credential` and saves reports to the Git-ignored `private-data/` directory. Its ACL grants the operator and SYSTEM access; inherited access is removed. Use only a dedicated report directory if overriding `-OutputDirectory`, and review existing explicit ACLs. The web workflow uses `-NoPersist` and does not create report files. Click **Load previously saved console reports** to view console reports using the session token.

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
  Local connect form -> authenticated loopback API -> PowerShell stdin
                                                 -> private WinRM -> Windows Server
                           -> private DCOM fallback
  private-data/*.json -> loopback FastAPI -> local browser

Public static demo -> bundled simulated fixtures only
```

Keep FastAPI on `127.0.0.1:8000`. Do not publish the local API through a reverse proxy or tunnel. API requests require a Bearer token; remote clients, unexpected Host headers, and cross-origin browser requests are rejected. The token-protected `/api/connect` route runs only the bundled read-only collector with validated targets and stdin credentials. It accepts no shell commands or script paths. Concurrent checks are rejected and subprocesses time out after 180 seconds. No CORS wildcard, upload or arbitrary command execution route exists. Access logs are disabled and report responses use `Cache-Control: no-store`.

Within the private network, scope WinRM HTTPS (5986), or domain WinRM (5985), to the management workstation. DCOM requires RPC 135 and the organization's restricted RPC dynamic-port policy; it is not a firewall bypass. Domain policy and least-privilege permissions must be configured by your administrators. Remote UAC, provider availability, firewall policy and authentication can prevent collection. The app does not modify those settings.

Reports contain hostnames, account names and event messages. Protect them at rest, apply your retention policy, and review exported JSON before sharing. `.gitignore` helps avoid accidental commits; it is not an access-control mechanism. Never replace public fixture files with actual reports. Report messages are displayed as text and never executed. Health checks use fixed thresholds: CPU and RAM at 85% used, and drive capacity at 85% used. Missing metrics are shown as unknown.

## Demo and development

```powershell
npm.cmd ci
npm.cmd run dev
```

The Vite development UI uses simulated reports. The private mode must be served by FastAPI at port 8000 after `npm run build`; it deliberately rejects other origins. The default landing view remains a clearly labeled demo even when served locally; the backend prints the private-mode URL.

`src/sample.js` and `samples/diagnostics.simulated.json` contain three fictional LAB servers. KB identifiers are deliberately fictional. The dashboard requires no model download or model service. The demo supports the simulated connection flow, server selection, section navigation, filtering, JSON export, the collection guide and automatic health checks.

## Tests

```powershell
npm.cmd test
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest tests\test_api.py -q
powershell.exe -NoProfile -File tests\Test-Collector.ps1
```

JavaScript tests cover drive sorting, unknown capacity, findings and simulated fixtures. Python tests cover token/Host/Origin boundaries, parsing, missing reports, the authenticated connection endpoint, credential redaction, injection rejection, fixed subprocess arguments, timeouts, partial/failed collection and health endpoint. PowerShell checks parser compatibility and collector safety contracts. CI runs these on Windows, using Windows PowerShell for the collector checks. Real remote WinRM/DCOM requires your environment and is not covered by these tests.

## Architecture

* `scripts/Collect-Diagnostics.ps1`: PowerShell 5.1 collection with console persistence or in-memory web results.
* `scripts/Invoke-HealthCheck.ps1`: fixed stdin bridge for the private local connection endpoint.
* `backend/app.py`: authenticated local connection/report API and static production frontend.
* `src/`: React UI, simulated fixtures and deterministic threshold findings.
* `tests/`: automated data, backend and collector contract checks.
* `.openai/hosting.json`: public static demo deployment metadata; only `dist/` is hosted.

See [SECURITY.md](SECURITY.md) for limitations. MIT licensed. No warranty.

## References

[Microsoft CIM sessions and DCOM fallback](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/new-cimsession?view=powershell-5.1), [Microsoft unexpected reboot investigation](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-unexpected-reboots-system-event-logs).
