# Прокси для отчётов о проблемах

Кнопка **Настройки → Журнал → Отправить разработчику** отправляет отчёт сюда, а этот
Cloudflare Worker создаёт Issue в репозитории с меткой `bug-report`. Токен GitHub хранится
только в Worker: в программе его нет, поэтому достать его из `.exe` нельзя.

```
AFTERPLAY ──POST /report──► Worker (токен, лимиты) ──► GitHub Issues
```

Что делает Worker:

- принимает только запросы с заголовком `X-AfterPlay-Key` и `User-Agent: AFTERPLAY/x.y.z`
  (это фильтр от случайного мусора, а не защита: ключ виден в коде программы);
- не больше 3 отчётов в минуту с одного IP-адреса, не больше 96 КБ на запрос;
- одинаковая ошибка (тот же отпечаток) от разных людей добавляется комментарием к уже
  открытому Issue, а не плодит новые;
- убирает `@упоминания` и `#ссылки` из присланного текста, журнал кладёт в свёрнутый блок.

Личные данные (пути, имя пользователя и компьютера, названия клипов, окон и профилей)
программа удаляет **до** отправки; пользователь видит отчёт целиком по кнопке «Показать».

## Развёртывание (один раз, ~10 минут)

1. **Аккаунт Cloudflare** — бесплатный тариф подходит: https://dash.cloudflare.com/sign-up

2. **Токен GitHub.** GitHub → Settings → Developer settings → Personal access tokens →
   **Fine-grained tokens** → Generate new token:
   - Repository access: **Only select repositories** → `Rom4nIlyin/afterplay`;
   - Permissions → Repository → **Issues: Read and write** (больше ничего);
   - срок действия — на ваше усмотрение (потом токен нужно будет заменить шагом 4).

3. **Метка для отчётов** (если её ещё нет):

   ```powershell
   gh label create bug-report --repo Rom4nIlyin/afterplay --color D93F0B --description "Отчёт из программы"
   ```

4. **Публикация Worker** (нужен Node.js), из этой папки:

   ```powershell
   npx wrangler login
   npx wrangler secret put GITHUB_TOKEN
   npx wrangler deploy
   ```

   На `secret put` вставьте токен из шага 2. После `deploy` wrangler напечатает адрес вида
   `https://afterplay-reports.<ваше-имя>.workers.dev`.

5. **Адрес в программе** — `REPORT_ENDPOINT` в `src/bug_report.py`. Сейчас там
   `https://afterplay-reports.report-proxy.workers.dev/report`; при переезде Worker поменяйте
   его и выпустите новую версию. Пустое значение выключает отправку, «Скопировать» работает всегда.

   Проверить без выпуска можно переменной окружения:

   ```powershell
   $env:AFTERPLAY_REPORT_ENDPOINT = 'https://afterplay-reports.<ваше-имя>.workers.dev/report'
   ```

## Разбор отчётов

```powershell
gh issue list --repo Rom4nIlyin/afterplay --label bug-report
gh issue view <номер> --repo Rom4nIlyin/afterplay --comments
```

В каждом отчёте есть версия программы, отпечаток ошибки и место в коде
(например `ValueError в replay.py:begin_replay/replay.py:start`), а журнал — со стектрейсами.
Можно попросить Claude Code: «посмотри новые bug-report и исправь».

Журнал Worker при ошибках: `npx wrangler tail`.
