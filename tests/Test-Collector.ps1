#requires -Version 5.1
$ErrorActionPreference='Stop'
$path=Join-Path $PSScriptRoot '../scripts/Collect-Diagnostics.ps1'
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null
if($errors.Count){throw ($errors | Out-String)}
$text=Get-Content -LiteralPath $path -Raw
foreach($required in @('Get-Credential','-Protocol Dcom','Remove-CimSession','InsertionStrings[6]','ToUniversalTime','icacls.exe')) {
    if(-not $text.Contains($required)){throw "Missing collector contract: $required"}
}
foreach($banned in @('Invoke-Expression','ConvertFrom-SecureString','-AsPlainText','SkipCACheck','SkipCNCheck','TrustedHosts')) {
    if($text.Contains($banned)){throw "Unsafe collector construct: $banned"}
}
Write-Host 'PowerShell parser and safety contract checks passed (not a remote integration test).'
$bridge=Join-Path $PSScriptRoot '../scripts/Invoke-HealthCheck.ps1'
[System.Management.Automation.Language.Parser]::ParseFile($bridge,[ref]$tokens,[ref]$errors) | Out-Null
if($errors.Count){throw ($errors | Out-String)}
$bridgeText=Get-Content -LiteralPath $bridge -Raw
foreach($required in @('[Console]::In.ReadToEnd()','-NoPersist','PSCredential','Dispose()')) {
    if(-not $bridgeText.Contains($required)){throw "Missing private bridge contract: $required"}
}
