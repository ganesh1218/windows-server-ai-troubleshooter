# Security

This is a read-only administrative tool for a trusted Windows management host. It runs with Windows PowerShell 5.1 and built-in Windows components; it does not require Python, Node.js or target agents at runtime.

Default hosting binds a loopback URL and rejects remote clients. Shared internal mode requires HTTPS, Windows Negotiate authentication and an explicit allowed-user list. Do not expose the listener, WinRM or DCOM to the public internet. The application never configures certificates, URL reservations, firewall rules, remote permissions or execution policy itself.

The server validates Host and Origin, requires a per-process API token, disables caching and serves only the dashboard and restricted asset filenames. The token is supplied to the host's own HTML, not URLs or persistent browser storage. Shared snapshots are isolated by the authenticated Windows identity. Other processes/administrators on the management host are outside this security boundary.

Target credentials are masked and cleared in the form, passed to a fixed PowerShell bridge through stdin, and never written to command-line arguments, report files or application access logs. Plaintext necessarily exists transiently in browser and managed process memory; complete erasure cannot be guaranteed. Raw collector errors are not returned to clients. Request bodies are limited and Windows HTTP.sys request timeouts are configured.

The connection endpoint accepts validated hostnames/IPs, not commands or script paths. A fixed child PowerShell process executes the read-only collector with a 180-second bound. Requests are serialized. The application executes no report text, findings or remediation. Web snapshots stay in memory until export or host shutdown; console collection can save explicitly private reports under its dedicated ACL-protected directory.

QFE history is not a compliance certification, TCP reachability is not proof of RDP login, and missing data is unknown. Review findings with an administrator. Shared HTTPS/domain hosting and target access must be validated in your environment.

Never put real credentials, diagnostics or private screenshots in source, fixtures, issues or public hosting. Report vulnerabilities privately to the repository owner. The public static site is setup guidance and fictional UI preview only; it cannot run Windows PowerShell or connect to private servers.
