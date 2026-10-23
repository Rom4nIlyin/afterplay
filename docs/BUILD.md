# Сборка на Windows

Нужны Windows x64, **Python 3.13 x64** с pip, .NET Framework 4.8 и интернет.
Для разработки интерфейса нужен установленный WebView2 Runtime.
Visual Studio не требуется: C#-компоненты компилируются штатным компилятором .NET Framework.

## Готовая портативная сборка

В корне клонированного репозитория:

```powershell
python scripts/build_portable.py
```

Результат: `dist/Game-Clips-1.1-Portable-Win64.zip` и файл `.sha256`.
Сборка содержит Python, закреплённые зависимости, FFmpeg и автономный
подписанный установщик WebView2. Личные файлы из `data` не копируются.
Загруженные установщики кэшируются в `build/downloads`.
Для зависимостей используются готовые wheels; небольшой чисто Python-пакет
`proxy_tools` собирается pip из исходного дистрибутива и не требует C/C++-компилятора.
Скрипт не перезаписывает существующую папку сборки. Для другой версии:

```powershell
python scripts/build_portable.py --version 1.1.1
```

При повторной сборке той же версии переименуйте предыдущую папку `build/portable-1.1`
и предыдущий ZIP в `dist`, либо выберите другой номер версии.
Не собирайте программу в папку с личными записями.

## Запуск для разработки

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Скомпилируйте библиотеки в корень репозитория:

```powershell
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:library /platform:x64 /out:ProcessAudio.dll ProcessAudio.cs
& $compiler /nologo /target:library /platform:x64 /r:System.Windows.Forms.dll /r:System.Drawing.dll /out:ReplayNotification.dll ReplayNotification.cs
.venv\Scripts\python.exe app.py
```

Без консольного окна:

```powershell
.venv\Scripts\pythonw.exe app.py
```

`requirements.txt` перечисляет прямые зависимости. `requirements-lock.txt` закрепляет
также транзитивные зависимости проверенной сборки. Драйвер видеокарты и системные
компоненты Windows не включаются в Python-зависимости.

## Проверка окна и элементов управления

```powershell
.venv\Scripts\python.exe app.py --smoke --data build\smoke-data
```

Проверка создаёт скрытое окно WebView2, открывает раздел повтора и проверяет наличие
семи вариантов длительности и четырёх режимов звука. Результат:
`build/smoke-data/verification-native-clips.json`, поле `ok` должно быть `true`.
Запись экрана этим режимом не включается.

Эта проверка не заменяет реальную запись: включите буфер, сохраните клип и проверьте
готовый MP4. Для аудиоизоляции воспроизводите разные звуки в двух независимых
приложениях, захватите одно и убедитесь, что второе не слышно в сохранённом файле.

## Что хранить в Git

Исходники Python/C#, интерфейс, иконки, документацию и списки зависимостей.
`data`, `runtime`, `build`, `dist`, скачанные установщики, видео и собранные EXE/DLL
исключены через `.gitignore`. Готовые архивы публикуются как **GitHub Release assets**.
