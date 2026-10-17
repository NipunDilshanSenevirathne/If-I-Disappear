// End-to-end smoke test in a real browser: walks through every main flow of the app
// against a running server and fails on any page error or broken step.
//   node scripts/smoke.mjs [baseUrl] [outDir]
// Needs the API serving the built app (make build, then the API with STATIC_DIR set), in
// offline (AI_MODE=fixture) or live mode. Screenshots of each step go to outDir.

import { chromium } from "playwright";
import { existsSync, mkdirSync } from "node:fs";

const base = process.argv[2] ?? "http://localhost:8080";
const out = process.argv[3] ?? "smoke-out";
mkdirSync(out, { recursive: true });
const exe = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium"].filter(Boolean).find((p) => existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const context = await browser.newContext({ viewport: { width: 1280, height: 860 }, reducedMotion: "reduce", acceptDownloads: true });
await context.addInitScript(() => {
  try {
    localStorage.setItem("iid.tour.seen", "1");
  } catch {
    /* ignore */
  }
});
const page = await context.newPage();
const problems = [];
page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error" && !/Failed to load resource/.test(m.text())) problems.push(`console: ${m.text()}`);
});
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.url()}`);
});

let n = 0;
async function step(name, fn) {
  const t = Date.now();
  try {
    await fn();
    await page.screenshot({ path: `${out}/${String(++n).padStart(2, "0")}-${name}.png` });
    console.log(`ok   ${name} (${Date.now() - t} ms)`);
  } catch (e) {
    problems.push(`${name}: ${e.message.split("\n")[0]}`);
    await page.screenshot({ path: `${out}/${String(++n).padStart(2, "0")}-${name}-FAILED.png` }).catch(() => undefined);
    console.log(`FAIL ${name}: ${e.message.split("\n")[0]}`);
  }
}
const toast = () => page.locator(".toast").last();

let h = "";
await step("landing", async () => {
  await page.goto(base + "/");
  await page.getByRole("heading", { name: /Leaving home for months/ }).waitFor();
  await page.locator(".hero-board").waitFor();
});

await step("open-sample", async () => {
  await page.goto(base + "/demo");
  await page.waitForURL(/\/h\/demo-/, { timeout: 20000 });
  h = new URL(page.url()).pathname.replace(/\/$/, "");
  await page.locator(".kpis").waitFor();
});

await step("tour", async () => {
  await page.getByRole("button", { name: "Take the tour" }).first().click();
  await page.locator(".tour-card").waitFor();
  for (let i = 0; i < 4; i++) {
    await page.locator(".tour-card").getByRole("button", { name: /Next/ }).click();
    await page.waitForTimeout(500);
  }
  await page.locator(".tour-card").getByRole("button", { name: "Skip the tour" }).click();
  await page.locator(".tour-card").waitFor({ state: "detached" });
});

await step("week-chart-keyboard", async () => {
  await page.goto(base + h);
  const bar = page.locator(".bar-hit").first();
  await bar.focus();
  await page.keyboard.press("ArrowRight");
  await page.locator(".chart-caption", { hasText: "Week of" }).waitFor();
});

await step("finding-answer", async () => {
  await page.goto(base + h + "/found");
  await page.locator(".finding").first().waitFor();
  const yes = page.locator(".answer").getByRole("button", { name: "Yes" }).first();
  await yes.click();
  await toast().waitFor();
});

await step("explore", async () => {
  await page.goto(base + h + "/explore");
  await page.locator(".explore-controls .choice", { hasText: "Sunil" }).first().click();
  await page.locator(".compare-big.worse").waitFor({ timeout: 10000 });
});

await step("plan-mark-done", async () => {
  await page.goto(base + h + "/plan");
  await page.getByRole("button", { name: "Mark done" }).first().click();
  await page.getByRole("button", { name: "Record it" }).click();
  await toast().waitFor();
});

await step("practise-typed", async () => {
  await page.goto(base + h + "/practise");
  await page.locator(".session textarea").waitFor();
  await page.waitForTimeout(800);
  await page.locator(".session textarea").fill("I take the bill and the cash to the post office before the 10th and keep the receipt with the bill.");
  await page.getByRole("button", { name: "Check my explanation" }).click();
  await page.locator(".result").waitFor({ timeout: 20000 });
});

await step("card", async () => {
  await page.goto(base + h + "/card");
  await page.locator(".ccard-item").first().waitFor();
});

let handover = "";
await step("share-link", async () => {
  await page.goto(base + h + "/share");
  await page.getByRole("button", { name: "Make the link" }).click();
  const input = page.getByLabel("Handover link", { exact: true });
  await input.waitFor();
  handover = await input.inputValue();
  if (!handover.includes("/handover#")) throw new Error(`unexpected link ${handover}`);
});

await step("handover-page", async () => {
  const p2 = await context.newPage();
  p2.on("pageerror", (e) => problems.push(`handover page error: ${e.message}`));
  await p2.goto(handover);
  await p2.getByRole("heading", { name: /Here's what/ }).waitFor();
  await p2.locator(".ccard").waitFor();
  await p2.screenshot({ path: `${out}/${String(++n).padStart(2, "0")}-handover-view.png`, fullPage: true });
  await p2.close();
});

await step("share-revoke", async () => {
  await page.getByRole("button", { name: "Switch off" }).first().click();
  await toast().waitFor();
});

await step("capture-sample", async () => {
  await page.goto(base + h + "/capture");
  await page.getByRole("tab", { name: /Photo or PDF/ }).click();
  await page.locator(".sample-tile").first().click();
  await page.locator(".outcome").waitFor({ timeout: 60000 });
});

await step("capture-by-hand", async () => {
  await page.getByRole("tab", { name: /By hand/ }).click();
  await page.getByLabel("What has to be done?").fill("Pay the water bill");
  await page.getByRole("button", { name: "Add it" }).click();
  await toast().waitFor();
});

await step("review", async () => {
  await page.goto(base + h + "/review");
  await page.locator(".review-group").first().waitFor();
});

await step("settings-days", async () => {
  await page.goto(base + h + "/settings");
  const days = page.getByLabel("Days away").first();
  await days.fill("60");
  await page.getByRole("button", { name: "Save changes" }).click();
  await toast().waitFor();
});

await step("settings-scope", async () => {
  await page.getByRole("switch").first().click();
  await page.locator(".scope-list li.off").first().waitFor();
  await page.getByRole("switch").first().click();
});

await step("trace-check-again", async () => {
  await page.goto(base + h + "/trace");
  await page.getByRole("button", { name: "Check again with AI" }).click();
  await page.locator(".job-steps li").nth(3).waitFor({ timeout: 60000 });
});

await step("evals", async () => {
  await page.goto(base + "/evals");
  await page.locator(".metric").first().waitFor();
});

await step("start-household", async () => {
  await page.goto(base + "/start");
  await page.getByLabel("Name of the person leaving").fill("Amali");
  await page.getByLabel("Name", { exact: true }).fill("Ruwan");
  await page.getByRole("button", { name: /Create the household/ }).click();
  await page.waitForURL(/\/capture$/, { timeout: 20000 });
});

await step("new-household-overview", async () => {
  await page.goto(page.url().replace(/\/capture$/, ""));
  await page.locator(".start-steps").waitFor();
  await page.getByRole("heading", { name: /while Amali is away/ }).waitFor();
  await page.locator(".pass-home", { hasText: "Ruwan" }).waitFor();
});

await step("theme-dark", async () => {
  await page.getByRole("radio", { name: "Dark" }).first().click();
  const t = await page.evaluate(() => document.documentElement.dataset.theme);
  if (t !== "dark") throw new Error(`theme is ${t}`);
});

await browser.close();
if (problems.length) {
  console.error(`\n${problems.length} problem(s):\n- ${problems.join("\n- ")}`);
  process.exit(1);
}
console.log("\nAll smoke steps passed.");
