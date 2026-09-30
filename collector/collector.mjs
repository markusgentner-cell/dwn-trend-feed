import { chromium } from "playwright";

const SOURCE_URL = "https://trends.google.de/trending?geo=DE&hl=de&hours=4&sort=search-volume&category=3&status=active";
const REPO = "markusgentner-cell/dwn-trend-feed";
const FILE_PATH = "latest.json";
const TOKEN = process.env.DWN_GITHUB_TOKEN;

if (!TOKEN) {
  console.error("DWN_GITHUB_TOKEN is not set.");
  process.exit(2);
}

async function github(path, options = {}) {
  const r = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...options,
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(options.headers || {})
    }
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}: ${await r.text()}`);
  return r.json();
}

async function updateLatest(payload) {
  const current = await github(`/contents/${FILE_PATH}`);
  const body = {
    message: "Update Google Trends snapshot",
    content: Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8").toString("base64"),
    sha: current.sha
  };
  await github(`/contents/${FILE_PATH}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
}

async function dismissConsent(page) {
  for (const label of [
    "Alle akzeptieren",
    "Alles akzeptieren",
    "Accept all",
    "Alle ablehnen",
    "Reject all"
  ]) {
    const b = page.getByRole("button", { name: label, exact: false });
    if (await b.count()) {
      try {
        await b.first().click({ timeout: 3000 });
        await page.waitForTimeout(1500);
      } catch {}
      break;
    }
  }
}

async function chooseFilter(page, currentLabel, optionPattern) {
  const trigger = page.getByText(currentLabel, { exact: true }).first();
  if (!(await trigger.count())) {
    throw new Error(`Filter trigger not found: ${currentLabel}`);
  }

  await trigger.click({ timeout: 10000 });
  await page.waitForTimeout(500);

  const roleCandidates = [
    page.getByRole("option", { name: optionPattern }).first(),
    page.getByRole("menuitem", { name: optionPattern }).first(),
    page.getByText(optionPattern).first()
  ];

  for (const candidate of roleCandidates) {
    if (await candidate.count()) {
      try {
        await candidate.click({ timeout: 5000 });
        await page.waitForTimeout(1200);
        return;
      } catch {}
    }
  }

  throw new Error(`Filter option not found for: ${optionPattern}`);
}

async function enforceTargetView(page) {
  let body = await page.locator("body").innerText();

  if (body.includes("Alle Kategorien")) {
    await chooseFilter(page, "Alle Kategorien", /Wirtschaft/i);
  }

  body = await page.locator("body").innerText();
  if (body.includes("Alle Trends")) {
    await chooseFilter(page, "Alle Trends", /^Aktiv$|aktive Trends/i);
  }

  body = await page.locator("body").innerText();
  if (body.includes("Nach Relevanz")) {
    await chooseFilter(page, "Nach Relevanz", /Suchvolumen/i);
  }

  await page.waitForTimeout(2500);

  body = await page.locator("body").innerText();
  const problems = [];
  if (body.includes("Alle Kategorien")) problems.push("Kategorie steht noch auf Alle Kategorien");
  if (body.includes("Alle Trends")) problems.push("Status steht noch auf Alle Trends");
  if (body.includes("Nach Relevanz")) problems.push("Sortierung steht noch auf Nach Relevanz");

  if (problems.length) {
    throw new Error("Zielansicht konnte nicht gesetzt werden: " + problems.join("; "));
  }
}

async function extractVisibleData(page) {
  // First try semantic table/grid rows. Google may render the list as a table,
  // ARIA grid, or div-based rows depending on the current UI version.
  const selectors = [
    "table tbody tr",
    '[role="row"]',
    '[role="listitem"]'
  ];

  const seen = new Set();
  const rows = [];

  for (const selector of selectors) {
    const loc = page.locator(selector);
    const count = Math.min(await loc.count(), 250);

    for (let i = 0; i < count; i++) {
      const el = loc.nth(i);
      let text = "";
      try {
        text = (await el.innerText({ timeout: 2000 }))
          .replace(/\s+/g, " ")
          .trim();
      } catch {}

      if (!text || text.length < 3 || seen.has(text)) continue;
      seen.add(text);

      let hrefs = [];
      try {
        hrefs = await el.locator("a").evaluateAll(as =>
          as.map(a => ({ text: (a.innerText || "").trim(), href: a.href }))
            .filter(x => x.href)
        );
      } catch {}

      rows.push({ text, links: hrefs });
    }
  }

  // Always keep the visible page text as a fallback/debug source. This lets us
  // adapt the parser if Google changes its DOM again without needing a new
  // manual browser session.
  let bodyText = "";
  try {
    bodyText = (await page.locator("body").innerText({ timeout: 10000 }))
      .replace(/\r/g, "")
      .trim();
  } catch {}

  // Keep only relevant links from the page to reduce noise.
  let links = [];
  try {
    links = await page.locator("a").evaluateAll(as =>
      as.map(a => ({
        text: (a.innerText || "").replace(/\s+/g, " ").trim(),
        href: a.href
      }))
      .filter(x =>
        x.href &&
        (
          x.href.includes("trends.google") ||
          x.href.includes("/trending") ||
          x.href.includes("/explore")
        )
      )
    );
  } catch {}

  // Deduplicate links.
  const linkMap = new Map();
  for (const link of links) {
    const key = link.href + "|" + link.text;
    if (!linkMap.has(key)) linkMap.set(key, link);
  }

  return {
    title: await page.title(),
    url: page.url(),
    rows,
    links: [...linkMap.values()].slice(0, 500),
    body_text: bodyText.slice(0, 150000)
  };
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  locale: "de-DE",
  viewport: { width: 1600, height: 1200 }
});

try {
  await page.goto(SOURCE_URL, {
    waitUntil: "domcontentloaded",
    timeout: 90000
  });

  await dismissConsent(page);

  // Give the client-side trends list time to render.
  await page.waitForTimeout(5000);

  // Google currently ignores some filter query parameters. Set the
  // editorial target view explicitly in the UI and verify it before reading.
  await enforceTargetView(page);

  const extracted = await extractVisibleData(page);

  if (
    extracted.rows.length === 0 &&
    (!extracted.body_text || extracted.body_text.length < 100)
  ) {
    throw new Error("Google Trends page loaded, but no usable trend data was visible.");
  }

  const payload = {
    ok: true,
    status: "fresh",
    captured_at: new Date().toISOString(),
    source_url: SOURCE_URL,
    page_title: extracted.title,
    final_url: extracted.url,
    rows: extracted.rows,
    links: extracted.links,
    body_text: extracted.body_text
  };

  await updateLatest(payload);
  console.log(
    `OK ${payload.captured_at} (${payload.rows.length} rows, ${payload.body_text.length} text chars)`
  );
} catch (err) {
  const payload = {
    ok: false,
    status: "collector_error",
    captured_at: new Date().toISOString(),
    source_url: SOURCE_URL,
    error: String(err)
  };
  try { await updateLatest(payload); } catch {}
  console.error(err);
  process.exitCode = 1;
} finally {
  await browser.close();
}
