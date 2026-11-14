# Сборка и разработка

Нужны Windows x64, **Python 3.13 x64** с pip, .NET Framework 4.8 и интернет.
Для запуска интерфейса из исходников нужен установленный WebView2 Runtime.
Visual Studio не требуется: C#-компоненты собирает штатный компилятор .NET Framework.

## Структура репозитория

| Папка | Что внутри | В сборке |
| :--- | :--- | :--- |
| `src/` | Python-модули, интерфейс `src/ui`, модель шумоподавления `src/models`, PowerShell-помощники | `app/` |
| `native/` | `Launcher.cs` (AFTERPLAY.exe), `Updater.cs`, `ProcessAudio.cs`, `ReplayNotification.cs`, `RuntimeExit.cs`, `app.manifest` | собранные `.exe` / `.dll` |
| `scripts/` | `build_portable.py`, `build_translations.py`, `repackage_portable.py` | — |
| `tests/` | Тесты Python (`test_*.py`) и JavaScript (`test_*.js`), C#-пробы | — |
| `docs/` | Руководство, сборка, проверки; `legal/` — лицензии, `archive/` — старые заметки | `docs/` без `archive` |

`src/` повторяет папку `app/` готовой программы, поэтому пути внутри кода (`ui/`, `models/`) одинаковы при разработке и в сборке.

## Запуск из исходников

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:library /platform:x64 /out:src\ProcessAudio.dll native\ProcessAudio.cs
& $compiler /nologo /target:library /platform:x64 /r:System.Windows.Forms.dll /r:System.Drawing.dll /out:src\ReplayNotification.dll native\ReplayNotification.cs
.venv\Scripts\python.exe src\app.py
```

Без консольного окна — `pythonw.exe src\app.py`. Собранные `.dll` в Git не попадают.

`requirements.txt` перечисляет прямые зависимости, `requirements-lock.txt` закрепляет и транзитивные зависимости проверенной сборки.

## Тесты и проверки

Из корня репозитория:

```powershell
python -m unittest discover -s tests -t .          # Python
Get-ChildItem tests -Filter test_*.js | ForEach-Object { node $_.FullName }   # JavaScript
python scripts/build_translations.py --check       # словари EN и KO
```

`tests/__init__.py` сам добавляет `src/` в путь импорта, поэтому нужен ключ `-t .`.

Проверка окна без записи экрана:

```powershell
.venv\Scripts\python.exe src\app.py --smoke --data build\smoke-data
```

Результат — `build/smoke-data/verification-native-clips.json`, поле `ok` должно быть `true`. Эта проверка не заменяет настоящую запись: включите буфер, сохраните клип и проверьте готовый MP4.

## Переводы

Русский — исходный язык. `src/ui/en.json` и `src/ui/ko.json` переводят русские строки по ключу. Ключ с `{0}` совпадает с целой фразой, где `{0}` — любое значение. Ключ с `{#0}` — только число, и такая фраза находится и внутри длинного текста, например даты.

После правки словарей пересоберите браузерные каталоги:

```powershell
python scripts/build_translations.py
```

Проверка `--check` падает, если в корейском словаре не хватает строк английского или не совпадают места для чисел.

## Портативная сборка

```powershell
python scripts/build_portable.py                 # версия из src/version.py
python scripts/build_portable.py --version 1.16.0
```

Результат — `dist/AFTERPLAY-<версия>-Portable-Win64.zip` и `.sha256`. Сборка кладёт внутрь Python, закреплённые зависимости, FFmpeg (закреплённый URL и SHA-256) и подписанный установщик WebView2. Загрузки кэшируются в `build/downloads`. Скрипт не перезаписывает существующую папку сборки: для повторной сборки той же версии переименуйте прежние `build/portable-<версия>` и ZIP в `dist`.

Раскладка архива: в корне `AFTERPLAY.exe` и `README.md` (из `docs/PORTABLE.md`), программа в `app/`, справка и лицензии в `docs/`. Каталог контрольных сумм — `app/SHA256SUMS.json`, ключи относительны к корню portable-папки.

## Выпуск на GitHub

Выпуск собирает workflow **Portable release** (`.github/workflows/release.yml`). Он запускается, когда в `main` меняется `src/version.py`, при push тега `v*` или вручную. Workflow проверяет переводы и тесты, собирает архив и публикует выпуск с текстом из `docs/RELEASE.md`. Если выпуск с этой версией уже есть, workflow всё проверяет и собирает, но ничего не публикует.

Workflow **Tests** (`.github/workflows/tests.yml`) прогоняет те же проверки на других ветках и в pull request.

Порядок выпуска:

1. Поднимите `VERSION` в `src/version.py`.
2. Добавьте раздел в `CHANGELOG.md` и обновите `docs/RELEASE.md`.
3. Влейте изменения в `main`.

Встроенный обновлятор берёт только последний стабильный выпуск с архивом вида `AFTERPLAY-<версия>-Portable-Win64.zip`. Для перехода со старых установок (1.8.3 и раньше) служит `app/Update-Existing.ps1` из нового архива.
