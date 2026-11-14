#requires -Version 5.1
# Private API bridge. Request/credentials arrive through stdin, never argv or disk.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$request = $null; $secure = $null; $credential = $null
try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $secure = ConvertTo-SecureString -String $request.password -AsPlainText -Force
    $credential = [System.Management.Automation.PSCredential]::new($request.username,$secure)
    $request.password = $null
    & (Join-Path $PSScriptRoot 'Collect-Diagnostics.ps1') -ComputerName $request.target -Credential $credential -UseSSL:([bool]$request.use_ssl) -Days 7 -NoPersist
} catch {
    # Raw exceptions may contain private request information: do not echo them.
    [Console]::Error.WriteLine('Collection failed. Check credentials, connectivity and remote permissions.')
    exit 1
} finally {
    $credential=$null; $request=$null
    if ($secure) { $secure.Dispose() }
}
