import { chromium } from "playwright";

const SOURCE_URL = "https://trends.google.de/trending?geo=DE&hl=de&hours=4&category=3&status=active&sort=search-volume";
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
    "Reject all",
    "Ok"
  ]) {
    const candidates = [
      page.getByRole("button", { name: label, exact: false }).first(),
      page.getByText(label, { exact: true }).first()
    ];
    for (const candidate of candidates) {
      if (await candidate.count()) {
        try {
          await candidate.click({ timeout: 3000 });
          await page.waitForTimeout(1000);
          return;
        } catch {}
      }
    }
  }
}

async function buttonExists(page, pattern) {
  return (await page.getByRole("button", { name: pattern }).count()) > 0;
}

async function clickInteractiveAncestor(page, locator) {
  const handle = await locator.elementHandle();
  if (!handle) return false;
  return await page.evaluate((el) => {
    let n = el;
    for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
      const role = n.getAttribute && n.getAttribute("role");
      const tag = n.tagName;
      const popup = n.getAttribute && n.getAttribute("aria-haspopup");
      const tabindex = n.getAttribute && n.getAttribute("tabindex");
      if (tag === "BUTTON" || role === "button" || role === "option" || role === "menuitem" || role === "combobox" || popup || tabindex === "0") {
        n.click();
        return true;
      }
    }
    el.click();
    return true;
  }, handle);
}

async function exactTextExists(page, pattern) {
  const text = await page.locator("body").innerText();
  const lines = text.replace(/\r/g, "").split("\n").map(x => x.trim()).filter(Boolean);
  return lines.some(line => pattern.test(line));
}

async function setFilter(page, { selected, trigger, optionTexts, toggle = false }) {
  if ((await exactTextExists(page, selected)) && !(await exactTextExists(page, trigger))) return;

  let target = page.getByRole("button", { name: trigger }).first();
  if (!(await target.count())) target = page.getByText(trigger, { exact: true }).first();
  if (!(await target.count())) throw new Error(`Filter control not found: ${trigger}`);

  await clickInteractiveAncestor(page, target);
  await page.waitForTimeout(1000);

  let exactOption = null;
  let matchedOption = null;
  for (const optionText of optionTexts) {
    const candidate = page.getByText(optionText, { exact: true }).last();
    if (await candidate.count()) {
      exactOption = candidate;
      matchedOption = optionText;
      break;
    }
  }

  if (!exactOption) {
    const visible = (await page.locator("body").innerText()).replace(/\r/g, "").split("\n").map(x => x.trim()).filter(Boolean).slice(0, 120).join(" | ");
    throw new Error(`Filter option not found: ${optionTexts.join(" / ")}. Visible text: ${visible}`);
  }

  if (toggle) {
    // "Nur aktive Trends anzeigen" is a switch. Find the nearest switch/checkbox
    // around the label and turn it on only when it is currently off.
    const handle = await exactOption.elementHandle();
    const toggled = await page.evaluate((el) => {
      let root = el;
      for (let i = 0; i < 6 && root; i++, root = root.parentElement) {
        const candidates = root.querySelectorAll('[role="switch"], input[type="checkbox"], [aria-checked]');
        for (const sw of candidates) {
          const checked = sw.getAttribute("aria-checked");
          const inputChecked = ("checked" in sw) ? sw.checked : null;
          const isOn = checked === "true" || inputChecked === true;
          if (!isOn) sw.click();
          return true;
        }
      }
      return false;
    }, handle);
    if (!toggled) {
      throw new Error(`Switch control not found near: ${matchedOption}`);
    }
  } else {
    await clickInteractiveAncestor(page, exactOption);
  }

  await page.waitForTimeout(1500);

  if (!((await exactTextExists(page, selected)) && !(await exactTextExists(page, trigger)))) {
    const visible = (await page.locator("body").innerText()).replace(/\r/g, "").split("\n").map(x => x.trim()).filter(Boolean).slice(0, 120).join(" | ");
    throw new Error(`Filter was not applied: ${matchedOption}. Visible text: ${visible}`);
  }
}

async function enforceTargetView(page) {
  // Exact labels taken from the current German Google Trends UI.
  await setFilter(page, {
    selected: /^Wirtschaft und Finanzen$/,
    trigger: /^Alle Kategorien$/,
    optionTexts: ["Wirtschaft und Finanzen"]
  });

  await setFilter(page, {
    selected: /^Nur aktive Trends$/,
    trigger: /^Alle Trends$/,
    optionTexts: ["Nur aktive Trends anzeigen", "Nur aktive Trends"],
    toggle: true
  });

  await setFilter(page, {
    selected: /^Nach Suchvolumen$/,
    trigger: /^Nach Relevanz$/,
    optionTexts: ["Suchvolumen"]
  });

  const missing = [];
  if (!(await exactTextExists(page, /^Deutschland$/))) missing.push("Deutschland");
  if (!(await exactTextExists(page, /^Letzte 4 Stunden$/))) missing.push("Letzte 4 Stunden");
  if (!(await exactTextExists(page, /^Wirtschaft und Finanzen$/))) missing.push("Wirtschaft und Finanzen");
  if (!(await exactTextExists(page, /^Nur aktive Trends$/))) missing.push("Nur aktive Trends");
  if (!(await exactTextExists(page, /^Nach Suchvolumen$/))) missing.push("Nach Suchvolumen");

  if (missing.length) {
    throw new Error("Zielansicht nicht bestätigt: " + missing.join(", "));
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

const browser = await chromium.launch({ headless: false, channel: "chrome" });
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
