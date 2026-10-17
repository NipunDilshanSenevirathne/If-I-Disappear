// Renders the social preview image (public/og.png, 1200x630) in the app's own type and
// colours: the two-tone headline, and a boarding pass for the sample family.
// Run: node scripts/render-og.mjs
import { chromium } from "playwright";
import { existsSync, readFileSync } from "node:fs";

// Use CHROMIUM_PATH if set, else a pre-installed Chromium if there is one, else Playwright's own
// (install it with `npx playwright install chromium`).
function launchOptions() {
  const candidates = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"].filter(Boolean);
  const found = candidates.find((p) => existsSync(p));
  return found ? { executablePath: found } : {};
}

const font = (p) => readFileSync(new URL(`../node_modules/${p}`, import.meta.url)).toString("base64");
const display = font("@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-opsz-normal.woff2");
const body = font("@fontsource-variable/figtree/files/figtree-latin-wght-normal.woff2");

const html = `<!doctype html><html><head><style>
@font-face{font-family:Display;src:url(data:font/woff2;base64,${display}) format("woff2");font-weight:200 800}
@font-face{font-family:Body;src:url(data:font/woff2;base64,${body}) format("woff2");font-weight:300 900}
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;overflow:hidden;position:relative;font-family:Body,sans-serif;color:#0e2a33;
  background:radial-gradient(700px 420px at 4% -6%,rgba(87,183,196,.34),transparent 64%),radial-gradient(640px 420px at 100% 0%,rgba(245,176,66,.32),transparent 62%),radial-gradient(800px 500px at 60% 120%,rgba(150,140,230,.18),transparent 60%),#eef2f3}
.brand{position:absolute;left:72px;top:58px;display:flex;align-items:center;gap:14px;font-family:Display;font-weight:700;font-size:30px;letter-spacing:-.02em}
.mark{width:52px;height:52px;border-radius:16px;background:linear-gradient(135deg,#14808f,#0a4a55);display:grid;place-items:center;box-shadow:0 10px 24px -12px #0a4a55}
h1{position:absolute;left:72px;top:138px;width:600px;font-family:Display;font-weight:700;font-size:68px;line-height:1;letter-spacing:-.04em;font-variation-settings:"opsz" 96}
h1 span{display:block}
h1 .second{color:#8ba1a7}
p{position:absolute;left:72px;top:446px;width:560px;font-size:23px;line-height:1.42;color:#3c565e}
.pass{position:absolute;right:64px;top:118px;width:410px;height:330px;display:grid;grid-template-columns:1fr 92px;border-radius:26px;overflow:hidden;
  background:linear-gradient(150deg,#fff7ea,#ffe8c4);color:#2a1c05;transform:rotate(-3deg);box-shadow:0 40px 70px -36px rgba(60,38,0,.6)}
.main{padding:24px 20px 20px 26px;display:grid;gap:12px;align-content:start}
.lab{display:block;font-size:13px;font-weight:700;opacity:.6}
.name{font-family:Display;font-weight:700;font-size:28px;letter-spacing:-.02em}
.route{display:flex;align-items:center;gap:10px;font-family:Display;font-weight:760;font-size:44px;line-height:1}
.route i{flex:1;border-top:3px dashed rgba(42,28,5,.25)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0;border-top:2px solid rgba(42,28,5,.18);border-bottom:2px solid rgba(42,28,5,.18)}
.grid b{display:block;font-size:17px}
.stub{border-left:3px dashed rgba(42,28,5,.22);padding:24px 14px;display:grid;align-content:space-between;background:rgba(255,232,196,.6)}
.stub b{font-family:Display;font-size:26px;display:block}
.code{height:70px;background:repeating-linear-gradient(90deg,#2a1c05 0 2px,transparent 2px 4px,#2a1c05 4px 5px,transparent 5px 8px,#2a1c05 8px 11px,transparent 11px 13px);opacity:.8}
.chip{position:absolute;right:250px;top:470px;display:flex;align-items:center;gap:12px;padding:12px 18px;border-radius:18px;background:rgba(255,255,255,.88);box-shadow:0 18px 40px -20px rgba(14,42,51,.4);font-size:17px;font-weight:600;color:#3c565e}
.chip b{font-family:Display;font-size:34px;color:#cc2e45}
.pill{position:absolute;right:64px;bottom:44px;display:flex;align-items:center;gap:10px;padding:10px 16px;border-radius:999px;background:#0f6c7a;color:#fff;font-weight:700;font-size:18px}
</style></head><body>
<div class="brand"><span class="mark"><svg width="32" height="32" viewBox="0 0 64 64"><path d="M32 12c6.5 8.6 10 13.7 10 19.4A10 10 0 0 1 22 31.4C22 25.7 25.5 20.6 32 12z" fill="#f3a712"/><path d="M32 24.5c2.6 3.6 4 5.9 4 8.2a4 4 0 0 1-8 0c0-2.3 1.4-4.6 4-8.2z" fill="#fff6e3"/><path d="M17 44c4 4.7 9 7 15 7s11-2.3 15-7" fill="none" stroke="#fff6e3" stroke-width="4" stroke-linecap="round"/></svg></span>If I Disappear</div>
<h1><span>Leaving home for months?</span><span class="second">Find what stops before you go.</span></h1>
<p>Voice notes and photos in. What breaks, date by date, the shortest plan to fix it, and practice for the person staying.</p>
<div class="pass"><div class="main">
  <div><span class="lab">Leaving</span><div class="name">Nirmala</div></div>
  <div class="route">CMB<i></i>NRT</div>
  <div class="grid"><div><span class="lab">Leaves</span><b>Sun, 1 Nov</b></div><div><span class="lab">Away</span><b>90 days</b></div><div><span class="lab">Back on</span><b>Fri, 29 Jan</b></div></div>
  <div><span class="lab">At home</span><b style="font-size:17px">Sunil, Achchi, Tharushi, Nimesh</b></div>
</div><div class="stub"><div><span class="lab">Ready</span><b>1/7</b></div><div><span class="lab">Plan</span><b>67 min</b></div><div class="code"></div></div></div>
<div class="chip"><b>5</b> would stop while she's away</div>
<div class="pill">Runs on the free Gemini tier</div>
</body></html>`;

const browser = await chromium.launch(launchOptions());
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.setContent(html, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: new URL("../public/og.png", import.meta.url).pathname });
await browser.close();
console.log("wrote public/og.png");
