# Private Windows hosting

The public address `https://wshc.ganesh18.dpdns.org` is served independently by Cloudflare Worker `wshc`; it is not the private diagnostics endpoint. The Worker contains only built public HTML/JS/CSS and makes no request to ChatGPT Sites. The private Windows hosting options below are unchanged.

The runtime is Windows PowerShell 5.1 plus Windows built-in .NET/HTTP.sys. The browser dashboard is bundled. Download/extract/run is sufficient for a local session when the account already has the required URL reservation and script permissions.

## Local workstation

Double-click `Start-HealthCheck.cmd`, or run `scripts\Start-HealthCheck.ps1` in Windows PowerShell. The default URL is `http://127.0.0.1:8000/`. The server rejects remote clients in this mode.

If access is denied, an administrator can reserve the exact loopback URL for the operator. Replace the example account with the real account; do not grant Everyone:

```powershell
netsh http add urlacl url=http://127.0.0.1:8000/ user=DOMAIN\operator
```

This is Windows configuration, not an application installation. The app does not run this command or modify policy automatically. Do not change execution policy without your administrator's approval. Follow your organization's code-signing/download-trust procedure for the scripts.

## Shared internal host

Have your Windows/domain administrator prepare:

1. An internal DNS name and trusted certificate for that exact name in the host's certificate store.
2. A matching HTTP.sys HTTPS certificate binding and URL reservation.
3. Private firewall scope limited to approved clients.
4. Windows authentication/browser intranet/SPN configuration as required by your environment.
5. Explicit operator accounts with only the permissions they need.

Example configuration commands, to be adapted and run by the administrator after reviewing existing reservations/bindings:

```powershell
netsh http show urlacl
netsh http show sslcert
netsh http add urlacl url=https://healthcheck.example.internal:8443/ user=DOMAIN\healthcheck-host
netsh http add sslcert hostnameport=healthcheck.example.internal:8443 certhash=REPLACE_WITH_CERTIFICATE_THUMBPRINT appid='{d19cf122-933d-4a07-aef1-cd82a60f7525}' certstorename=MY
```

The thumbprint placeholder must be replaced with an actual certificate thumbprint. These examples do not configure a firewall, DNS, certificate issuance or service-account permissions. Never bind/publish this administrative endpoint to the public internet.

Run as the reserved host account:

```powershell
.\scripts\Start-HealthCheck.ps1 -Prefix 'https://healthcheck.example.internal:8443/' -AllowRemote -AllowedUsers 'DOMAIN\operator1','DOMAIN\operator2' -NoBrowser
```

Users visit that HTTPS address. The listener uses Windows Negotiate authentication, then checks each identity against the allowlist. They enter their remote-server credentials inside the authenticated HTTPS app; no agent or project installation is required on their laptops or targets. Browsers must trust the certificate and permit Windows authentication to this internal URL. No insecure HTTP remote mode is available.

Requests, including collections, are serialized. Snapshots are separated by authenticated identity and cleared when the host process exits. This tool does not install a Windows service or configure unattended startup. Validate shared hosting and real target connections with your own domain/network policies before operational rollout.

## Microsoft references

- [HttpListener, authentication and HTTPS certificates](https://learn.microsoft.com/en-us/dotnet/api/system.net.httplistener?view=netframework-4.8.1)
- [Windows HTTP.sys configuration with netsh http](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-http)
- [PowerShell CIM sessions and DCOM](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/new-cimsession?view=powershell-5.1)
