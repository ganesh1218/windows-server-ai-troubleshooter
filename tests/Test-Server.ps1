#requires -Version 5.1
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/Server.Core.psm1') -Force
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$state=New-HealthState -WebRoot (Join-Path $root 'dist') -BridgePath (Join-Path $root 'scripts/Invoke-HealthCheck.ps1')
$script:count=0
function Assert($condition,[string]$message) {if(-not $condition){throw "FAILED: $message"};$script:count++}
function Request([string]$method='GET',[string]$path='/api/health',[string]$body='', [hashtable]$extra=@{}, [scriptblock]$collector) {
    $r=@{Method=$method;Path=$path;Body=$body;Headers=@{Host='127.0.0.1:8000';Authorization=('Bearer '+$state.Token)};RemoteAddress='127.0.0.1';Identity='';IsSecure=$false}
    foreach($key in $extra.Keys){$r[$key]=$extra[$key]}
    Invoke-HealthRequest -State $state -Request $r -Collector $collector
}
$response=Request
Assert ($response.Status -eq 200 -and ($response.Text|ConvertFrom-Json).mode -eq 'powershell') 'PowerShell runtime health'
$response=Request -path '/'
Assert ($response.Text.Contains('serverscope-session') -and $response.Text.Contains($state.Token)) 'same-origin session bootstrap'
$response=Request -path '/api/reports' -extra @{Headers=@{Host='127.0.0.1:8000'}}
Assert ($response.Status -eq 401) 'API token required'
$response=Request -extra @{Headers=@{Host='evil.example'}}
Assert ($response.Status -eq 400) 'unexpected Host denied'
$response=Request -extra @{Headers=@{Host='127.0.0.1:8000';Origin='https://evil.example'}}
Assert ($response.Status -eq 403) 'cross-origin request denied'
$response=Request -extra @{RemoteAddress='192.0.2.5'}
Assert ($response.Status -eq 403) 'remote HTTP client denied'
$response=Request -path '/assets/../../scripts/Invoke-HealthCheck.ps1'
Assert ($response.Status -eq 404) 'arbitrary file access denied'
$response=Request -path '/api/reports'
Assert ($response.Text -eq '[]') 'empty report array'
$websiteHeaders=@{Host='127.0.0.1:8000';Origin='https://wshc.ganesh18.dpdns.org'}
$response=Request OPTIONS '/api/reports' -extra @{Headers=$websiteHeaders}
Assert ($response.Status -eq 204) 'website preflight accepted on loopback'
$response=Request -path '/api/reports' -extra @{Headers=$websiteHeaders}
Assert ($response.Status -eq 401) 'website cannot read reports without pairing code'
$websiteHeaders.Authorization='Bearer '+$state.Token
$response=Request -path '/api/reports' -extra @{Headers=$websiteHeaders}
Assert ($response.Status -eq 200) 'paired website can read local reports'
$response=Request -path '/' -extra @{Headers=$websiteHeaders}
Assert ($response.Status -eq 403) 'website cannot fetch automatic session bootstrap'
$response=Request OPTIONS '/api/reports' -extra @{Headers=$websiteHeaders;RemoteAddress='192.0.2.5'}
Assert ($response.Status -eq 403) 'website preflight does not allow remote clients'
$response=Request OPTIONS '/api/reports' -extra @{Headers=@{Host='127.0.0.1:8000';Origin='https://wshc.ganesh18.dpdns.org.evil.example'}}
Assert ($response.Status -eq 403) 'website lookalike origin rejected'
foreach($target in @('server01','server01.example.internal','10.0.0.15','2001:db8::10')) {Assert (Test-HealthTarget $target) "valid target $target"}
foreach($target in @('server;whoami','../secret','https://server','-command','')) {
    $body=@{target=$target;username='LAB\test';password='dummy-secret'}|ConvertTo-Json -Compress
    $response=Request POST '/api/connect' $body
    Assert ($response.Status -eq 400 -and -not $response.Text.Contains('dummy-secret')) 'invalid target redacted'
}
$response=Request POST '/api/connect' ('x'*17000)
Assert ($response.Status -eq 413) 'oversized request denied'
$response=Request POST '/api/connect' '{broken'
Assert ($response.Status -eq 400) 'invalid JSON denied'
$body=@{target='server01';username='LAB\test';password='dummy-secret';use_ssl=$true}|ConvertTo-Json -Compress
$success={param($payload,$bridge)
    if($payload.target -ne 'server01' -or $payload.password -ne 'dummy-secret' -or -not $bridge.EndsWith('Invoke-HealthCheck.ps1')) {throw 'Invalid collector bridge input'}
    @{TimedOut=$false;ExitCode=0;Output='{"schemaVersion":1,"id":"server01","name":"server01","cpu":34,"errors":[]}'}
}
$response=Request POST '/api/connect' $body @{} $success
Assert ($response.Status -eq 200 -and ($response.Text|ConvertFrom-Json).simulated -eq $false) 'fresh report returned'
Assert (-not $response.Text.Contains('dummy-secret')) 'password excluded from response'
$response=Request -path '/api/reports'
Assert (($response.Text|ConvertFrom-Json)[0].cpu -eq 34) 'snapshot retained in memory'
$response=Request POST '/api/connect' $body @{} {param($p,$b) @{TimedOut=$true;ExitCode=-1;Output=''}}
Assert ($response.Status -eq 504) 'collection timeout explicit'
$response=Request POST '/api/connect' $body @{} {param($p,$b) @{TimedOut=$false;ExitCode=1;Output='private raw error'}}
Assert ($response.Status -eq 502 -and -not $response.Text.Contains('private raw error')) 'failed process sanitized'
$response=Request POST '/api/connect' $body @{} {param($p,$b) @{TimedOut=$false;ExitCode=0;Output='{"schemaVersion":1,"id":"server01","errors":[{"section":"connection"}]}'}}
Assert ($response.Status -eq 502) 'failed transports not marked connected'
$state.AllowRemote=$true;$state.AllowedUsers=@('LAB\alice','LAB\bob')
$response=Request -extra @{Identity='LAB\alice';IsSecure=$false}
Assert ($response.Status -eq 403) 'shared mode requires HTTPS'
$response=Request -extra @{Identity='LAB\other';IsSecure=$true}
Assert ($response.Status -eq 403) 'shared mode identity allowlist enforced'
$response=Request POST '/api/connect' $body @{Identity='LAB\alice';IsSecure=$true} $success
Assert ($response.Status -eq 200) 'allowed HTTPS operator can collect'
$response=Request -path '/api/reports' -extra @{Identity='LAB\bob';IsSecure=$true}
Assert ($response.Text -eq '[]') 'operators cannot read each others snapshots'
$response=Request -path '/api/reports' -extra @{Identity='LAB\alice';IsSecure=$true}
Assert (($response.Text|ConvertFrom-Json)[0].id -eq 'server01') 'operator can reload own snapshot'
Write-Host "$script:count PowerShell server assertions passed. Collector network responses were mocked."
