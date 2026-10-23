$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $link = $shell.CreateShortcut((Join-Path $folder 'Game Clips.lnk'))
    $link.TargetPath = Join-Path $PSScriptRoot 'Game Clips.exe'
    $link.WorkingDirectory = $PSScriptRoot
    $link.IconLocation = (Join-Path $PSScriptRoot 'Game Clips.exe') + ',0'
    $link.Description = 'Game Clips — видеотека и повтор последних 1–30 минут'
    $link.Save()
}
