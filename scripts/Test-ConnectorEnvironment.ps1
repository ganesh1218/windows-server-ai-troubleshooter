#requires -Version 5.1
# Local-only readiness check. No server address, credentials or network probes.
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$checks=@()
foreach($name in @('ConvertFrom-Json','ConvertTo-SecureString','New-CimSessionOption','New-CimSession','Get-CimInstance','Remove-CimSession','Test-NetConnection')) {
    try {
        Get-Command $name -ErrorAction Stop | Out-Null
        $checks+=@{check=$name;status='available'}
    } catch {
        $checks+=@{check=$name;status='unavailable';exceptionType=$_.Exception.GetType().FullName}
    }
}
foreach($name in @('Invoke-HealthCheck.ps1','Collect-Diagnostics.ps1')) {
    $file=Join-Path $PSScriptRoot $name
    $tokens=$null;$parseErrors=$null
    if (-not [IO.File]::Exists($file)) {$checks+=@{check=$name;status='missing'};continue}
    [void][Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$parseErrors)
    $checks+=@{check=$name;status=if($parseErrors.Count){'parse-error'}else{'parse-ok'}}
    try {
        $zone=Get-Item -LiteralPath $file -Stream Zone.Identifier -ErrorAction SilentlyContinue
        $checks+=@{check=($name+' downloaded-file marker');status=if($zone){'present'}else{'absent'}}
    } catch {$checks+=@{check=($name+' downloaded-file marker');status='unknown'}}
}
try {$policy=[string](Get-ExecutionPolicy -ErrorAction Stop)}catch{$policy='Unknown'}
@{connectorVersion='1.0.3';powershellVersion=$PSVersionTable.PSVersion.ToString();executionPolicy=$policy;checks=$checks} | ConvertTo-Json -Depth 5 -Compress
