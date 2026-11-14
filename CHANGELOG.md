# Release notes

## Python connector and website setup

- Added a downloadable local Python connector, official Python download link and step-by-step website setup instructions.
- Python uses the bundled Windows PowerShell collector without requiring a separate PowerShell session or pip packages.
- Preserved exact-origin CORS, loopback-only binding, per-run pairing, stdin credentials and bounded collection.
- Website builds regenerate the connector ZIP and SHA-256 checksum directly from public source files.
- Added Python HTTP/security/collector/package tests to GitHub checks. Automatic Windows startup is not configured.

## Independent Cloudflare hosting

- Public website assets are deployed directly to Cloudflare Pages project `wshc-health-check`.
- Enabled native Cloudflare GitHub integration: pushes to main build and deploy the public website automatically.
- Removed local ChatGPT Sites hosting configuration.
- Added `/hosting-health` and `X-WSHC-Hosting` for deployment verification.
- Public management API routes remain unavailable; the PowerShell backend stays private.

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
