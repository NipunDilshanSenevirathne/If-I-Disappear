// Live end-to-end test in a real browser, against a server that has a Gemini key.
//   node scripts/live-browser.mjs [baseUrl] [outDir]
// Env: VOICE_NOTE=note.wav      what the fake microphone says for a voice note (else skipped)
//      PRACTICE_VOICE=say.wav   what it says in spoken practice (else skipped)
//      SKIP_BASIC=1             only the two voice flows
// Needs the API in live mode (GEMINI_API_KEY set) serving the built app. Chromium's fake
// microphone plays the WAV files. If HTTPS_PROXY is set, the page reaches Gemini Live through it.
// Prints one line per flow and writes a screenshot of each to outDir. Exits 1 if any flow fails.

import { chromium } from "playwright";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";

const base = process.argv[2] ?? "http://localhost:8090";
const out = process.argv[3] ?? "live-out";
mkdirSync(out, { recursive: true });
const exe = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium"].filter(Boolean).find((p) => existsSync(p));
const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;

async function browserWith(wav) {
  const args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"];
  if (wav) args.push(`--use-file-for-fake-audio-capture=${wav}%noloop`);
  return chromium.launch({
    ...(exe ? { executablePath: exe } : {}),
    args,
    ...(proxy ? { proxy: { server: proxy, bypass: "localhost,127.0.0.1" } } : {}),
  });
}

async function pageIn(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ["microphone"] });
  await context.addInitScript(() => {
    try {
      localStorage.setItem("iid.tour.seen", "1");
    } catch {
      /* ignore */
    }
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !/Failed to load resource/.test(m.text())) problems.push(`console: ${m.text().slice(0, 300)}`);
  });
  return page;
}

const problems = [];
const results = [];
let n = 0;
async function flow(name, page, fn) {
  const t = Date.now();
  const before = problems.length;
  try {
    const note = await fn();
    const extra = problems.slice(before);
    if (extra.length) throw new Error(extra.join(" | "));
    results.push({ name, ok: true, seconds: (Date.now() - t) / 1000, note });
    console.log(`ok   ${name} (${((Date.now() - t) / 1000).toFixed(1)} s)${note ? `: ${note}` : ""}`);
  } catch (e) {
    results.push({ name, ok: false, seconds: (Date.now() - t) / 1000, error: String(e.message ?? e).slice(0, 500) });
    console.log(`FAIL ${name}: ${String(e.message ?? e).slice(0, 500)}`);
  }
  try {
    await page.screenshot({ path: `${out}/${String(++n).padStart(2, "0")}-${name}.png`, fullPage: false });
  } catch {
    /* page gone */
  }
}

async function openSample(page) {
  await page.goto(`${base}/demo`);
  await page.waitForURL(/\/h\/demo-/, { timeout: 30000 });
  await page.waitForLoadState("networkidle");
  return new URL(page.url()).pathname.replace(/\/$/, "");
}

async function waitOutcome(page, timeout = 240000) {
  // the capture page shows "Found N new facts…" or an error note when the job ends
  const done = page.locator(".outcome").first();
  await page.waitForFunction(
    () => /Found \d+ new fact|No new facts|facts you already had|couldn't be read|No AI model could/.test(document.body.innerText),
    null,
    { timeout },
  );
  return (await done.count()) ? (await done.innerText()).slice(0, 200) : "";
}

// ---------------------------------------------------------------- photo, review, check, typed practice, share
if (!process.env.SKIP_BASIC) {
  const browser = await browserWith(null);
  const page = await pageIn(browser);
  const h = await openSample(page);

  await flow("ai-pill-live", page, async () => {
    const pill = page.locator(".ai-pill").first();
    await pill.waitFor({ timeout: 15000 });
    const text = (await pill.innerText()).replace(/\s+/g, " ");
    if (/Offline demo/i.test(text)) throw new Error(`the server is in offline mode: ${text}`);
    return text;
  });

  await flow("capture-photo-sample", page, async () => {
    await page.goto(`${base}${h}/capture?mode=file`);
    await page.getByRole("tab", { name: /Photo or PDF/ }).click();
    const consent = page.locator("label.consent input[type=checkbox]");
    await consent.waitFor({ timeout: 15000 });
    await consent.check();
    await page.locator(".sample-tile", { hasText: "Electricity bill" }).first().click();
    await waitOutcome(page);
    const body = await page.locator("main").innerText();
    if (/couldn't be read|No AI model could/.test(body)) throw new Error(body.match(/(couldn't be read|No AI model could)[^\n]*/)?.[0]);
    const models = await page.locator(".job-steps .model-chip, .job-steps [class*=model]").allInnerTexts();
    return `${body.match(/Found[^.]*\./)?.[0] ?? ""} models: ${[...new Set(models.map((m) => m.trim()))].join(", ")}`;
  });

  await flow("review-facts-with-quotes", page, async () => {
    await page.goto(`${base}${h}/review`);
    await page.waitForLoadState("networkidle");
    const cards = await page.locator(".claim-card, .claim").count();
    const slips = await page.locator(".slip").count();
    if (!cards) throw new Error("no facts to review");
    return `${cards} facts on the page, ${slips} quote slips`;
  });

  await flow("check-again-with-ai", page, async () => {
    await page.goto(`${base}${h}/trace`);
    await page.getByRole("button", { name: "Check again with AI" }).click();
    await page.getByRole("button", { name: "Checking…" }).waitFor({ timeout: 10000 });
    await page.getByRole("button", { name: "Check again with AI" }).waitFor({ timeout: 240000 });
    await page.waitForTimeout(1500);
    const text = await page.locator("main").innerText();
    const m = text.match(/(Gemini [0-9.]+ [A-Za-z-]+|Gemma 4 \d+B)/g) ?? [];
    if (/AI review step failed|engine ran on its own/.test(text)) throw new Error("the AI review fell back to the engine alone");
    return `models on the page: ${[...new Set(m)].join(", ")}`;
  });

  await flow("practise-typed-graded-by-gemini", page, async () => {
    await page.goto(`${base}${h}/practise?r=r_electricity&p=sunil`);
    await page.waitForLoadState("networkidle");
    const typeTab = page.getByRole("radio", { name: /Type/ }).or(page.getByRole("tab", { name: /Type/ })).or(page.getByRole("button", { name: /^Type$/ }));
    if (await typeTab.count()) await typeTab.first().click();
    await page.locator("textarea").first().fill("I take the bill and the cash to the post office.");
    const check = async () => {
      await page.getByRole("button", { name: /Check my explanation/ }).click();
      await page.getByText("Checking the explanation…").waitFor({ timeout: 10000 }).catch(() => undefined);
      await page.getByText("Checking the explanation…").waitFor({ state: "detached", timeout: 120000 });
      await page.locator(".result").waitFor({ timeout: 10000 });
      return (await page.locator(".result-head").innerText()).replace(/\s+/g, " ");
    };
    const first = await check();
    await page
      .locator("textarea")
      .first()
      .fill("The paper bill comes every month and I pay it by the 10th. I take the bill and the cash to the post office, and I keep the receipt with the bill.");
    const second = await check();
    if (/offline checker/.test(first + second)) throw new Error(`graded offline: ${first} / ${second}`);
    return `vague: ${first} | complete: ${second}`;
  });

  await flow("handover-link-practice", page, async () => {
    await page.goto(`${base}${h}/share`);
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Make the link" }).click();
    const box = page.getByRole("textbox", { name: "Handover link" });
    await box.waitFor({ timeout: 15000 });
    const url = (await box.inputValue()).trim();
    if (!url.includes("/handover#")) throw new Error(`unexpected link: ${url.slice(0, 80)}`);
    const p2 = await pageIn(browser);
    await p2.goto(url);
    await p2.waitForLoadState("networkidle");
    // each task the link covers is a closed panel; open the gas refill (in Sunil's default link)
    await p2.locator(".handover-practice .disclose", { hasText: /gas/i }).first().click();
    const typeTab = p2.getByRole("radio", { name: /Type/ });
    await typeTab.first().click();
    await p2.locator("textarea").first().fill("When the gas runs low I call the gas shop from my phone and ask them for a refill.");
    await p2.getByRole("button", { name: /Check my explanation/ }).click();
    await p2.locator(".result").waitFor({ timeout: 120000 });
    const res = (await p2.locator(".result-head").innerText()).replace(/\s+/g, " ");
    await p2.screenshot({ path: `${out}/handover-page.png` });
    if (/offline checker/.test(res)) throw new Error(`graded offline: ${res}`);
    await p2.close();
    return res;
  });

  await flow("ai-allowance-after", page, async () => {
    await page.goto(`${base}${h}`);
    await page.locator(".ai-pill").first().click();
    await page.waitForTimeout(800);
    const text = (await page.locator(".ai-pop, [role=dialog]").first().innerText()).replace(/\s+/g, " ").slice(0, 400);
    return text;
  });
  await browser.close();
}

// ---------------------------------------------------------------- a recorded voice note
if (process.env.VOICE_NOTE) {
  const browser = await browserWith(process.env.VOICE_NOTE);
  const page = await pageIn(browser);
  const h = await openSample(page);
  await flow("voice-note-recorded-and-read", page, async () => {
    await page.goto(`${base}${h}/capture`);
    await page.waitForLoadState("networkidle");
    const consent = page.locator("label.consent input[type=checkbox]");
    await consent.waitFor({ timeout: 15000 }); // live mode asks before anything is sent to Gemini
    await consent.check();
    await page.getByRole("button", { name: "Start recording" }).click();
    await page.waitForTimeout(Number(process.env.VOICE_SECONDS ?? 33) * 1000);
    // the fake microphone stops when its file ends, and the page then adds what it recorded;
    // if it's still recording, press stop like a person would
    const stop = page.getByRole("button", { name: "Stop and add the voice note" });
    if (await stop.count()) await stop.click({ force: true });
    await waitOutcome(page);
    const body = await page.locator("main").innerText();
    if (/couldn't be read|No AI model could/.test(body)) throw new Error(body.match(/(couldn't be read|No AI model could)[^\n]*/)?.[0]);
    // the newest source is listed first, with the text Gemini wrote down
    const first = page.locator(".source-list .source-item").first();
    await first.locator("summary", { hasText: "What was said" }).click();
    const transcript = (await first.locator(".source-text").innerText().catch(() => "")).replace(/\s+/g, " ");
    if (!/clinic|Achchi|drawer|cupboard/i.test(transcript)) throw new Error(`the transcript doesn't look right: ${transcript.slice(0, 200)}`);
    if (/4419|four four one nine/i.test(transcript)) throw new Error("the PIN was not removed from the transcript");
    return `${body.match(/Found[^.]*\./)?.[0] ?? ""} transcript: ${transcript.slice(0, 220)}`;
  });
  await browser.close();
}

// ---------------------------------------------------------------- spoken practice with Gemini Live
if (process.env.PRACTICE_VOICE) {
  const browser = await browserWith(process.env.PRACTICE_VOICE);
  const page = await pageIn(browser);
  const h = await openSample(page);
  await flow("spoken-practice-gemini-live", page, async () => {
    await page.goto(`${base}${h}/practise?r=r_electricity&p=sunil`);
    await page.waitForLoadState("networkidle");
    const talk = page.getByRole("radio", { name: /Talk/ });
    if (await talk.count()) await talk.first().click();
    await page.getByRole("button", { name: "Start talking" }).click();
    await page.waitForFunction(() => /Listening…|practice partner is speaking/.test(document.body.innerText), null, { timeout: 30000 });
    await page.waitForTimeout(Number(process.env.PRACTICE_SECONDS ?? 32) * 1000);
    const bubbles = await page.locator(".bubble").allInnerTexts();
    await page.getByRole("button", { name: "Finish and check" }).click({ force: true }); // the orb pulses while live
    await page.locator(".result").waitFor({ timeout: 120000 });
    const res = (await page.locator(".result-head").innerText()).replace(/\s+/g, " ");
    writeFileSync(`${out}/spoken-practice-turns.txt`, bubbles.join("\n---\n"));
    const mine = bubbles.filter((b) => /^Sunil/.test(b)).join(" ").slice(0, 200);
    if (!mine) throw new Error(`nothing was heard from the learner; turns: ${bubbles.join(" | ").slice(0, 300)}`);
    return `${res} | heard: ${mine}`;
  });
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
writeFileSync(`${out}/results.json`, JSON.stringify(results, null, 2));
console.log(`\n${results.length - failed.length} of ${results.length} live browser flows passed`);
process.exit(failed.length ? 1 : 0);
