#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$')][string[]]$ComputerName,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../private-data'),
    [switch]$UseSSL,
    [ValidateRange(1,30)][int]$Days = 7
)
$ErrorActionPreference = 'Stop'
$credential = Get-Credential -Message 'Remote diagnostic account (never saved)'
if (-not $credential) { throw 'Credentials are required.' }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
# Restrict private reports to the current operator and SYSTEM before writing.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $OutputDirectory /inheritance:r /grant:r "${identity}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect output directory ACL.' }
try {
foreach ($computer in $ComputerName) {
    $session = $null; $transport = 'WinRM'; $errors = [System.Collections.Generic.List[object]]::new()
    $report = [ordered]@{schemaVersion=1; id=$computer; name=$computer; simulated=$false; collectedAt=[DateTime]::UtcNow.ToString('o'); transport=$null; cpu=$null; memory=$null; drives=@(); rdp=$null; patches=@(); services=@(); events=@(); reboots=@(); errors=@()}
    try {
        try {
            $options = New-CimSessionOption -Protocol Wsman -UseSsl:$UseSSL
            $session = New-CimSession -ComputerName $computer -Credential $credential -Authentication Negotiate -SessionOption $options -OperationTimeoutSec 30
            Get-CimInstance -CimSession $session -ClassName Win32_OperatingSystem -ErrorAction Stop | Out-Null
        } catch {
            if ($session) { Remove-CimSession $session; $session=$null }
            $errors.Add(@{section='WinRM';message='WinRM failed; attempting DCOM. Check authentication, listener and firewall.'})
            $transport='DCOM'
            $session = New-CimSession -ComputerName $computer -Credential $credential -SessionOption (New-CimSessionOption -Protocol Dcom) -OperationTimeoutSec 30
        }
        $report.transport=$transport
        function Read-Section([string]$Name,[scriptblock]$Action) {
            try { & $Action } catch { $errors.Add(@{section=$Name;message='Collection unavailable. Verify permissions and connectivity.'}) }
        }
        $report.cpu = Read-Section 'cpu' { $cpus=@(Get-CimInstance Win32_Processor -CimSession $session); $value=($cpus | Measure-Object LoadPercentage -Average).Average; if ($null -ne $value) { [math]::Round($value,1) } }
        $report.memory = Read-Section 'memory' { $os=Get-CimInstance Win32_OperatingSystem -CimSession $session; @{totalGB=[math]::Round($os.TotalVisibleMemorySize/1MB,2);usedGB=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2);usedPercent=[math]::Round((1-$os.FreePhysicalMemory/$os.TotalVisibleMemorySize)*100,1)} }
        $report.drives = @(Read-Section 'drives' { Get-CimInstance Win32_LogicalDisk -CimSession $session | Sort-Object @{Expression={if($_.DeviceID -eq 'C:'){0}else{1}}},DeviceID | ForEach-Object { @{name=$_.DeviceID;label=$_.VolumeName;type=$_.DriveType;totalGB=if($null -ne $_.Size){[math]::Round($_.Size/1GB,2)}else{$null};freeGB=if($null -ne $_.FreeSpace){[math]::Round($_.FreeSpace/1GB,2)}else{$null}} } })
        $report.services = @(Read-Section 'services' { Get-CimInstance Win32_Service -CimSession $session | Sort-Object Name | ForEach-Object { @{name=$_.Name;displayName=$_.DisplayName;state=$_.State;startMode=$_.StartMode} } })
        $report.patches = @(Read-Section 'patches' { Get-CimInstance Win32_QuickFixEngineering -CimSession $session | ForEach-Object { @{id=$_.HotFixID;description=$_.Description;installedOn=[string]$_.InstalledOn;installedBy=$_.InstalledBy} } })
        $report.rdp = Read-Section 'rdp' {
            $setting=Get-CimInstance -Namespace root/cimv2/TerminalServices -ClassName Win32_TerminalServiceSetting -CimSession $session
            $service=Get-CimInstance Win32_Service -Filter "Name='TermService'" -CimSession $session
            $portSetting=Get-CimInstance -Namespace root/cimv2/TerminalServices -ClassName Win32_TSGeneralSetting -CimSession $session -Filter "TerminalName='RDP-tcp'"
            # TCP is a reachability observation, never proof that RDP authentication works.
            $tcp=Test-NetConnection -ComputerName $computer -Port 3389 -InformationLevel Quiet -WarningAction SilentlyContinue
            @{enabled=($setting.AllowTSConnections -eq 1);serviceState=$service.State;tcp3389=$tcp;nlaRequired=($portSetting.UserAuthenticationRequired -eq 1);note='Probe uses 3389; custom ports and firewall policy require separate review.'}
        }
        # Win32_NTLogEvent supports remote collection over the chosen CIM transport.
        $since=[Management.ManagementDateTimeConverter]::ToDmtfDateTime((Get-Date).AddDays(-$Days))
        $report.events = @(Read-Section 'events' { Get-CimInstance Win32_NTLogEvent -CimSession $session -Filter "(Logfile='System' OR Logfile='Application') AND (EventType=1 OR EventType=2) AND TimeGenerated >= '$since'" | Sort-Object TimeGenerated -Descending | Select-Object -First 100 | ForEach-Object { @{id=$_.EventCode;source=$_.SourceName;level=if($_.EventType -eq 1){'Error'}else{'Warning'};timestamp=$_.TimeGenerated.ToUniversalTime().ToString('o');message=$_.Message;account=$_.User} } })
        $report.reboots = @(Read-Section 'reboots' { Get-CimInstance Win32_NTLogEvent -CimSession $session -Filter "Logfile='System' AND (EventCode=1074 OR EventCode=6005 OR EventCode=6006 OR EventCode=6008 OR EventCode=41 OR EventCode=12 OR EventCode=13) AND TimeGenerated >= '$since'" | Sort-Object TimeGenerated -Descending | Select-Object -First 100 | ForEach-Object {
            $initiator=$_.User
            # USER32 1074 insertion strings: process, computer, reason, code, type, comment, account.
            if($_.EventCode -eq 1074 -and @($_.InsertionStrings).Count -ge 7){$initiator=$_.InsertionStrings[6]}
            @{id=$_.EventCode;source=$_.SourceName;timestamp=$_.TimeGenerated.ToUniversalTime().ToString('o');account=$initiator;message=$_.Message;kind=if($_.EventCode -eq 1074){'Planned action'}elseif($_.EventCode -in 41,6008){'Unexpected shutdown evidence'}else{'Lifecycle event'}}
        } })
    } catch { $errors.Add(@{section='connection';message='Connection failed on both transports. No credentials or raw exceptions saved.'}) }
    finally { if($session){Remove-CimSession $session}; $report.errors=@($errors.ToArray()) }
    $path=Join-Path $OutputDirectory ($computer+'.json'); $temp=$path+'.tmp'
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $path -Force
    Write-Host "Saved private report for $computer ($transport)."
}
} finally { $credential=$null }
