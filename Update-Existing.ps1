param(
    [Parameter(Mandatory=$true)][string]$Target,
    [switch]$NoRestart
)
$ErrorActionPreference = 'Stop'
$stage = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$destination = (Resolve-Path -LiteralPath $Target).Path.TrimEnd('\')
if ($stage -eq $destination) { throw 'Распакуйте новый архив в отдельную папку и укажите прежнюю папку через -Target.' }
$exe = Join-Path $destination 'AFTERPLAY.exe'
if (Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -eq $exe }) {
    throw 'Сначала полностью закройте AFTERPLAY через меню трея и дождитесь сохранения.'
}
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $stage 'SHA256SUMS.json') | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $stage 'Updater.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.'Updater.exe') {
    throw 'Контрольная сумма обновлятора не совпадает с каталогом.'
}
$entries = @($manifest.PSObject.Properties | ForEach-Object { @{ path=$_.Name; sha256=$_.Value } })
$entries += @{ path='SHA256SUMS.json'; sha256=(Get-FileHash -LiteralPath (Join-Path $stage 'SHA256SUMS.json') -Algorithm SHA256).Hash.ToLowerInvariant() }
$versionText = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $stage 'version.py')
if ($versionText -notmatch "VERSION = '(\d+\.\d+\.\d+)'") { throw 'Некорректная версия в архиве.' }
$releaseVersion = $Matches[1]
$plan = @{
    target=$destination; stage=$stage; version=$releaseVersion; parent_pid=0;
    files=$entries; status=(Join-Path $destination 'data\update-status.json');
    restart=(-not $NoRestart); quiet=$true
}
$planPath = Join-Path $stage ('.install-plan-'+[Guid]::NewGuid().ToString('N')+'.json')
try {
    [IO.File]::WriteAllText($planPath,($plan | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = Join-Path $stage 'Updater.exe'
    $start.Arguments = '"'+$planPath+'"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $process = [Diagnostics.Process]::Start($start)
    $process.WaitForExit()
    $result = Get-Content -Raw -Encoding UTF8 -LiteralPath $plan.status | ConvertFrom-Json
    if ($process.ExitCode -ne 0) { throw $result.message }
    Write-Output ('AFTERPLAY '+$releaseVersion+' установлен. Резервная копия: '+$result.backup)
} finally {
    if (Test-Path -LiteralPath $planPath) { Remove-Item -LiteralPath $planPath }
}
