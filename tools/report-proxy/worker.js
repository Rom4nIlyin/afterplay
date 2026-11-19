// AFTERPLAY report proxy: receives a problem report from the app and files it as a
// GitHub issue. The GitHub token lives only here (a Worker secret), never in the app.
//
// Secrets / vars (see README.md):
//   GITHUB_TOKEN  fine-grained token, this repository only, Issues: Read and write
//   REPOSITORY    "owner/name"
//   LIMITER       rate-limit binding from wrangler.toml

const APP_KEY = 'afterplay-report-v1';
const LABEL = 'bug-report';
const MAX_BODY = 96 * 1024;          // request size
const MAX_REPORT = 56 * 1024;        // GitHub caps an issue body at 65 536 characters
const MAX_DESCRIPTION = 4000;

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8' },
});

// Reports are untrusted text: no @mentions (they notify people), no #refs, and the
// log goes into a fence that its own content cannot close.
const quiet = s => String(s || '').replace(/@/g, '@​').replace(/#(\d)/g, '#​$1');
const fence = s => {
  const longest = Math.max(2, ...(String(s).match(/`+/g) || []).map(x => x.length));
  const f = '`'.repeat(longest + 1);
  return `${f}text\n${s}\n${f}`;
};
const clip = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n) + '\n…(обрезано)' : s; };

async function github(env, path, init = {}) {
  const r = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'afterplay-report-proxy',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 300)}`);
  return r.status === 204 ? {} : r.json();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/report') return json({ ok: false, error: 'Not found' }, 404);
    if (request.headers.get('X-AfterPlay-Key') !== APP_KEY) return json({ ok: false, error: 'Forbidden' }, 403);
    if (!/^AFTERPLAY\/\d+\.\d+\.\d+$/.test(request.headers.get('User-Agent') || '')) return json({ ok: false, error: 'Forbidden' }, 403);

    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    if (env.LIMITER) {
      const { success } = await env.LIMITER.limit({ key: ip });
      if (!success) return json({ ok: false, error: 'Слишком много отчётов' }, 429);
    }

    const raw = await request.text();
    if (raw.length > MAX_BODY) return json({ ok: false, error: 'Отчёт слишком большой' }, 413);
    let p;
    try { p = JSON.parse(raw); } catch { return json({ ok: false, error: 'Некорректный отчёт' }, 400); }

    const version = String(p.version || '');
    if (!/^\d+\.\d+\.\d+$/.test(version)) return json({ ok: false, error: 'Некорректная версия' }, 400);
    const fp = /^[0-9a-f]{12}$/.test(p.fingerprint || '') ? p.fingerprint : '';
    const report = clip(p.report, MAX_REPORT);
    if (!report.trim()) return json({ ok: false, error: 'Пустой отчёт' }, 400);
    const description = quiet(clip(p.description, MAX_DESCRIPTION).trim());
    const title = quiet(String(p.title || 'Отчёт о проблеме').replace(/\s+/g, ' ').trim().slice(0, 100));
    const summary = quiet(String(p.summary || '').slice(0, 200));

    const repo = env.REPOSITORY;
    const marker = fp ? `afterplay-fp:${fp}` : '';
    const section = [
      `**Версия:** ${version}`,
      summary ? `**Ошибка:** ${summary}` : '',
      '',
      '### Что делал пользователь',
      description || '_не указано_',
      '',
      '<details><summary>Журнал (личные данные удалены в приложении)</summary>',
      '',
      fence(report),
      '',
      '</details>',
    ].filter(x => x !== null).join('\n');

    try {
      // The same failure from many users becomes one issue with comments.
      if (marker) {
        const q = encodeURIComponent(`repo:${repo} is:issue is:open label:${LABEL} "${marker}" in:body`);
        const found = await github(env, `/search/issues?q=${q}&per_page=1`);
        const issue = found.items && found.items[0];
        if (issue) {
          await github(env, `/repos/${repo}/issues/${issue.number}/comments`, {
            method: 'POST', body: JSON.stringify({ body: `Повтор от другого запуска.\n\n${section}` }),
          });
          return json({ ok: true, duplicate: true, number: issue.number, url: issue.html_url });
        }
      }
      const issue = await github(env, `/repos/${repo}/issues`, {
        method: 'POST',
        body: JSON.stringify({
          title: `[Отчёт] ${title}`,
          labels: [LABEL],
          body: `${section}\n\n<!-- ${marker || 'afterplay-fp:none'} -->`,
        }),
      });
      return json({ ok: true, duplicate: false, number: issue.number, url: issue.html_url });
    } catch (e) {
      console.error(String(e));
      return json({ ok: false, error: 'Не удалось создать отчёт на GitHub' }, 502);
    }
  },
};
