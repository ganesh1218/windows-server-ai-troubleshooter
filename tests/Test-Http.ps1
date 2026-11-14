#requires -Version 5.1
param([string]$BaseUrl='http://127.0.0.1:8000')
$ErrorActionPreference='Stop'
$health=Invoke-RestMethod "$BaseUrl/api/health"
if($health.mode -ne 'powershell'){throw 'The HTTP backend is not PowerShell.'}
$page=Invoke-WebRequest "$BaseUrl/" -UseBasicParsing
$match=[regex]::Match($page.Content,'name="serverscope-session" content="([^"]+)"')
if(-not $match.Success){throw 'Session bootstrap metadata missing.'}
$headers=@{Authorization='Bearer '+[Net.WebUtility]::HtmlDecode($match.Groups[1].Value)}
$reports=Invoke-WebRequest "$BaseUrl/api/reports" -Headers $headers -UseBasicParsing
if($reports.StatusCode -ne 200 -or $reports.Headers['Cache-Control'] -ne 'no-store'){throw 'Authenticated reports or no-store header failed.'}
$asset=[regex]::Match($page.Content,'src="(/assets/[^"]+\.js)"').Groups[1].Value
if(-not $asset){throw 'Bundled JavaScript link missing.'}
if((Invoke-WebRequest ($BaseUrl+$asset) -UseBasicParsing).StatusCode -ne 200){throw 'Bundled JavaScript unavailable.'}
try{
    Invoke-WebRequest "$BaseUrl/api/connect" -Method POST -Headers $headers -ContentType 'application/json' -Body '{"target":"server;whoami","username":"test","password":"dummy-test-password"}' -UseBasicParsing | Out-Null
    throw 'Invalid target was accepted.'
}catch{
    if(-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 400){throw}
}
Write-Host 'Real HTTP smoke test passed: PowerShell runtime, bundled assets, automatic session, authenticated reports, no-store and invalid target rejection. No real server was contacted.'
