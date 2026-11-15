# Security

This is a read-only administrative tool for a trusted Windows management host. The downloadable connector requires Python 3.11+ and built-in Windows PowerShell 5.1, with no third-party Python packages. An optional PowerShell-only web host is also available. No target-server agent is required.

Default hosting binds a loopback URL and rejects remote clients. Shared internal mode requires HTTPS, Windows Negotiate authentication and an explicit allowed-user list. Do not expose the listener, WinRM or DCOM to the public internet. The application never configures certificates, URL reservations, firewall rules, remote permissions or execution policy itself.

The server validates Host and Origin, requires a per-process API token, disables caching and serves only the dashboard and restricted asset filenames. The token is supplied to the host's own HTML, not URLs or persistent browser storage. Shared snapshots are isolated by the authenticated Windows identity. Other processes/administrators on the management host are outside this security boundary.

Target credentials are masked and cleared in the form, passed to a fixed PowerShell bridge through stdin, and never written to command-line arguments, report files or application access logs. Plaintext necessarily exists transiently in browser and managed process memory; complete erasure cannot be guaranteed. Raw collector errors are not returned to clients. Request bodies are limited and Windows HTTP.sys request timeouts are configured.

The connection endpoint accepts validated hostnames/IPs, not commands or script paths. A fixed child PowerShell process executes the read-only collector with a 180-second bound. Requests are serialized. The application executes no report text, findings or remediation. Web snapshots stay in memory until export or host shutdown; console collection can save explicitly private reports under its dedicated ACL-protected directory.

QFE history is not a compliance certification, TCP reachability is not proof of RDP login, and missing data is unknown. Review findings with an administrator. Shared HTTPS/domain hosting and target access must be validated in your environment.

Never put real credentials, diagnostics or private screenshots in source, fixtures, issues or public hosting. Report vulnerabilities privately to the repository owner.

The Cloudflare dashboard may pair with the Python connector or the loopback PowerShell service. CORS is restricted to the exact HTTPS origin `https://wshc.ganesh18.dpdns.org`, limited API routes, and loopback clients. A random per-process code must be entered manually; it is never disclosed through a cross-origin bootstrap endpoint. API requests still require the bearer code. Preflight responses grant no diagnostic access. Shared Windows-authenticated hosting does not enable website pairing. No wildcard origins, cloud diagnostic proxy, or public management listener is provided.

The Python connector binds only IPv4 loopback, validates Host/Origin and the bearer code, caps bodies at 16 KiB, sets socket timeouts, serializes collections and bounds the fixed PowerShell child process at 180 seconds. It serves no arbitrary files, logs no access requests and writes no reports or credentials. It is a small local administrative connector, not a public or multi-user web server. The ZIP is generated from an explicit source allowlist; private data, environment files and credentials are never packaging inputs. A SHA-256 checksum is published alongside it; website/repository access must still be trusted.

The published JavaScript can see data entered into or returned to the dashboard. Protect GitHub write access and Cloudflare deployment permissions as privileged access to the diagnostics UI. No third-party analytics or scripts are included. Browser local-network permission and enterprise policies may block loopback requests; the same-origin localhost dashboard remains available.

On normal startup, the Python connector may offer to remove downloaded-file markers from exactly its three bundled PowerShell scripts. It requires explicit local terminal confirmation after listing those files, uses literal paths with no recursion or wildcard, rejects resolved paths outside the package, and verifies removal. Unrelated files and execution policies remain unchanged. There is no HTTP unblocking endpoint. `--diagnose` remains read-only; `--unblock` is the explicit local helper. File trust is the operator's decision and does not bypass Restricted/AllSigned or organizational code-signing policy.
