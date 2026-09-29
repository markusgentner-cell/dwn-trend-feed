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

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ locale: "de-DE" });

try {
  await page.goto(SOURCE_URL, { waitUntil: "domcontentloaded", timeout: 90000 });

  // Cookie dialogs are regional and may or may not be present.
  for (const label of ["Alle akzeptieren", "Alles akzeptieren", "Accept all", "Alle ablehnen", "Reject all"]) {
    const b = page.getByRole("button", { name: label, exact: false });
    if (await b.count()) {
      try { await b.first().click({ timeout: 3000 }); } catch {}
      break;
    }
  }

  await page.waitForTimeout(5000);

  // Prefer Google's own CSV export. The UI label can vary slightly by locale.
  const downloadPromise = page.waitForEvent("download", { timeout: 20000 });
  const exportButton = page.getByRole("button", { name: /Export|Herunterladen|Download/i }).first();
  await exportButton.click({ timeout: 15000 });

  // Some versions open a small menu with a CSV item.
  const csvItem = page.getByText(/CSV/i).first();
  if (await csvItem.count()) {
    try { await csvItem.click({ timeout: 5000 }); } catch {}
  }

  const download = await downloadPromise;
  const file = await download.createReadStream();
  let csv = "";
  for await (const chunk of file) csv += chunk.toString("utf8");

  if (!csv || csv.length < 20) throw new Error("Google Trends export was empty.");

  const payload = {
    ok: true,
    status: "fresh",
    captured_at: new Date().toISOString(),
    source_url: SOURCE_URL,
    csv
  };

  await updateLatest(payload);
  console.log(`OK ${payload.captured_at} (${csv.length} bytes)`);
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
