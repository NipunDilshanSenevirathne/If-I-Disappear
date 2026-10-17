// Renders the diagrams and wireframes in docs/diagrams/src into docs/diagrams:
//   *.mmd  (Mermaid)  -> name.svg and name.png
//   *.html (wireframes and posters drawn in HTML) -> name.png
//   node scripts/render-diagrams.mjs [name-filter]
// Mermaid is loaded from MERMAID_JS (a local mermaid.min.js) if set, else from jsDelivr.
// The app's own fonts are embedded, so the images match the app.

import { chromium } from "playwright";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { basename, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..", "..");
const srcDir = join(root, "docs", "diagrams", "src");
const outDir = join(root, "docs", "diagrams");
mkdirSync(outDir, { recursive: true });

const require = createRequire(import.meta.url);
const fontFile = (pkg, file) => join(dirname(require.resolve(`${pkg}/package.json`)), "files", file);
const fontFace = (family, pkg, file, weights) =>
  `@font-face{font-family:"${family}";src:url(data:font/woff2;base64,${readFileSync(fontFile(pkg, file)).toString("base64")}) format("woff2");font-weight:${weights};font-display:block}`;
const fonts = [
  fontFace("Figtree", "@fontsource-variable/figtree", "figtree-latin-wght-normal.woff2", "300 900"),
  fontFace("Bricolage Grotesque", "@fontsource-variable/bricolage-grotesque", "bricolage-grotesque-latin-opsz-normal.woff2", "200 800"),
].join("\n");

const mermaidSrc = process.env.MERMAID_JS ?? "https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js";
const filter = process.argv[2] ?? "";

const exe = [process.env.CHROMIUM_PATH, "/opt/pw-browsers/chromium"].filter(Boolean).find((p) => existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const context = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1600, height: 1200 } });
const page = await context.newPage();
page.on("pageerror", (e) => console.error("page error:", e.message));

const files = readdirSync(srcDir)
  .filter((f) => (f.endsWith(".mmd") || f.endsWith(".html")) && f.includes(filter))
  .sort();

let failed = 0;
for (const file of files) {
  const name = basename(file).replace(/\.(mmd|html)$/, "");
  try {
    await render(file, name);
    console.log("rendered", name);
  } catch (e) {
    failed += 1;
    console.error(`FAILED ${name}: ${String(e.message ?? e).split("\n").slice(0, 3).join(" ")}`);
  }
}

async function render(file, name) {
  if (file.endsWith(".mmd")) {
    const text = readFileSync(join(srcDir, file), "utf8");
    await page.setContent(
      `<!doctype html><html><head><meta charset="utf-8"><style>${fonts}
      html,body{margin:0;background:#ffffff;font-family:Figtree,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#0e2a33}
      #box{display:inline-block;padding:28px;background:#ffffff}
      </style></head><body><div id="box"></div></body></html>`,
    );
    if (mermaidSrc.startsWith("http")) await page.addScriptTag({ url: mermaidSrc });
    else await page.addScriptTag({ path: mermaidSrc });
    await page.evaluate(() => document.fonts.ready);
    const svg = await page.evaluate(async (def) => {
      // eslint-disable-next-line no-undef
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
      // eslint-disable-next-line no-undef
      const { svg } = await mermaid.render("d", def);
      const box = document.getElementById("box");
      box.innerHTML = svg;
      // draw at the diagram's natural size (Mermaid makes it shrink to its container)
      const el = box.querySelector("svg");
      const vb = el.viewBox.baseVal;
      if (vb && vb.width) {
        el.setAttribute("width", String(Math.ceil(vb.width)));
        el.setAttribute("height", String(Math.ceil(vb.height)));
        el.style.maxWidth = "none";
      }
      return box.innerHTML;
    }, text);
    await page.waitForTimeout(150);
    writeFileSync(join(outDir, `${name}.svg`), svg);
    await page.locator("#box").screenshot({ path: join(outDir, `${name}.png`) });
  } else {
    await page.goto(pathToFileURL(join(srcDir, file)).href);
    await page.addStyleTag({ content: fonts });
    await page.evaluate(() => document.fonts.ready);
    // HTML diagrams draw their arrows from the boxes' positions: draw them again now that the
    // embedded fonts have given every box its real size.
    await page.evaluate(() => (window.redrawWires ? window.redrawWires() : undefined));
    await page.waitForTimeout(150);
    const target = (await page.locator("[data-shot]").count()) ? page.locator("[data-shot]").first() : page.locator("body");
    await target.screenshot({ path: join(outDir, `${name}.png`) });
  }
}

await browser.close();
process.exit(failed ? 1 : 0);
