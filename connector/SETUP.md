# Windows Server Health Check — Python connector

## GitHub checkout instead of ZIP

Install Python 3.11+ and Git for Windows, then clone `https://github.com/ganesh1218/windows-server-health-check.git` on your management computer. In the cloned folder, run `py -3 launcher.py`. It checks GitHub `main`, shows updates and lets you review the full diff before approving a fast-forward update. The connector then runs locally. Nothing is copied to target servers.

Future sessions use the same command. Use `--diagnose` for local readiness checks or `--offline` to explicitly skip the network update check. The launcher refuses dirty worktrees, divergent/local-ahead history, other branches and unexpected origins. It never discards edits or changes security policies. Only approve code you have reviewed; repository/ancestry checks are not a signature verification or security audit. Clone into a separate folder; the small ZIP below does not include Git history or the launcher.

## ZIP setup

1. Use a Windows management computer with network/VPN access to your servers.
2. Install Python 3.11 or newer from https://www.python.org/downloads/windows/.
3. Extract the complete connector ZIP to a trusted folder. Keep `connector.py` and the `scripts` folder together.
4. Open a terminal in that folder and run:

   ```powershell
   py -3 connector.py
   ```

   If `py` is unavailable, use `python connector.py`. No pip packages are required.
5. Keep the terminal open. Visit https://wshc.ganesh18.dpdns.org.
6. Enter the server name/IP and continue. Allow local-network access if prompted by the browser.
7. Pair using the private session code printed by the connector. Enter your Windows username and password, then check health.

The connector uses built-in Windows PowerShell 5.1 for read-only diagnostics over WinRM, with WMI/DCOM fallback. You do not need to open PowerShell separately. Target servers need existing remote-management configuration and permissions; no connector is installed on them.

WinRM HTTPS (5986) is the default. Only clear that option where your organization's private WinRM/Negotiate configuration permits HTTP (5985). No certificate validation is disabled and no firewall or TrustedHosts settings are changed.

The connector binds only 127.0.0.1:8000. Never expose it, WinRM or DCOM publicly. Only the exact website origin is allowed, and diagnostic endpoints require a random per-run session code. Credentials travel directly from your browser to localhost and then through stdin to a fixed PowerShell collector. Credentials and snapshots are not written to files or logs. They exist transiently in process memory; exported snapshots remain your responsibility.

Ctrl+C stops the connector. Restarting creates a new session code and clears collected snapshots. If port 8000 is busy, stop the earlier connector or PowerShell web host. Starting automatically with Windows is not configured by this package.

Browser or organization policies may block public-website-to-localhost requests. Allow local network access for this exact site where approved; otherwise use the existing same-origin PowerShell dashboard or ask your administrator about internal hosting. Python does not bypass browser security.

If collection fails, check target permissions, VPN/DNS, WinRM/WMI firewall rules and your organization's PowerShell script-signing/execution policy. The connector never bypasses those policies. No arbitrary commands, remediation or script uploads are accepted.

The website now distinguishes blocked PowerShell scripts, invalid connector requests, credential preparation failures, script parsing problems and missing Windows PowerShell. Messages are chosen from fixed safe text; raw errors, account names and passwords are not returned. If Windows blocks scripts from the extracted ZIP, review the scripts and follow your organization's approved signing/downloaded-file trust process. Do not disable your execution policy to troubleshoot. After obtaining an updated connector package, stop the previous process, extract into a fresh folder, restart and pair with the new code; refreshing the website alone does not update a running connector.

The connector clears inherited PSModulePath only for its Windows PowerShell child process. Windows PowerShell then rebuilds its own default module paths, avoiding incompatible PowerShell 7 modules. Your system/user environment, execution policy and installed modules are not changed.

## Diagnose a repeated local failure

Connector **1.0.3** prints its version at startup. In the extracted folder, run `py -3 connector.py --diagnose`. This checks only local commands, script parsing and file-trust markers. It does not ask for credentials, connect to any server, bind a port or change policy. Its output contains no passwords, session codes, hostnames or usernames and can be supplied for troubleshooting. Collection failures also include a safe exception type and script line where available. If you see only the older generic message, stop the old process and run the updated extracted package before retrying.
