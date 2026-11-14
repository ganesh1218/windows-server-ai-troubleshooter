# Security

This is a read-only administrative tool for a trusted Windows management host. It runs with Windows PowerShell 5.1 and built-in Windows components; it does not require Python, Node.js or target agents at runtime.

Default hosting binds a loopback URL and rejects remote clients. Shared internal mode requires HTTPS, Windows Negotiate authentication and an explicit allowed-user list. Do not expose the listener, WinRM or DCOM to the public internet. The application never configures certificates, URL reservations, firewall rules, remote permissions or execution policy itself.

The server validates Host and Origin, requires a per-process API token, disables caching and serves only the dashboard and restricted asset filenames. The token is supplied to the host's own HTML, not URLs or persistent browser storage. Shared snapshots are isolated by the authenticated Windows identity. Other processes/administrators on the management host are outside this security boundary.

Target credentials are masked and cleared in the form, passed to a fixed PowerShell bridge through stdin, and never written to command-line arguments, report files or application access logs. Plaintext necessarily exists transiently in browser and managed process memory; complete erasure cannot be guaranteed. Raw collector errors are not returned to clients. Request bodies are limited and Windows HTTP.sys request timeouts are configured.

The connection endpoint accepts validated hostnames/IPs, not commands or script paths. A fixed child PowerShell process executes the read-only collector with a 180-second bound. Requests are serialized. The application executes no report text, findings or remediation. Web snapshots stay in memory until export or host shutdown; console collection can save explicitly private reports under its dedicated ACL-protected directory.

QFE history is not a compliance certification, TCP reachability is not proof of RDP login, and missing data is unknown. Review findings with an administrator. Shared HTTPS/domain hosting and target access must be validated in your environment.

Never put real credentials, diagnostics or private screenshots in source, fixtures, issues or public hosting. Report vulnerabilities privately to the repository owner.

The Cloudflare dashboard may pair with the loopback PowerShell service. CORS is restricted to the exact HTTPS origin `https://wshc.ganesh18.dpdns.org`, limited API routes, and loopback clients. A random per-process code must be entered manually; it is never disclosed through a cross-origin bootstrap endpoint. API requests still require the bearer code. Preflight responses grant no diagnostic access. Shared Windows-authenticated hosting does not enable website pairing. No wildcard origins, cloud diagnostic proxy, or public management listener is provided.

The published JavaScript can see data entered into or returned to the dashboard. Protect GitHub write access and Cloudflare deployment permissions as privileged access to the diagnostics UI. No third-party analytics or scripts are included. Browser local-network permission and enterprise policies may block loopback requests; the same-origin localhost dashboard remains available.
