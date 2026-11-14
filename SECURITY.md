# Security

This is an operator tool for a trusted local Windows workstation, not a multi-user internet service. Never expose the FastAPI, Ollama, WinRM or DCOM endpoints publicly.

Credentials exist only as a PowerShell PSCredential for the duration of console collection. The API never receives credentials and cannot start collection. Diagnostic data can still include sensitive server/account/event information. Secure the workstation, report directory, terminal and any exports. Review explicit ACLs if using an existing output directory. Administrative and SYSTEM access remains outside the application's security boundary.

The local API uses a random per-process Bearer token, a loopback client check, Host validation, an Origin allowlist and no-store responses. This does not defend against malware or another process running as the operator. No automated remediation is provided. AI output may be incorrect; report text can contain malicious instructions. The system prompt marks report content untrusted, but prompt instructions are not a security guarantee. The app never executes model output.

The public demo is a static build with simulated fixture data. Do not add real diagnostic files to source, build assets, screenshots, GitHub issues or public hosting. Report a vulnerability privately to the repository owner through GitHub; do not include credentials or actual diagnostics in a public issue.
