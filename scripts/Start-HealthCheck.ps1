#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Prefix='http://127.0.0.1:8000/',
    [switch]$AllowRemote,
    [string[]]$AllowedUsers=@(),
    [switch]$NoBrowser,
    [string]$WebRoot
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$uri=$null
if (-not [uri]::TryCreate($Prefix,[UriKind]::Absolute,[ref]$uri) -or $uri.AbsolutePath -ne '/' -or $uri.Query -or $uri.UserInfo -or $uri.Fragment -or $Prefix -match '[*+]') {throw 'Use an explicit origin ending in /; wildcards and URL paths are not allowed.'}
if ($AllowRemote) {
    if ($uri.Scheme -ne 'https' -or -not $AllowedUsers.Count) {throw 'Shared mode requires HTTPS and an explicit -AllowedUsers list.'}
} elseif ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1','localhost','[::1]','::1')) {throw 'Default mode supports loopback HTTP only. Shared mode requires HTTPS.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $WebRoot) {
    $archive=Join-Path $root 'dashboard.zip'
    if (-not (Test-Path -LiteralPath $archive)) {throw 'Bundled dashboard.zip is missing. Download the complete repository ZIP.'}
    $WebRoot=Join-Path $root '.runtime/web'
    $hash=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    $marker=Join-Path $root '.runtime/dashboard.sha256'
    if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $hash -or -not (Test-Path -LiteralPath (Join-Path $WebRoot 'index.html'))) {
        New-Item -ItemType Directory -Force -Path $WebRoot | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $WebRoot -Force
        Set-Content -LiteralPath $marker -Value $hash -Encoding ASCII
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $WebRoot 'index.html'))) {throw 'Dashboard index.html is missing.'}
Import-Module (Join-Path $PSScriptRoot 'Server.Core.psm1') -Force
$state=New-HealthState -WebRoot $WebRoot -BridgePath (Join-Path $PSScriptRoot 'Invoke-HealthCheck.ps1') -Origin $uri.GetLeftPart([UriPartial]::Authority) -AllowRemote ([bool]$AllowRemote) -AllowedUsers $AllowedUsers
$listener=New-Object Net.HttpListener
$listener.Prefixes.Add($Prefix)
if ($AllowRemote) {$listener.AuthenticationSchemes=[Net.AuthenticationSchemes]::Negotiate}
try {
    try {$listener.Start()} catch {throw 'Cannot start the Windows HTTP listener. Check the port, URL reservation and HTTPS certificate binding. Run as administrator for a local test, or ask your administrator to reserve this exact URL for your account. No settings were changed.'}
    $listener.TimeoutManager.EntityBody=[TimeSpan]::FromSeconds(15)
    $listener.TimeoutManager.HeaderWait=[TimeSpan]::FromSeconds(15)
    Write-Host "Server Health Check 2.0 - Windows PowerShell $($PSVersionTable.PSVersion)"
    Write-Host "Open $Prefix - keep this window open; press Ctrl+C to stop."
    Write-Host 'No Python, Node.js, package installation or model service is required.'
    if (-not $NoBrowser) {Start-Process $Prefix}
    while($listener.IsListening) {
        # Periodic waits let Ctrl+C stop an otherwise idle Windows PowerShell host.
        $pending=$listener.BeginGetContext($null,$null)
        while($listener.IsListening -and -not $pending.AsyncWaitHandle.WaitOne(250)) {}
        if(-not $listener.IsListening){break}
        $context=$listener.EndGetContext($pending)
        $pending.AsyncWaitHandle.Close()
        try {
            $request=$context.Request
            $identity=if($context.User -and $context.User.Identity.IsAuthenticated){$context.User.Identity.Name}else{''}
            $body=''
            if ($request.HttpMethod -eq 'POST') {
                if ($request.ContentLength64 -lt 0 -or $request.ContentLength64 -gt 16384) {
                    $context.Response.StatusCode=413;$context.Response.Close();continue
                }
                $reader=New-Object IO.StreamReader($request.InputStream,([Text.UTF8Encoding]::new($false,$true)))
                try {$body=$reader.ReadToEnd()} finally {$reader.Dispose()}
            }
            $headers=@{Host=$request.Headers['Host'];Origin=$request.Headers['Origin'];Authorization=$request.Headers['Authorization']}
            $result=Invoke-HealthRequest -State $state -Request @{Method=$request.HttpMethod;Path=$request.Url.AbsolutePath;Headers=$headers;Body=$body;RemoteAddress=$request.RemoteEndPoint.Address.ToString();Identity=$identity;IsSecure=$request.IsSecureConnection}
            $response=$context.Response
            $response.StatusCode=$result.Status;$response.ContentType=$result.ContentType
            $response.Headers['Cache-Control']='no-store'
            $response.Headers['X-Content-Type-Options']='nosniff'
            $response.Headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            $bytes=[Text.Encoding]::UTF8.GetBytes([string]$result.Text)
            $response.ContentLength64=$bytes.Length
            $response.OutputStream.Write($bytes,0,$bytes.Length)
            $response.Close()
        } catch {
            # Do not write request bodies, account names, passwords or raw exceptions to logs.
            try {$context.Response.StatusCode=500;$context.Response.Close()}catch{}
        } finally {$body=$null;$context=$null}
    }
} finally {$listener.Close();$state.Reports.Clear();$state.Token=$null}
