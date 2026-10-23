$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'runtime\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Распакуйте портативный архив целиком.' }
& $python -c "import sys; from shortcuts import create_shortcut; create_shortcut(sys.argv[1]); create_shortcut(sys.argv[1], 'programs')" $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать ярлыки Game Clips.' }
