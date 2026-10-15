param([int]$Port = 5050)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $taskPython)) {
    $taskPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
}
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Python missing. See README for installation and run commands.' }
$taskSocket = [Net.Sockets.TcpClient]::new()
try { $taskSocket.Connect('127.0.0.1',27017); $taskMongoRunning=$true } catch { $taskMongoRunning=$false } finally { $taskSocket.Dispose() }
if (!$taskMongoRunning) {
    $taskMongoScript = Join-Path $PSScriptRoot '..\lab1\start.ps1'
    if (!(Test-Path -LiteralPath $taskMongoScript)) { throw 'Start MongoDB manually first; see README.' }
    & $taskMongoScript
}
$env:PORT = [string]$Port
Push-Location $PSScriptRoot
try { & $taskPython -X utf8 run.py } finally { Pop-Location }
