// Draws arrows between elements of an HTML diagram, from their edges, so the layout can change
// without redrawing anything by hand. Used by 07-screen-map.html and 14-security.html.
//
// setupWires(posterElement, () => [ ...wires ])  draws now and again on window.redrawWires()
//   (the renderer calls it once the embedded fonts have loaded, so the boxes have their real size).
// drawWires(posterElement, [
//   { from: "id", to: "id", out: "r", in: "l" },             // a curve between two sides (t, r, b, l)
//   { from: "id", to: "id", out: "l", in: "l", via: { x: 30 } },  // along a channel at x (or { y })
//   { ..., outAt: 0.3, inAt: 0.7 },                          // where on the side (0..1, default 0.5)
//   { ..., inAt: "level" },                                  // straight across when the boxes overlap
//   { ..., label: "text", at: 0.5, dx: 0, dy: 0 },           // a label along the wire
//   { ..., dashed: true, color: "#4f4fc8" },
// ])
function setupWires(poster, makeWires) {
  const draw = () => drawWires(poster, makeWires());
  window.redrawWires = draw;
  draw();
}

function drawWires(poster, wires) {
  const NS = "http://www.w3.org/2000/svg";
  let svg = poster.querySelector("svg.wires");
  if (!svg) {
    svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "wires");
    poster.appendChild(svg);
  }
  svg.replaceChildren();
  poster.querySelectorAll(".tag[data-wire]").forEach((t) => t.remove());
  const defs = document.createElementNS(NS, "defs");
  svg.appendChild(defs);
  const markers = new Map();
  const marker = (color) => {
    if (markers.has(color)) return markers.get(color);
    const id = `arr${markers.size}`;
    const m = document.createElementNS(NS, "marker");
    m.setAttribute("id", id);
    m.setAttribute("viewBox", "0 0 10 10");
    m.setAttribute("refX", "9");
    m.setAttribute("refY", "5");
    m.setAttribute("markerWidth", "7");
    m.setAttribute("markerHeight", "7");
    m.setAttribute("orient", "auto-start-reverse");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", "M0,0 L10,5 L0,10 z");
    p.setAttribute("fill", color);
    m.appendChild(p);
    defs.appendChild(m);
    markers.set(color, id);
    return id;
  };
  const P = poster.getBoundingClientRect();
  const rect = (id) => {
    const el = document.getElementById(id);
    if (!el) throw new Error(`no element #${id}`);
    const r = el.getBoundingClientRect();
    return { x: r.left - P.left, y: r.top - P.top, w: r.width, h: r.height };
  };
  const port = (r, side, at = 0.5) => {
    if (side === "t") return { x: r.x + r.w * at, y: r.y };
    if (side === "b") return { x: r.x + r.w * at, y: r.y + r.h };
    if (side === "l") return { x: r.x, y: r.y + r.h * at };
    return { x: r.x + r.w, y: r.y + r.h * at };
  };
  const DIR = { t: [0, -1], b: [0, 1], l: [-1, 0], r: [1, 0] };
  // An orthogonal path through the points, with rounded corners.
  const rounded = (pts, radius = 14) => {
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const a = pts[i - 1], b = pts[i], c = pts[i + 1];
      const l1 = Math.hypot(b.x - a.x, b.y - a.y), l2 = Math.hypot(c.x - b.x, c.y - b.y);
      const r = Math.min(radius, l1 / 2, l2 / 2);
      const p1 = { x: b.x + ((a.x - b.x) / l1) * r, y: b.y + ((a.y - b.y) / l1) * r };
      const p2 = { x: b.x + ((c.x - b.x) / l2) * r, y: b.y + ((c.y - b.y) / l2) * r };
      d += ` L${p1.x},${p1.y} Q${b.x},${b.y} ${p2.x},${p2.y}`;
    }
    const last = pts[pts.length - 1];
    return d + ` L${last.x},${last.y}`;
  };
  for (const w of wires) {
    const a = rect(w.from), b = rect(w.to);
    const p1 = port(a, w.out, w.outAt);
    let inAt = w.inAt;
    if (inAt === "level") {
      // line up with where the wire leaves, kept a little inside the target's edge
      const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
      inAt = w.in === "l" || w.in === "r" ? clamp((p1.y - b.y) / b.h, 12 / b.h, 1 - 12 / b.h) : clamp((p1.x - b.x) / b.w, 20 / b.w, 1 - 20 / b.w);
    }
    const p2 = port(b, w.in, inAt);
    let d;
    if (w.via && w.via.x !== undefined) {
      d = rounded([p1, { x: w.via.x, y: p1.y }, { x: w.via.x, y: p2.y }, p2]);
    } else if (w.via && w.via.y !== undefined) {
      d = rounded([p1, { x: p1.x, y: w.via.y }, { x: p2.x, y: w.via.y }, p2]);
    } else if (w.straight) {
      d = `M${p1.x},${p1.y} L${p2.x},${p2.y}`;
    } else {
      const k = Math.max(36, Math.hypot(p2.x - p1.x, p2.y - p1.y) * 0.42);
      const [ox, oy] = DIR[w.out], [ix, iy] = DIR[w.in];
      d = `M${p1.x},${p1.y} C${p1.x + ox * k},${p1.y + oy * k} ${p2.x + ix * k},${p2.y + iy * k} ${p2.x},${p2.y}`;
    }
    const color = w.color || "#6f8489";
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", w.width || "1.9");
    if (w.dashed) path.setAttribute("stroke-dasharray", "7 5");
    path.setAttribute("marker-end", `url(#${marker(color)})`);
    svg.appendChild(path);
    if (w.label) {
      const pt = path.getPointAtLength(path.getTotalLength() * (w.at ?? 0.5));
      const tag = document.createElement("div");
      tag.className = "tag";
      tag.dataset.wire = "1";
      tag.textContent = w.label;
      tag.style.left = `${pt.x + (w.dx || 0)}px`;
      tag.style.top = `${pt.y + (w.dy || 0)}px`;
      poster.appendChild(tag);
    }
  }
}
