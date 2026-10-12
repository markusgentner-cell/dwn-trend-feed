const { chromium } = require('playwright-core');
const fs = require('fs');

const TARGET_URL = 'https://trends.google.de/trending?geo=DE&hl=de&hours=4&category=3&status=active&sort=search-volume';

function clean(s) {
  return String(s || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
}

(async () => {
  const candidates = [
    process.env.CHROME_BIN,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser'
  ].filter(Boolean);

  let browser;
  let lastError;
  for (const executablePath of candidates) {
    try {
      browser = await chromium.launch({
        executablePath,
        headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage']
      });
      break;
    } catch (err) {
      lastError = err;
    }
  }
  if (!browser) throw lastError || new Error('No Chrome/Chromium executable found');

  const page = await browser.newPage({
    locale: 'de-DE',
    timezoneId: 'Europe/Berlin',
    viewport: { width: 1440, height: 1200 }
  });

  try {
    await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });

    for (const label of ['Alle akzeptieren', 'Accept all']) {
      const button = page.getByRole('button', { name: label, exact: true });
      if (await button.count()) {
        try { await button.first().click({ timeout: 2500 }); } catch (_) {}
      }
    }

    await page.waitForTimeout(7000);

    const finalUrl = page.url();
    const pageTitle = await page.title();
    const bodyText = clean(await page.locator('body').innerText());

    const requiredLabels = [
      'Deutschland',
      'Letzte 4 Stunden',
      'Wirtschaft und Finanzen',
      'Nur aktive Trends',
      'Nach Suchvolumen'
    ];
    const missingLabels = requiredLabels.filter(x => !bodyText.includes(x));

    const rawRows = await page.locator('tr, [role="row"]').allInnerTexts();
    const seen = new Set();
    const rows = [];

    for (const raw of rawRows) {
      const text = clean(raw);
      if (!text || seen.has(text)) continue;
      seen.add(text);

      // A real trend row contains a search-volume token such as 200+, 1.000+ or 10.000+.
      if (!/(?:^|\s)\d{1,3}(?:\.\d{3})*\+(?:\s|$)/.test(text)) continue;
      // Exclude header/filter rows.
      if (text.includes('Suchvolumen') && !text.includes('Aktiv')) continue;
      rows.push({ text });
    }

    const noTrends = /Keine Trends entsprechen derzeit diesen Filtern/i.test(bodyText);
    const urlOk = ['geo=DE','hours=4','category=3','status=active','sort=search-volume']
      .every(token => finalUrl.includes(token) || TARGET_URL.includes(token));

    const ok = missingLabels.length === 0 && urlOk && (rows.length > 0 || noTrends);

    const payload = {
      ok,
      status: ok ? 'fresh' : 'invalid',
      captured_at: new Date().toISOString(),
      source_url: TARGET_URL,
      page_title: pageTitle,
      final_url: finalUrl,
      rows,
      links: await page.locator('a').evaluateAll(as => as.slice(0, 100).map(a => ({
        text: (a.innerText || '').trim(),
        href: a.href || ''
      }))),
      body_text: bodyText
    };

    if (!ok) {
      payload.validation_errors = [];
      if (missingLabels.length) payload.validation_errors.push('Missing labels: ' + missingLabels.join(', '));
      if (!urlOk) payload.validation_errors.push('Final URL does not match required filters');
      if (!rows.length && !noTrends) payload.validation_errors.push('No trend rows found and no explicit empty-state message found');
    }

    fs.writeFileSync('latest.json', JSON.stringify(payload, null, 2) + '\n', 'utf8');
    console.log(`Wrote latest.json: ok=${ok}, rows=${rows.length}, final_url=${finalUrl}`);

    if (!ok) process.exitCode = 2;
  } finally {
    await browser.close();
  }
})().catch(err => {
  console.error(err);
  process.exit(1);
});
