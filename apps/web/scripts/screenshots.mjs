// Screenshots of every screen, desktop and mobile, light and dark, for review and the README.
//   node scripts/screenshots.mjs [baseUrl] [outDir]
// Env: SCHEME=light|dark|both (default both), ONLY=desktop|mobile, PAGES=overview,plan (filter),
//      DEMO=jaffna (another sample household), FORMAT=jpeg (smaller files for the README),
//      QUALITY=82 (jpeg), FULL=0 (viewport only, never the whole page)
// Needs the API serving the built app (see HOW_TO_RUN.md), or `npm run preview` with the API on :8080.

import { chromium } from "playwright";
import { existsSync, mkdirSync } from "node:fs";

// Use CHROMIUM_PATH if set, else a pre-installed Chromium if there is one, else Playwright's own
// (install it with `npx playwright install chromium`).
export function launchOptions() {
  const candidates = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"].filter(Boolean);
  const found = candidates.find((p) => existsSync(p));
  return found ? { executablePath: found } : {};
}

const base = process.argv[2] ?? "http://localhost:4173";
const out = process.argv[3] ?? "../../docs/screenshots";
mkdirSync(out, { recursive: true });

const browser = await chromium.launch(launchOptions());

const schemes = (process.env.SCHEME ?? "both") === "both" ? ["light", "dark"] : [process.env.SCHEME];
const viewports = [
  { name: "desktop", width: 1440, height: 900, mobile: false },
  { name: "mobile", width: 390, height: 844, mobile: true },
].filter((v) => !process.env.ONLY || v.name === process.env.ONLY);

const allPages = [
  { name: "01-landing", path: "/", full: true },
  { name: "02-overview", path: "{h}", full: true },
  { name: "03-found", path: "{h}/found", full: true },
  { name: "04-explore", path: "{h}/explore", full: false, setup: "explore" },
  { name: "05-calendar", path: "{h}/calendar", full: true },
  { name: "06-plan", path: "{h}/plan", full: true },
  { name: "07-practise", path: "{h}/practise", full: true },
  { name: "08-card", path: "{h}/card", full: true },
  { name: "09-capture", path: "{h}/capture", full: true, setup: "file" },
  { name: "10-review", path: "{h}/review", full: true },
  { name: "11-share", path: "{h}/share", full: true },
  { name: "12-settings", path: "{h}/settings", full: true },
  { name: "13-trace", path: "{h}/trace", full: true },
  { name: "14-evals", path: "/evals", full: true },
  { name: "15-start", path: "/start", full: true },
  { name: "16-tour", path: "{h}", full: false, setup: "tour" },
];
const demo = process.env.DEMO ?? "";
const tag = demo && demo !== "perera" ? `-${demo}` : "";
const pages = allPages.filter((p) => !process.env.PAGES || process.env.PAGES.split(",").some((x) => p.name.includes(x)));

for (const scheme of schemes) {
  for (const vp of viewports) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: vp.mobile ? 2 : 1,
      isMobile: vp.mobile,
      hasTouch: vp.mobile,
      reducedMotion: "reduce",
      colorScheme: scheme,
    });
    // the tour starts by itself on a first visit; screenshots show the pages, so mark it seen
    await context.addInitScript(() => {
      try {
        localStorage.setItem("iid.tour.seen", "1");
      } catch {
        /* ignore */
      }
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => console.error(`[${scheme} ${vp.name}] page error:`, e.message));
    page.on("console", (m) => m.type() === "error" && console.error(`[${scheme} ${vp.name}] console:`, m.text()));
    await page.goto(`${base}/demo${demo ? `/${demo}` : ""}`);
    await page.waitForURL(/\/h\/demo-/, { timeout: 20000 });
    const h = new URL(page.url()).pathname.replace(/\/$/, "");
    for (const p of pages) {
      await page.goto(base + p.path.replace("{h}", h));
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.addStyleTag({ content: "body{position:relative}body::before{position:absolute!important;inset:0!important}" });
      await page.waitForTimeout(900);
      if (p.setup === "explore") {
        // switch on one "what if" so the screenshot shows a change
        const named = page.locator(".explore-controls .choice", { hasText: process.env.EXPLORE ?? "Sunil" }).first();
        const chip = (await named.count()) ? named : page.locator(".explore-controls .choice").first();
        if (await chip.count()) await chip.click();
        await page.waitForTimeout(900);
      }
      if (p.setup === "file") {
        const tab = page.getByRole("tab", { name: /Photo or PDF/ });
        if (await tab.count()) await tab.click();
        await page.waitForTimeout(700);
      }
      if (p.setup === "tour") {
        const btn = page.getByRole("button", { name: "Take the tour" }).first();
        if (await btn.count()) await btn.click();
        await page.waitForTimeout(1500);
      }
      const suffix = scheme === "dark" ? "-dark" : "";
      const jpeg = process.env.FORMAT === "jpeg";
      const file = `${p.name}${tag}-${vp.name}${suffix}.${jpeg ? "jpg" : "png"}`;
      await page.screenshot({
        path: `${out}/${file}`,
        fullPage: p.full && !vp.mobile && process.env.FULL !== "0",
        ...(jpeg ? { type: "jpeg", quality: Number(process.env.QUALITY ?? 82) } : {}),
      });
      console.log("saved", file);
    }
    await context.close();
  }
}
await browser.close();
