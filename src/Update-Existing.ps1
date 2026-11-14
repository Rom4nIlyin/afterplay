param(
    [Parameter(Mandatory=$true)][string]$Target,
    [switch]$NoRestart
)
$ErrorActionPreference = 'Stop'
# PowerShell 7 can pass its module path to Windows PowerShell 5.1.
# Load the built-in utility module from this host for Get-FileHash.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
$stage = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
if ((Split-Path -Leaf $stage) -eq 'app' -and (Test-Path -LiteralPath (Join-Path $stage 'app.py'))) {
    $stage = Split-Path -Parent $stage
}
$prefix = if (Test-Path -LiteralPath (Join-Path $stage 'app\app.py')) { 'app\' } else { '' }
$destination = (Resolve-Path -LiteralPath $Target).Path.TrimEnd('\')
if ($stage -eq $destination) { throw 'Распакуйте новый архив в отдельную папку и укажите прежнюю папку через -Target.' }
$exe = Join-Path $destination 'AFTERPLAY.exe'
if (Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -eq $exe }) {
    throw 'Сначала полностью закройте AFTERPLAY через меню трея и дождитесь сохранения.'
}
$catalog = $prefix + 'SHA256SUMS.json'
$helper = $prefix + 'Updater.exe'
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $stage $catalog) | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $stage $helper) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.($helper.Replace('\','/'))) {
    throw 'Контрольная сумма обновлятора не совпадает с каталогом.'
}
$entries = @($manifest.PSObject.Properties | ForEach-Object { @{ path=$_.Name; sha256=$_.Value } })
$entries += @{ path=$catalog.Replace('\','/'); sha256=(Get-FileHash -LiteralPath (Join-Path $stage $catalog) -Algorithm SHA256).Hash.ToLowerInvariant() }
$versionText = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $stage ($prefix + 'version.py'))
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
    $start.FileName = Join-Path $stage $helper
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
