#requires -Version 5.1
# Bridge the local connection form to the read-only collector.
# Credentials arrive on stdin; only diagnostic JSON is written to stdout.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$request = $null; $secure = $null; $credential = $null
$stage='invalid_request'
try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $stage='credential_setup'
    $secure = ConvertTo-SecureString -String $request.password -AsPlainText -Force
    $credential = [System.Management.Automation.PSCredential]::new($request.username,$secure)
    $request.password = $null
    $stage='collector_failed'
    & (Join-Path $PSScriptRoot 'Collect-Diagnostics.ps1') -ComputerName $request.target -Credential $credential -UseSSL:([bool]$request.use_ssl) -Days 7 -NoPersist
} catch {
    # Only allowlisted codes cross the bridge; never return raw exceptions.
    if ($_.Exception -is [System.Management.Automation.PSSecurityException]) {$stage='script_blocked'}
    $scriptName=[IO.Path]::GetFileName($_.InvocationInfo.ScriptName)
    if ($scriptName -notin @('Invoke-HealthCheck.ps1','Collect-Diagnostics.ps1')) {$scriptName='PowerShell'}
    [Console]::Out.WriteLine((ConvertTo-Json -Compress -InputObject @{errorCode=$stage;exceptionType=$_.Exception.GetType().FullName;script=$scriptName;line=$_.InvocationInfo.ScriptLineNumber}))
    exit 1
} finally {
    $credential=$null; $request=$null
    if ($secure) { $secure.Dispose() }
}
