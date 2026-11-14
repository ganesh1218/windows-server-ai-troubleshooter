#requires -Version 5.1
# Maintainer-only packaging. End users receive dashboard.zip already built.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not (Test-Path -LiteralPath (Join-Path $root 'dist/index.html'))) {throw 'Run npm ci and npm run build before bundling.'}
Compress-Archive -Path (Join-Path $root 'dist/*') -DestinationPath (Join-Path $root 'dashboard.zip') -Force
Write-Host 'Bundled dashboard.zip. End users need only Windows PowerShell 5.1.'
