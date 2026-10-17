// Accessibility check of every screen with axe-core (WCAG 2.2 A and AA rules), in light and
// dark mode, on a desktop and a phone viewport. Fails if any rule is violated.
//   node scripts/a11y.mjs [baseUrl]
// Env: SCHEME=light|dark|both (default both), ONLY=desktop|mobile, PAGES=overview,plan (filter)
// Needs the API serving the built app (see HOW_TO_RUN.md), like the smoke test.

import { chromium } from "playwright";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";

const require = createRequire(import.meta.url);
const axePath = require.resolve("axe-core/axe.min.js");
const axeVersion = require("axe-core/package.json").version;

const base = process.argv[2] ?? "http://localhost:8080";
const exe = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium"].filter(Boolean).find((p) => existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});

const schemes = (process.env.SCHEME ?? "both") === "both" ? ["light", "dark"] : [process.env.SCHEME];
const viewports = [
  { name: "desktop", width: 1280, height: 860, mobile: false },
  { name: "mobile", width: 390, height: 844, mobile: true },
].filter((v) => !process.env.ONLY || v.name === process.env.ONLY);

const allPages = [
  { name: "landing", path: "/" },
  { name: "overview", path: "{h}" },
  { name: "found", path: "{h}/found" },
  { name: "explore", path: "{h}/explore", setup: "explore" },
  { name: "calendar", path: "{h}/calendar" },
  { name: "plan", path: "{h}/plan" },
  { name: "practise", path: "{h}/practise" },
  { name: "card", path: "{h}/card" },
  { name: "capture", path: "{h}/capture" },
  { name: "review", path: "{h}/review" },
  { name: "share", path: "{h}/share" },
  { name: "settings", path: "{h}/settings" },
  { name: "trace", path: "{h}/trace" },
  { name: "evals", path: "/evals" },
  { name: "start", path: "/start" },
  { name: "tour", path: "{h}", setup: "tour" },
];
const pages = allPages.filter((p) => !process.env.PAGES || process.env.PAGES.split(",").includes(p.name));

const tags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
let checked = 0;
const failures = [];

for (const scheme of schemes) {
  for (const vp of viewports) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      isMobile: vp.mobile,
      hasTouch: vp.mobile,
      reducedMotion: "reduce",
      colorScheme: scheme,
      bypassCSP: true, // axe is injected as a script; the app's CSP rightly forbids that
    });
    await context.addInitScript(() => {
      try {
        localStorage.setItem("iid.tour.seen", "1");
      } catch {
        /* ignore */
      }
    });
    const page = await context.newPage();
    await page.goto(`${base}/demo`);
    await page.waitForURL(/\/h\/demo-/, { timeout: 20000 });
    const h = new URL(page.url()).pathname.replace(/\/$/, "");
    for (const p of pages) {
      await page.goto(base + p.path.replace("{h}", h));
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(700);
      if (p.setup === "explore") {
        const chip = page.locator(".explore-controls .choice", { hasText: "Sunil" }).first();
        if (await chip.count()) await chip.click();
        await page.waitForTimeout(700);
      }
      if (p.setup === "tour") {
        const btn = page.getByRole("button", { name: "Take the tour" }).first();
        if (await btn.count()) await btn.click();
        else await page.goto(`${base}${h}?tour=1`);
        await page.waitForTimeout(1200);
      }
      await page.addScriptTag({ path: axePath });
      const result = await page.evaluate(async (runTags) => {
        // eslint-disable-next-line no-undef
        const r = await axe.run(document, { runOnly: { type: "tag", values: runTags }, resultTypes: ["violations"] });
        return r.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          nodes: v.nodes.slice(0, 4).map((n) => `${n.target.join(" ")}: ${(n.failureSummary ?? "").split("\n").slice(1, 2).join(" ").trim()}`),
          count: v.nodes.length,
        }));
      }, tags);
      checked += 1;
      const label = `${p.name} (${scheme}, ${vp.name})`;
      if (result.length === 0) {
        console.log(`ok   ${label}`);
      } else {
        console.log(`FAIL ${label}`);
        for (const v of result) {
          console.log(`     ${v.impact ?? ""} ${v.id}: ${v.help} (${v.count})`);
          for (const n of v.nodes) console.log(`       - ${n}`);
        }
        failures.push({ label, result });
      }
    }
    await context.close();
  }
}
await browser.close();

console.log(`\naxe-core ${axeVersion}, rules: ${tags.join(", ")}`);
console.log(`${checked - failures.length} of ${checked} screens with no violations`);
process.exit(failures.length ? 1 : 0);
