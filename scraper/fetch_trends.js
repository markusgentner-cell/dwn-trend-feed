const { chromium } = require('playwright-core');
const fs = require('fs');

const TARGET_URL = 'https://trends.google.de/trending?geo=DE&hl=de&hours=4&category=3&status=active&sort=search-volume';

function clean(s) {
  return String(s || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
}

async function clickText(page, text) {
  const loc = page.getByText(text, { exact: true }).filter({ visible: true });
  const count = await loc.count();
  if (!count) throw new Error('UI control not found: ' + text);
  const el = loc.first();
  if (text === 'Alle Trends' || text === 'Nach Relevanz') {
    const chain = await el.evaluate(node => {
      const out = [];
      let cur = node;
      for (let i = 0; i < 5 && cur; i++, cur = cur.parentElement) {
        out.push(cur.outerHTML.slice(0, 1200));
      }
      return out;
    });
    console.log('DOM chain for "' + text + '":', JSON.stringify(chain));
  }
  try {
    await el.click({ timeout: 3000 });
  } catch (_) {
    await el.evaluate(node => {
      const clickable = node.closest('[role="option"], [role="menuitem"], [role="button"], li, div') || node;
      clickable.click();
    });
  }
}

async function hasVisibleExactText(page, text) {
  return (await page.getByText(text, { exact: true }).filter({ visible: true }).count()) > 0;
}

async function ensureFilterByText(page, currentText, desiredText, desiredPattern) {
  if (await hasVisibleExactText(page, desiredText)) return;
  await clickText(page, currentText);
  await page.waitForTimeout(700);

  const matches = page.getByText(desiredPattern).filter({ visible: true });
  if (!(await matches.count())) {
    throw new Error('Desired filter option not found: ' + desiredText);
  }
  const chosen = matches.last();
  try {
    await chosen.click({ timeout: 3000 });
  } catch (_) {
    await chosen.evaluate(node => {
      const clickable = node.closest('[role="option"], [role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"], li, div') || node;
      clickable.click();
    });
  }
  await page.waitForTimeout(1400);

  if (!(await hasVisibleExactText(page, desiredText))) {
    throw new Error('Filter did not switch to: ' + desiredText);
  }
}

async function selectMenuOption(page, buttonNamePattern, optionPattern, desiredButtonPattern, label) {
  const button = page.getByRole('button', { name: buttonNamePattern }).filter({ visible: true }).first();
  if (!(await button.count())) throw new Error(label + ' button not found');

  const initialLabel = await button.getAttribute('aria-label') || '';
  if (desiredButtonPattern.test(initialLabel)) return;

  await button.click({ timeout: 5000 });
  await page.waitForTimeout(600);

  const expanded = await button.getAttribute('aria-expanded');
  console.log(label + ' aria-expanded after click:', expanded);

  let menu = page.locator('[role="menu"]:visible');
  if (!(await menu.count())) menu = page.locator('[role="listbox"]:visible');
  if (!(await menu.count())) {
    throw new Error(label + ' menu did not open');
  }
  menu = menu.last();

  const menuText = clean(await menu.innerText());
  console.log(label + ' menu text:', menuText);

  const roleOptions = menu.locator('[role="switch"], [role="menuitemcheckbox"], [role="menuitemradio"], [role="menuitem"], [role="option"]');
  let chosen = null;
  const n = await roleOptions.count();
  for (let i = 0; i < n; i++) {
    const item = roleOptions.nth(i);
    const txt = clean((await item.innerText()) + ' ' + ((await item.getAttribute('aria-label')) || ''));
    if (optionPattern.test(txt)) {
      chosen = item;
      console.log(label + ' chosen option:', txt,
        'role=' + (await item.getAttribute('role')),
        'aria-checked=' + (await item.getAttribute('aria-checked')));
      break;
    }
  }
  if (!chosen) {
    const dump = await menu.locator('*').evaluateAll(nodes => nodes
      .map(n => ({
        tag: n.tagName,
        role: n.getAttribute('role'),
        ariaChecked: n.getAttribute('aria-checked'),
        ariaLabel: n.getAttribute('aria-label'),
        jsname: n.getAttribute('jsname'),
        text: (n.innerText || n.textContent || '').trim().replace(/\s+/g,' ').slice(0,200)
      }))
      .filter(x => x.role || x.ariaChecked || x.ariaLabel || /aktive/i.test(x.text))
      .slice(0,120));
    console.log(label + ' menu DOM dump:', JSON.stringify(dump));
    throw new Error(label + ' option not found: ' + optionPattern);
  }

  try {
    await chosen.click({ timeout: 3000 });
  } catch (_) {
    await chosen.click({ timeout: 3000, force: true });
  }
  await page.waitForTimeout(1500);

  const finalLabel = await button.getAttribute('aria-label') || '';
  console.log(label + ' final aria-label:', finalLabel);
  if (!desiredButtonPattern.test(finalLabel)) {
    throw new Error(label + ' did not switch to expected value');
  }
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

    await page.waitForTimeout(5000);

    // Google sometimes ignores category/status/sort query parameters on initial load.
    // Enforce the desired view through the visible UI before reading rows.
    await ensureFilterByText(page, 'Alle Kategorien', 'Wirtschaft und Finanzen', /^Wirtschaft und Finanzen/);
    await selectMenuOption(page, /Trendstatus auswählen/i, /aktive/i, /Nur aktive Trends/i, 'Status');
    await selectMenuOption(page, /Sortierung auswählen|Sortierung/i, /Suchvolumen/i, /Nach Suchvolumen/i, 'Sortierung');

    await page.waitForTimeout(3000);

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
    const visibility = {};
    for (const label of requiredLabels) visibility[label] = await hasVisibleExactText(page, label);
    const missingLabels = requiredLabels.filter(x => !visibility[x]);

    const forbiddenDefaults = ['Alle Kategorien', 'Alle Trends', 'Nach Relevanz'];
    const presentDefaults = [];
    for (const label of forbiddenDefaults) {
      if (await hasVisibleExactText(page, label)) presentDefaults.push(label);
    }

    const rawRows = await page.locator('tr, [role="row"]').allInnerTexts();
    const seen = new Set();
    const rows = [];

    for (const raw of rawRows) {
      const text = clean(raw);
      if (!text || seen.has(text)) continue;
      seen.add(text);

      if (!/(?:^|\s)\d{1,3}(?:\.\d{3})*\+(?:\s|$)/.test(text)) continue;
      if (text.includes('Suchvolumen') && !text.includes('Aktiv')) continue;
      rows.push({ text });
    }

    const noTrends = /Keine Trends entsprechen derzeit diesen Filtern/i.test(bodyText);
    const urlOk = ['geo=DE','hours=4'].every(token => finalUrl.includes(token));

    const ok =
      missingLabels.length === 0 &&
      presentDefaults.length === 0 &&
      urlOk &&
      (rows.length > 0 || noTrends);

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
      if (presentDefaults.length) payload.validation_errors.push('Default filters still active: ' + presentDefaults.join(', '));
      if (!urlOk) payload.validation_errors.push('Final URL does not retain geo/time filters');
      if (!rows.length && !noTrends) payload.validation_errors.push('No trend rows found and no explicit empty-state message found');
    }

    fs.writeFileSync('latest.json', JSON.stringify(payload, null, 2) + '\n', 'utf8');
    console.log(`Wrote latest.json: ok=${ok}, rows=${rows.length}, final_url=${finalUrl}`);
    console.log('Validated view:', requiredLabels.map(x => visibility[x] ? x : 'MISSING:' + x).join(' | '));

    if (!ok) process.exitCode = 2;
  } finally {
    await browser.close();
  }
})().catch(err => {
  console.error(err);
  process.exit(1);
});
