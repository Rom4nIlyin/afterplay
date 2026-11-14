$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'runtime\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Распакуйте портативный архив целиком.' }
$target = if ((Split-Path -Leaf $PSScriptRoot) -eq 'app') { Split-Path -Parent $PSScriptRoot } else { $PSScriptRoot }
& $python -c "import sys; sys.path.insert(0,sys.argv[1]); from shortcuts import create_shortcut; create_shortcut(sys.argv[2]); create_shortcut(sys.argv[2], 'programs')" $PSScriptRoot $target
if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать ярлыки AFTERPLAY.' }
