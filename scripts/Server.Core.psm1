#requires -Version 5.1
# PowerShell-only HTTP routing and bounded, read-only collection.
Set-StrictMode -Version 2

function New-HealthState {
    param([string]$WebRoot,[string]$BridgePath,[string]$Origin='http://127.0.0.1:8000',[bool]$AllowRemote=$false,[string[]]$AllowedUsers=@())
    $bytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try {$rng.GetBytes($bytes)} finally {$rng.Dispose()}
    @{Token=[Convert]::ToBase64String($bytes);Origin=$Origin;Authority=([uri]$Origin).Authority;WebRoot=[IO.Path]::GetFullPath($WebRoot);BridgePath=[IO.Path]::GetFullPath($BridgePath);AllowRemote=$AllowRemote;AllowedUsers=$AllowedUsers;Reports=@{}}
}

function New-HealthResponse {
    param([int]$Status=200,$Value,[string]$Text,[string]$ContentType='application/json; charset=utf-8')
    if ($PSBoundParameters.ContainsKey('Value')) {$Text=ConvertTo-Json -InputObject $Value -Depth 16 -Compress}
    @{Status=$Status;Text=$Text;ContentType=$ContentType}
}

function Test-HealthTarget {
    param($Target)
    if ($Target -isnot [string] -or $Target.Length -lt 1 -or $Target.Length -gt 253) {return $false}
    $ip=$null
    if ([Net.IPAddress]::TryParse($Target,[ref]$ip)) {return $true}
    foreach($label in $Target.Split('.')) {
        if ($label -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$') {return $false}
    }
    return $true
}

function Test-HealthToken {
    param([string]$Actual,[string]$Expected)
    if ($Actual.Length -ne $Expected.Length) {return $false}
    $difference=0
    for($i=0;$i -lt $Expected.Length;$i++) {$difference=$difference -bor ([int][char]$Actual[$i] -bxor [int][char]$Expected[$i])}
    return $difference -eq 0
}

function Invoke-CollectorProcess {
    param([hashtable]$Payload,[string]$BridgePath,[int]$TimeoutSeconds=180)
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $info.Arguments='-NoProfile -NonInteractive -File "'+$BridgePath+'"'
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $utf8=[Text.UTF8Encoding]::new($false)
    $info.StandardOutputEncoding=$utf8;$info.StandardErrorEncoding=$utf8
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$info
    try {
        [void]$process.Start()
        # Drain both pipes before waiting, avoiding blocked output buffers.
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write((ConvertTo-Json -InputObject $Payload -Compress))
        $process.StandardInput.Close()
        if (-not $process.WaitForExit($TimeoutSeconds*1000)) {
            $process.Kill();$process.WaitForExit()
            return @{TimedOut=$true;ExitCode=-1;Output=''}
        }
        @{TimedOut=$false;ExitCode=$process.ExitCode;Output=$stdout.GetAwaiter().GetResult()}
    } finally {
        $Payload.Clear()
        $process.Dispose()
    }
}

function Invoke-HealthRequest {
    param([hashtable]$State,[hashtable]$Request,[scriptblock]$Collector)
    $headers=$Request.Headers
    if ($headers['Host'] -ne $State.Authority) {return New-HealthResponse 400 @{detail='Unexpected Host header.'}}
    $websiteRequest=($headers['Origin'] -eq 'https://wshc.ganesh18.dpdns.org' -and -not $State.AllowRemote -and $Request.Path -in @('/api/connect','/api/reports','/api/health'))
    if ($headers['Origin'] -and $headers['Origin'] -ne $State.Origin -and -not $websiteRequest) {return New-HealthResponse 403 @{detail='Origin denied.'}}
    if ($State.AllowRemote) {
        if (-not $Request.IsSecure -or -not $Request.Identity -or $State.AllowedUsers -notcontains $Request.Identity) {
            return New-HealthResponse 403 @{detail='HTTPS and an allowed Windows identity are required.'}
        }
        $owner=$Request.Identity
    } else {
        $ip=$null
        if (-not [Net.IPAddress]::TryParse($Request.RemoteAddress,[ref]$ip) -or -not [Net.IPAddress]::IsLoopback($ip)) {
            return New-HealthResponse 403 @{detail='Loopback clients only.'}
        }
        $owner='local'
    }
    if ($Request.Method -eq 'OPTIONS' -and $websiteRequest) {return New-HealthResponse -Status 204 -Text ''}
    if ($Request.Method -eq 'GET' -and $Request.Path -eq '/api/health') {
        return New-HealthResponse 200 @{status='ok';mode='powershell';application='Server Health Check';version='2.0.0'}
    }
    if ($Request.Method -eq 'GET' -and $Request.Path -eq '/') {
        $document=[IO.File]::ReadAllText((Join-Path $State.WebRoot 'index.html'))
        $meta='<meta name="serverscope-session" content="'+[Net.WebUtility]::HtmlEncode($State.Token)+'">'
        return New-HealthResponse -Status 200 -Text $document.Replace('</head>',$meta+'</head>') -ContentType 'text/html; charset=utf-8'
    }
    if ($Request.Method -eq 'GET' -and $Request.Path -match '^/assets/[A-Za-z0-9_-]+\.(js|css)$') {
        $file=Join-Path $State.WebRoot $Request.Path.TrimStart('/')
        if (-not [IO.File]::Exists($file)) {return New-HealthResponse 404 @{detail='Asset not found.'}}
        $mime=if($Request.Path.EndsWith('.js')){'application/javascript; charset=utf-8'}else{'text/css; charset=utf-8'}
        return New-HealthResponse -Status 200 -Text ([IO.File]::ReadAllText($file)) -ContentType $mime
    }
    if ($Request.Path -notin @('/api/connect','/api/reports')) {return New-HealthResponse 404 @{detail='Not found.'}}
    if (-not (Test-HealthToken ([string]$headers['Authorization']) ('Bearer '+$State.Token))) {return New-HealthResponse 401 @{detail='Local session expired. Reload the dashboard.'}}
    if ($Request.Method -eq 'GET' -and $Request.Path -eq '/api/reports') {
        $items=@()
        if ($State.Reports.ContainsKey($owner)) {$items=@($State.Reports[$owner].Values)}
        return New-HealthResponse -Status 200 -Value $items
    }
    if ($Request.Method -ne 'POST' -or $Request.Path -ne '/api/connect') {return New-HealthResponse 405 @{detail='Method not allowed.'}}
    if ([Text.Encoding]::UTF8.GetByteCount([string]$Request.Body) -gt 16384) {return New-HealthResponse 413 @{detail='Connection request is too large.'}}
    $data=$null;$payload=$null
    try {
        $data=ConvertFrom-Json -InputObject $Request.Body -ErrorAction Stop
        if ($data -isnot [pscustomobject]) {throw 'Invalid request'}
        $names=@($data.PSObject.Properties.Name)
        if (@('target','username','password' | Where-Object {$names -notcontains $_}).Count) {throw 'Missing fields'}
        if (-not (Test-HealthTarget $data.target) -or $data.username -isnot [string] -or $data.username.Length -lt 1 -or $data.username.Length -gt 256 -or $data.password -isnot [string] -or $data.password.Length -lt 1 -or $data.password.Length -gt 4096) {throw 'Invalid fields'}
        $ssl=$true
        if ($names -contains 'use_ssl') {if($data.use_ssl -isnot [bool]){throw 'Invalid option'};$ssl=$data.use_ssl}
        $payload=@{target=$data.target;username=$data.username;password=$data.password;use_ssl=$ssl}
    } catch {
        return New-HealthResponse 400 @{detail='Enter a valid server name or IP, username, password and connection option.'}
    }
    try {
        $target=$payload.target
        if ($Collector) {$result=& $Collector $payload $State.BridgePath} else {$result=Invoke-CollectorProcess $payload $State.BridgePath}
        if ($result.TimedOut) {return New-HealthResponse 504 @{detail='Health check timed out after 180 seconds. Verify connectivity and server load.'}}
        if ($result.ExitCode -ne 0) {return New-HealthResponse 502 @{detail='Collection failed. Check PowerShell execution policy, credentials, connectivity and remote permissions.'}}
        $report=ConvertFrom-Json -InputObject $result.Output.TrimStart([char]0xFEFF) -ErrorAction Stop
        if ($report.schemaVersion -ne 1 -or $report.id -ne $target) {throw 'Invalid collector result'}
        if (@($report.errors | Where-Object {$_.section -eq 'connection'}).Count) {return New-HealthResponse 502 @{detail='Unable to connect using WinRM or DCOM. Verify the server address, credentials, firewall and permissions.'}}
        $report | Add-Member -NotePropertyName simulated -NotePropertyValue $false -Force
        if (-not $State.Reports.ContainsKey($owner)) {$State.Reports[$owner]=@{}}
        $State.Reports[$owner][$target]=$report
        return New-HealthResponse 200 $report
    } catch {
        return New-HealthResponse 502 @{detail='The PowerShell collector could not return a valid report.'}
    } finally {
        if($payload){$payload.Clear()}
        if($data){$data.password=$null}
    }
}

Export-ModuleMember -Function New-HealthState,Invoke-HealthRequest,Invoke-CollectorProcess,Test-HealthTarget
