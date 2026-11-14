# Windows Server Health Check 2.0

**Run with Windows PowerShell 5.1. No Python, Node.js, package installation or target-server agent is required.**

[Website and run guide](https://wshc.ganesh18.dpdns.org) · [Private shared hosting](DEPLOYMENT.md) · [Release notes](CHANGELOG.md)

## Public website hosting

The public website is hosted directly by **Cloudflare Pages**, project `wshc-health-check`. Cloudflare's native GitHub integration watches `ganesh1218/windows-server-health-check` and automatically builds and deploys pushes to `main`. ChatGPT Sites is not in the request path.

Production settings: branch `main`, build command `npm run build`, output directory `dist`, Node.js 22. No GitHub Actions deployment secret or separate Worker build token is required. The existing Cloudflare GitHub App integration supplies repository access.

`cloudflare-hosting.json` contains only public project identifiers. `/hosting-health` and `X-WSHC-Hosting` identify Cloudflare Pages. Public `/api/*` requests return 404; Windows diagnostics remain on the private PowerShell host. Frontend build tooling runs in Cloudflare, not on end-user machines.

ServerScope provides a browser dashboard for read-only Windows Server diagnostics. Enter a server name or IP and Windows credentials; the PowerShell backend collects a fresh snapshot through WinRM with WMI/DCOM fallback. The prebuilt React dashboard is included in `dashboard.zip`.

## Run on localhost

For an existing checkout, run `Start-HealthCheck.cmd` and open **http://127.0.0.1:8000/**. Enter the server name/IP and credentials there to collect live health details. The public website provides an **Open local dashboard** link; it never receives those details. No additional runtime installation is needed. A browser cannot start PowerShell, so keep the local service running while using the dashboard.

## First-time source setup

1. [Download the complete repository ZIP](https://github.com/ganesh1218/windows-server-health-check/archive/refs/heads/main.zip).
2. Extract it to a folder on your Windows management workstation or internal Windows host.
3. Double-click **Start-HealthCheck.cmd**.
4. Open **http://127.0.0.1:8000/** if the browser does not open automatically.
5. Enter the target server name/IP, username such as `DOMAIN\username`, and password. Click **Connect & check health**.

Keep the PowerShell window open. Press **Ctrl+C** there to stop. The bundled dashboard is extracted to `.runtime/web/` automatically; no build or dependency download happens at startup.

To launch directly from Windows PowerShell:

```powershell
.\scripts\Start-HealthCheck.ps1
```

Windows HTTP.sys may require an administrator-approved URL reservation. If the listener reports access denied, use **Run as administrator** for a local test, or ask your administrator to reserve the exact URL for the account running the application. The application does not change URL reservations, firewall rules, execution policy, certificates or remote-management settings automatically.

Windows PowerShell 5.1 and its built-in .NET/CIM/networking components are the runtime requirements. Script execution must be permitted by your organization's policy. A normal browser cannot run PowerShell itself; the backend runs once on the Windows host. Your workstation/host must already have network or VPN access to the target servers and an account with the required remote diagnostic permissions.

## One shared internal website

You can run the backend on **one internal Windows management server**. Users then open its private HTTPS address in their browsers. Nothing from this project needs installing on their laptops or target servers.

Shared mode requires all of the following:

- An explicit private HTTPS hostname and a trusted certificate bound in Windows HTTP.sys.
- A URL reservation for the Windows account running the application.
- Windows Integrated Authentication and an explicit list of allowed Windows user accounts.
- Firewall access scoped to the intended private management network; no public exposure.

Launch after those administrator-managed prerequisites are in place:

```powershell
.\scripts\Start-HealthCheck.ps1 `
  -Prefix 'https://healthcheck.example.internal:8443/' `
  -AllowRemote `
  -AllowedUsers 'DOMAIN\operator1','DOMAIN\operator2' `
  -NoBrowser
```

HTTP shared hosting, wildcard listener prefixes, missing Windows identities and accounts outside the allowlist are rejected. The application uses Negotiate authentication; your domain/browser configuration must permit integrated authentication to this internal hostname. Target-server credentials are entered separately over HTTPS. Collected snapshots are isolated by the authenticated operator's identity and remain in memory until the host process stops.

The listener handles requests serially, including one collection at a time. Other browser requests can wait while a check runs. This is a small administrative tool, not a high-concurrency monitoring platform. Shared HTTPS/domain authentication still needs validation in your environment.

See [DEPLOYMENT.md](DEPLOYMENT.md) for administrator configuration examples and [SECURITY.md](SECURITY.md) for the boundary. The public hosted page contains setup guidance and optional fictional preview data; it cannot access private servers or execute PowerShell.

## What it checks

| Area | Details |
| --- | --- |
| CPU | Point-in-time processor utilization |
| RAM | Used/total physical memory and utilization |
| Drives | All logical drives, with C: first and free/total capacity |
| RDP | Enablement, TermService state, NLA and TCP 3389 reachability |
| Patches | QFE installation history and installation accounts when available |
| Services | Current state and startup mode |
| Events | Recent System/Application warnings and errors |
| Reboots/shutdowns | UTC event timestamps, lifecycle evidence and initiating accounts when available |

Threshold findings flag CPU/RAM at 85% used and disks at 85% capacity used. Missing data stays **Unknown**. Collection defaults to seven days of event history, capped at 100 returned records per category. Each web collection is limited to 180 seconds.

CPU/RAM are single samples, RDP reachability does not prove interactive login, and QFE history does not certify patch compliance. Stopped automatic/trigger-start services may be legitimate. Events 41 and 6008 may refer to the same incident and do not establish its root cause. Event creation time is not necessarily the exact shutdown time; initiating accounts are shown only when supplied by the evidence.

## Remote connection prerequisites

WinRM HTTPS (5986) is the default. Domain-managed WinRM/Negotiate (5985) is available by clearing the checkbox when appropriate for your private management network. Domain hostnames are preferred for Kerberos; IP-based WinRM may require an appropriately configured HTTPS listener and matching certificate.

DCOM fallback requires remote WMI rights, RPC 135 and your organization's restricted RPC dynamic-port policy. The app never enables services, opens firewall ports, broadens TrustedHosts or disables certificate validation. No target-server software from this project is required, but existing Windows remote management must be configured.

## Credentials and data

The form masks the password and clears it after submission. Credentials reach the PowerShell collector through stdin, not command-line arguments or report files. They necessarily exist transiently in browser and PowerShell process memory. Use a trusted management host; managed runtimes do not guarantee complete memory erasure.

The host supplies its per-process API token to its own HTML. Tokens are not placed in URLs or persistent browser storage. Host/Origin validation, API tokens, no-store responses and restricted static-file routes protect browser access. Remote shared mode additionally requires HTTPS and allowed Windows identities. Report text is displayed as text and is never executed. There is no arbitrary command or script-upload endpoint.

Fresh web reports are memory-only unless exported. Reconnect with credentials for a new snapshot; **Reload collected snapshots** only reloads existing snapshots. Exported reports can contain sensitive hostnames, accounts and event messages. Keep them private and out of GitHub. The application performs no remediation.

## Optional console collection

```powershell
.\scripts\Collect-Diagnostics.ps1 -ComputerName 'server01.example.internal' -UseSSL -Days 7
```

This prompts with `Get-Credential` and saves JSON under the Git-ignored `private-data/` directory. The dedicated directory ACL grants the operator and SYSTEM access and removes inherited access. Review existing explicit ACLs if overriding `-OutputDirectory`. Console `-Days` supports 1–30 days. The browser's collector uses `-NoPersist` instead.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Listener cannot start | Port availability, exact URL reservation and HTTPS certificate binding |
| Script is blocked | Organization-approved execution policy/signing and downloaded-file trust |
| Server cannot connect | DNS/IP, VPN route, listener, account permissions and private firewall policy |
| DCOM also fails | WMI namespace rights and RPC network policy |
| Some sections are unknown | Provider availability and per-section permissions |
| Shared browser access denied | HTTPS, Windows authentication and the explicit allowed-user list |
| Request waits | Another collection may be running; requests are serialized |

## Maintainers only: rebuild and test

End users do not need these development tools. Node.js is needed only to modify/rebuild the React source:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run build
powershell.exe -NoProfile -File scripts\Bundle-Dashboard.ps1
powershell.exe -NoProfile -File tests\Test-Collector.ps1
powershell.exe -NoProfile -File tests\Test-Server.ps1
```

Commit the rebuilt `dashboard.zip` with source changes. `npm.cmd run dev` uses fictional preview fixtures. PowerShell server tests exercise authentication, Host/Origin checks, target validation, redaction, timeout/error handling and operator isolation with mocked collection responses.

With the PowerShell server running, test real HTTP serving without contacting a target server:

```powershell
powershell.exe -NoProfile -File tests\Test-Http.ps1 -BaseUrl http://127.0.0.1:8000
```

Real WinRM/DCOM connections and shared HTTPS/domain authentication require your environment; these tests are not a substitute for that integration validation.

## Source layout

| Path | Purpose |
| --- | --- |
| `Start-HealthCheck.cmd` | Windows PowerShell launcher |
| `dashboard.zip` | Prebuilt browser dashboard; no runtime build required |
| `scripts/Start-HealthCheck.ps1` | Built-in HTTP.sys/HttpListener web host |
| `scripts/Server.Core.psm1` | Authentication, request routing and bounded collector process |
| `scripts/Collect-Diagnostics.ps1` | Read-only WinRM/DCOM diagnostics |
| `scripts/Invoke-HealthCheck.ps1` | Private stdin credential bridge |
| `src/` | React source and deterministic health findings |
| `tests/` | JavaScript and Windows PowerShell tests |

No Python backend remains. [MIT License](LICENSE). Provided without warranty.
