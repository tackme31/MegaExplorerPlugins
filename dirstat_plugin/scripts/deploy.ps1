<#
.SYNOPSIS
    Build the plugin in Release and install it, with Qt's DLLs, into bin/.

.DESCRIPTION
    plugin.json starts bin/MegaDirStatPlugin.exe, so after this the folder is a
    complete plugin: link it into MEGA Explorer's plugins folder with a junction
    (or copy it there) and restart the app.

.PARAMETER Config
    Release (default) or Debug. A Debug bin/ needs the debug CRT, which only a
    machine with Visual Studio has.
#>
[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')]
    [string]$Config = 'Release'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# The `cmake` on PATH may be an older copy (Strawberry Perl's) that cannot drive this MSVC.
$CMake = if ($env:MEGADIRSTAT_CMAKE) { $env:MEGADIRSTAT_CMAKE } else { 'C:/Qt/Tools/CMake_64/bin/cmake.exe' }

Push-Location $Root
try {
    # A running plugin holds its exe and DLLs open, and the install would fail half-way.
    Get-Process MegaDirStatPlugin -ErrorAction SilentlyContinue | Stop-Process -Force

    & $CMake --preset msvc
    if ($LASTEXITCODE) { throw 'configure failed' }
    & $CMake --build --preset ($Config.ToLower()) --target MegaDirStatPlugin
    if ($LASTEXITCODE) { throw 'build failed' }

    $bin = Join-Path $Root 'bin'
    if (Test-Path $bin) { Remove-Item -Recurse -Force $bin }
    & $CMake --install build/msvc --config $Config --prefix $bin
    if ($LASTEXITCODE) { throw 'install failed' }

    Write-Host "Installed into $bin"
}
finally {
    Pop-Location
}
