# Release notes

## 2.0 — PowerShell-only runtime

- The web backend runs with Windows PowerShell 5.1 and built-in Windows components.
- `dashboard.zip` includes the prebuilt dashboard. End users do not run npm, pip or a build step.
- `Start-HealthCheck.cmd` starts the PowerShell host and opens the browser.
- Real connections accept a server name/IP and credentials, using WinRM with DCOM fallback.
- Shared internal hosting supports HTTPS, Windows authentication, an explicit user allowlist and per-user snapshots.
- README, deployment instructions, security notes and server comments describe the PowerShell runtime.
- The website is now at https://wshc.ganesh18.dpdns.org.
- Python runtime files have been removed. Node.js is used only by frontend maintainers.

Validation includes PowerShell server assertions, real HTTP smoke checks and frontend tests. Real target connectivity and domain/HTTPS integration still require environment-specific validation.
