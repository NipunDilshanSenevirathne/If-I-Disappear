// Render the demo household's SAMPLE documents (photos, screenshots, a PDF)
// from exactly the text their claims quote.
//
//   cd services/api && python -m app.tools.export_sources perera > /tmp/sources.json
//   cd apps/web && node scripts/render-samples.mjs /tmp/sources.json ../../services/api/fixtures/households/perera/files
//
// Every image says SAMPLE. Names, numbers and organisations are fictional.

import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// Use CHROMIUM_PATH if set, else a pre-installed Chromium if there is one, else Playwright's own
// (install it with `npx playwright install chromium`).
function launchOptions() {
  const candidates = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"].filter(Boolean);
  const found = candidates.find((p) => existsSync(p));
  return found ? { executablePath: found } : {};
}

const [, , jsonPath, outDir] = process.argv;
if (!jsonPath || !outDir) {
  console.error("usage: node scripts/render-samples.mjs sources.json outDir");
  process.exit(1);
}
const { sources } = JSON.parse(readFileSync(jsonPath, "utf8"));
mkdirSync(outDir, { recursive: true });

// fonts are inlined as data URLs: pages set with setContent can't load file:// fonts
const nm = (p) => `data:font/woff2;base64,${readFileSync(resolve("node_modules", p)).toString("base64")}`;
const FONTS = `
@font-face { font-family: "Noto Sans"; src: url("${nm("@fontsource-variable/noto-sans/files/noto-sans-latin-wght-normal.woff2")}") format("woff2-variations"); font-weight: 100 900; }
@font-face { font-family: "Caveat"; src: url("${nm("@fontsource/caveat/files/caveat-latin-500-normal.woff2")}") format("woff2"); }
@font-face { font-family: "Fraunces"; src: url("${nm("@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2")}") format("woff2-variations"); font-weight: 100 900; }
`;

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function rows(lines) {
  return lines
    .map((l) => {
      const m = /^([A-Z][A-Za-z .'()-]{1,28}):\s(.+)$/.exec(l);
      if (m && m[1].split(" ").length <= 4) return `<div class="row"><span class="k">${esc(m[1])}</span><span class="v">${esc(m[2])}</span></div>`;
      return `<p>${esc(l)}</p>`;
    })
    .join("\n");
}

const BASE = `
${FONTS}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { font-family: "Noto Sans", sans-serif; }
.table { width: 1200px; height: 900px; display: grid; place-items: center; background:
  radial-gradient(700px 500px at 30% 20%, rgba(255,230,190,.35), transparent 70%),
  repeating-linear-gradient(95deg, #6b4a32 0 18px, #71503a 18px 30px, #664530 30px 52px); }
.paper { position: relative; width: 760px; background: #fbf8f1; color: #1d2a2f; padding: 44px 52px 40px;
  box-shadow: 0 30px 60px rgba(0,0,0,.45), 0 2px 0 rgba(0,0,0,.08); transform: rotate(-1.4deg); }
.paper::after { content: ""; position: absolute; inset: 0; background:
  radial-gradient(400px 300px at 80% 10%, rgba(255,255,255,.35), transparent 70%),
  repeating-radial-gradient(circle at 20% 30%, rgba(0,0,0,.012) 0 2px, transparent 2px 4px); pointer-events: none; }
.brand { font-weight: 800; letter-spacing: .04em; font-size: 30px; }
.title { font-size: 21px; margin-top: 4px; color: #44545a; }
.row { display: flex; justify-content: space-between; gap: 24px; padding: 9px 0; border-bottom: 1px solid #e2dccd; font-size: 20px; }
.row .k { color: #5b6a70; }
.row .v { font-weight: 700; text-align: right; }
p { font-size: 19px; line-height: 1.45; margin: 12px 0 0; }
.wm { position: absolute; inset: 0; display: grid; place-items: center; pointer-events: none; }
.wm span { font: 900 120px "Noto Sans"; color: rgba(194, 57, 77, .12); transform: rotate(-24deg); letter-spacing: .1em; }
`;

function documentPhoto({ accent, band, lines, rotate = -1.4, extraCss = "" }) {
  const [brand, title, ...rest] = lines;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${BASE}
  .paper { transform: rotate(${rotate}deg); }
  .head { display: flex; align-items: center; gap: 16px; border-bottom: 4px solid ${accent}; padding-bottom: 14px; margin-bottom: 14px; }
  .logo { width: 54px; height: 54px; border-radius: 12px; background: ${accent}; display: grid; place-items: center; color: #fff; font: 800 26px "Noto Sans"; }
  .band { background: ${band}; }
  ${extraCss}
  </style></head><body><div class="table"><div class="paper">
    <div class="head"><div class="logo">${esc(brand.slice(0, 1))}</div><div><div class="brand" style="color:${accent}">${esc(brand)}</div><div class="title">${esc(title)}</div></div></div>
    ${rows(rest)}
    <div class="wm"><span>SAMPLE</span></div>
  </div></div></body></html>`;
}

function clinicBook(lines) {
  const [brand, title, ...rest] = lines;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${BASE}
  .paper { background: #2f6b4f; color: #f4f1e6; width: 640px; padding: 56px 50px; border-radius: 6px 14px 14px 6px; transform: rotate(1.2deg);
    box-shadow: inset 14px 0 0 rgba(0,0,0,.18), 0 30px 60px rgba(0,0,0,.45); }
  .brand { color: #f4f1e6; font-size: 24px; text-align: center; }
  .title { color: #f4f1e6; text-align: center; font: 600 40px "Fraunces"; margin: 10px 0 26px; }
  .label { background: #f4f1e6; color: #1d2a2f; border-radius: 10px; padding: 18px 22px; }
  .row { border-bottom-color: #d6cfbd; }
  p { color: #1d2a2f; }
  .wm span { color: rgba(255,255,255,.14); }
  </style></head><body><div class="table"><div class="paper">
    <div class="brand">${esc(brand)}</div><div class="title">${esc(title)}</div>
    <div class="label">${rows(rest)}</div>
    <div class="wm"><span>SAMPLE</span></div>
  </div></div></body></html>`;
}

function handwritten(lines) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${BASE}
  .paper { width: 620px; padding: 40px 44px 46px 70px; transform: rotate(-2.4deg); background:
     repeating-linear-gradient(180deg, transparent 0 47px, #b9cfe4 47px 48px), #fffdf6;
     box-shadow: 0 24px 50px rgba(0,0,0,.45); }
  .paper::before { content: ""; position: absolute; left: 52px; top: 0; bottom: 0; width: 2px; background: #e8a0a8; }
  .hand { font: 500 40px/48px "Caveat", cursive; color: #1f3a8a; white-space: pre-line; }
  .sample { position: absolute; right: 18px; top: 14px; font: 800 14px "Noto Sans"; color: #c2394d; border: 2px solid #c2394d; padding: 2px 8px; border-radius: 6px; transform: rotate(6deg); }
  </style></head><body><div class="table"><div class="paper"><div class="sample">SAMPLE</div><div class="hand">${lines.map(esc).join("\n")}</div></div></div></body></html>`;
}

function drawerPhoto() {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${BASE}
  .scene { width: 1200px; height: 900px; background: linear-gradient(180deg, #8d969b, #6f797e); display: grid; place-items: center; }
  </style></head><body><div class="scene">
  <svg width="1000" height="760" viewBox="0 0 1000 760" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="steel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c9d0d4"/><stop offset="1" stop-color="#9aa4aa"/></linearGradient>
      <linearGradient id="inside" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5e676c"/><stop offset="1" stop-color="#7d878c"/></linearGradient>
    </defs>
    <rect x="40" y="20" width="920" height="720" rx="10" fill="url(#steel)"/>
    <rect x="70" y="60" width="860" height="70" rx="6" fill="#b3bbc0"/>
    <polygon points="90,150 910,150 960,560 40,560" fill="url(#inside)"/>
    <rect x="40" y="560" width="920" height="150" rx="8" fill="url(#steel)" stroke="#8a9398"/>
    <rect x="420" y="610" width="160" height="26" rx="13" fill="#7c868b"/>
    <g transform="rotate(-6 360 360)">
      <rect x="210" y="250" width="300" height="230" rx="8" fill="#2f6b4f"/>
      <rect x="226" y="250" width="12" height="230" fill="#25553f"/>
      <rect x="262" y="320" width="210" height="70" rx="6" fill="#f4f1e6"/>
      <text x="367" y="362" text-anchor="middle" font-family="Fraunces" font-size="30" fill="#1d2a2f">Diabetic clinic</text>
    </g>
    <g transform="rotate(4 690 380)">
      <rect x="560" y="260" width="260" height="210" fill="#fbf8f1"/>
      <line x1="560" y1="365" x2="820" y2="365" stroke="#d8d1c2" stroke-width="2"/>
      <text x="690" y="305" text-anchor="middle" font-family="Noto Sans" font-weight="700" font-size="22" fill="#1d2a2f">Medicine list - Kamala</text>
      <g stroke="#9aa5ab" stroke-width="3"><line x1="590" y1="330" x2="790" y2="330"/><line x1="590" y1="395" x2="770" y2="395"/><line x1="590" y1="425" x2="780" y2="425"/></g>
    </g>
    <g transform="rotate(-8 880 90)"><rect x="820" y="70" width="120" height="40" rx="6" fill="#fff" stroke="#c2394d" stroke-width="3"/><text x="880" y="98" text-anchor="middle" font-family="Noto Sans" font-weight="800" font-size="20" fill="#c2394d">SAMPLE</text></g>
  </svg></div></body></html>`;
}

function phone(inner, css = "") {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${BASE}
  .scene { width: 900px; height: 1500px; display: grid; place-items: center; background: #dfe5e6; }
  .phone { width: 600px; height: 1260px; border-radius: 64px; background: #10181b; padding: 22px; box-shadow: 0 40px 80px rgba(0,0,0,.35); }
  .screen { width: 100%; height: 100%; border-radius: 46px; background: #f6f7f8; overflow: hidden; position: relative; }
  .status { display: flex; justify-content: space-between; padding: 22px 34px 10px; font: 600 22px "Noto Sans"; color: #111; }
  .sample { position: absolute; right: 26px; bottom: 30px; font: 800 18px "Noto Sans"; color: #c2394d; border: 2px solid #c2394d; padding: 3px 10px; border-radius: 8px; }
  ${css}
  </style></head><body><div class="scene"><div class="phone"><div class="screen">
    <div class="status"><span>9:41</span><span>●●● 4G</span></div>
    ${inner}
    <div class="sample">SAMPLE</div>
  </div></div></div></body></html>`;
}

function bankScreen(lines) {
  const [brand, title, ...rest] = lines;
  return phone(
    `<div class="app"><div class="bar">${esc(brand)}</div><h1>${esc(title)}</h1><div class="card">${rows(rest)}</div></div>`,
    `.app { padding: 0 0 20px; } .bar { background: #1f4e8c; color: #fff; padding: 26px 34px; font: 800 26px "Noto Sans"; }
     h1 { font: 700 34px "Noto Sans"; margin: 30px 34px 18px; } .card { background: #fff; margin: 0 26px; border-radius: 22px; padding: 10px 26px 24px; box-shadow: 0 6px 20px rgba(0,0,0,.06); }
     .row { font-size: 21px; flex-direction: column; gap: 4px; } .row .v { text-align: left; }`,
  );
}

function contactsScreen(lines) {
  const [title, ...rest] = lines;
  const items = rest
    .map((l) => {
      const m = /^(.*?)\s(07X-XXX-\d{4})$/.exec(l);
      const name = m ? m[1] : l;
      const num = m ? m[2] : "";
      return `<div class="c"><div class="av">${esc(name.replace(/^Mr /, "").slice(0, 1))}</div><div><div class="n">${esc(name)}</div><div class="p">${esc(num)}</div></div></div>`;
    })
    .join("");
  return phone(
    `<h1>Contacts</h1><div class="cap">${esc(title)}</div>${items}`,
    `h1 { font: 800 44px "Noto Sans"; margin: 20px 34px 4px; } .cap { margin: 0 34px 20px; color: #667; font-size: 18px; }
     .c { display: flex; gap: 20px; align-items: center; padding: 20px 34px; border-bottom: 1px solid #e3e6e8; }
     .av { width: 64px; height: 64px; border-radius: 50%; background: #1f5f68; color: #fff; display: grid; place-items: center; font: 700 28px "Noto Sans"; }
     .n { font: 600 26px "Noto Sans"; } .p { color: #556; font-size: 21px; margin-top: 4px; }`,
  );
}

function smsScreen(lines) {
  const text = lines.join(" ");
  const sender = text.split(":")[0];
  const body = text.slice(sender.length + 1).trim();
  return phone(
    `<div class="hdr"><div class="av">L</div><div class="who">${esc(sender)}</div></div>
     <div class="thread"><div class="day">Thursday 29 October</div><div class="bubble">${esc(sender)}: ${esc(body)}</div></div>`,
    `.hdr { display: grid; justify-items: center; gap: 8px; padding: 18px 0 22px; border-bottom: 1px solid #e3e6e8; }
     .av { width: 80px; height: 80px; border-radius: 50%; background: #7a4f9a; color: #fff; display: grid; place-items: center; font: 700 34px "Noto Sans"; }
     .who { font: 600 22px "Noto Sans"; } .thread { padding: 26px; } .day { text-align: center; color: #778; font-size: 18px; margin-bottom: 16px; }
     .bubble { background: #e9e9eb; border-radius: 28px; padding: 22px 26px; font-size: 24px; line-height: 1.45; max-width: 88%; }`,
  );
}

function policyPdf(text) {
  const pages = text.split(/\[Page \d+\]\n?/).filter((p) => p.trim());
  const body = pages
    .map((p, i) => {
      const lines = p.trim().split("\n");
      const content = i === 0 ? `<div class="brand">${esc(lines[0])}</div><div class="title">${esc(lines[1])}</div>${rows(lines.slice(2))}` : `<h2>${esc(lines[0])}</h2>${lines.slice(1).map((l) => `<p>${esc(l)}</p>`).join("")}`;
      return `<section class="page">${content}<div class="foot">Page ${i + 1} of ${pages.length}. SAMPLE document. Ceylon Shield Insurance is fictional.</div><div class="wm"><span>SAMPLE</span></div></section>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>${FONTS}
  @page { size: A5; margin: 0; }
  body { margin: 0; font-family: "Noto Sans", sans-serif; color: #1d2a2f; }
  .page { position: relative; width: 148mm; height: 210mm; padding: 16mm 14mm; page-break-after: always; overflow: hidden; }
  .brand { font-weight: 800; color: #8a3348; font-size: 15pt; border-bottom: 3px solid #8a3348; padding-bottom: 6pt; }
  .title { font-size: 12pt; color: #44545a; margin: 6pt 0 10pt; }
  .row { display: flex; justify-content: space-between; gap: 12pt; padding: 6pt 0; border-bottom: 1px solid #e2dccd; font-size: 10pt; }
  .row .k { color: #5b6a70; } .row .v { font-weight: 700; text-align: right; }
  h2 { font-size: 14pt; color: #8a3348; } p { font-size: 10.5pt; line-height: 1.5; }
  .foot { position: absolute; bottom: 10mm; left: 14mm; right: 14mm; font-size: 8pt; color: #778; }
  .wm { position: absolute; inset: 0; display: grid; place-items: center; pointer-events: none; }
  .wm span { font: 900 60pt "Noto Sans"; color: rgba(194,57,77,.1); transform: rotate(-30deg); }
  </style></head><body>${body}</body></html>`;
}

const STYLE = {
  S04: (l) => documentPhoto({ accent: "#b9740f", band: "#fff3dc", lines: l, rotate: -1.6 }),
  S05: (l) => documentPhoto({ accent: "#1f5f68", band: "#e6f2f1", lines: l, rotate: 1.1 }),
  S06: (l) => documentPhoto({ accent: "#8a3348", band: "#f8e9ed", lines: l, rotate: -0.8, extraCss: ".paper { border: 10px double #8a3348; }" }),
  S08: clinicBook,
  S09: handwritten,
  S10: drawerPhoto,
  S12: bankScreen,
  S15: contactsScreen,
  S17: smsScreen,
};

const browser = await chromium.launch(launchOptions());
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const s of sources) {
  const target = resolve(outDir, s.file.replace(/^files\//, ""));
  if (s.id === "S07") {
    await page.setContent(policyPdf(s.text), { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({ path: target, format: "A5", printBackground: true });
    console.log("rendered", s.id, target);
    continue;
  }
  const make = STYLE[s.id];
  if (!make) continue;
  const lines = s.text.split("\n").filter((l) => l.trim());
  await page.setContent(make(lines), { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const size = await page.evaluate(() => {
    const el = document.querySelector(".table, .scene");
    const r = el.getBoundingClientRect();
    return { width: Math.ceil(r.width), height: Math.ceil(r.height) };
  });
  await page.setViewportSize(size);
  await page.screenshot({ path: target, clip: { x: 0, y: 0, ...size } });
  console.log("rendered", s.id, target);
}
await browser.close();
