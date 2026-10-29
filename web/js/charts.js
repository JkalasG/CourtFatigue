/* CourtFatigue - dependency-free SVG charts */
(function () {
  "use strict";

  // tactics-board palette (mirrors css/style.css): chalk ink, maple wood, court-line orange
  const C = { accent: "#ece6da", accent2: "#cfc6b6", good: "#9cc48a", bad: "#e5584f", blue: "#a39887", muted: "#a39887", maple: "#c9a273", court: "#e8923f", dim: "#6f6455" };
  const T = (k, v) => window.I18N.t(k, v);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (v, d = 1) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);

  function scale(d0, d1, r0, r1) {
    const k = (r1 - r0) / (d1 - d0 || 1);
    return (v) => r0 + (v - d0) * k;
  }
  function niceTicks(lo, hi, n = 5) {
    const span = hi - lo || 1;
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(10));
    return out;
  }
  function tickFmt(ticks) {
    const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
    let d = 0;
    while (Math.abs(step * 10 ** d - Math.round(step * 10 ** d)) > 1e-6 && d < 4) d++;
    return (t) => t.toFixed(d);
  }
  function wrap(W, H, inner, label) {
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label || T("chart.default"))}">${inner}</svg>`;
  }
  function empty(msg, W = 640, H = 160) {
    return wrap(W, H, `<text class="empty" x="${W / 2}" y="${H / 2}" text-anchor="middle">${esc(msg)}</text>`, msg);
  }

  /* Line with confidence band. pts: {x, y, lo, hi, tip}; ticks: [{x,label}] */
  function lineBand(o) {
    const pts = o.pts.filter((p) => p.y != null);
    if (!pts.length) return empty(o.emptyMsg || T("chart.nodata"));
    const W = o.W || 640, H = o.H || 310, m = { l: 52, r: 18, t: 16, b: 58 };
    const ys = pts.flatMap((p) => [p.lo, p.hi, p.y, o.includeZero === false ? null : 0]).filter((v) => v != null);
    let y0 = Math.min(...ys), y1 = Math.max(...ys);
    const pad = (y1 - y0) * 0.12 || 1;
    y0 -= pad; y1 += pad;
    const sx = scale(o.xmin, o.xmax, m.l, W - m.r), sy = scale(y0, y1, H - m.b, m.t);
    let g = "";
    const yt = niceTicks(y0, y1, 5), yf = tickFmt(yt);
    yt.forEach((t) => {
      g += `<g class="ax"><line x1="${m.l}" x2="${W - m.r}" y1="${sy(t)}" y2="${sy(t)}" class="grid-l"/><text x="${m.l - 8}" y="${sy(t) + 4}" text-anchor="end">${yf(t)}</text></g>`;
    });
    if (o.hatchFrom != null) {
      const hx = sx(o.hatchFrom);
      g += `<rect class="hatch" x="${hx}" y="${m.t}" width="${W - m.r - hx}" height="${H - m.b - m.t}"/>`;
      g += `<text class="t" x="${(hx + W - m.r) / 2}" y="${m.t + 14}" text-anchor="middle">${esc(o.hatchLabel || T("chart.fewdata"))}</text>`;
    }
    if (y0 < 0 && y1 > 0) g += `<line class="zero" x1="${m.l}" x2="${W - m.r}" y1="${sy(0)}" y2="${sy(0)}"/>`;
    (o.ticks || []).forEach((t) => {
      g += `<text class="t" x="${sx(t.x)}" y="${H - m.b + 18}" text-anchor="middle">${esc(t.label)}</text>`;
      if (t.sub != null) g += `<text class="t" x="${sx(t.x)}" y="${H - m.b + 32}" text-anchor="middle" style="opacity:.7">${esc(t.sub)}</text>`;
    });
    const band = pts.filter((p) => p.lo != null && p.hi != null);
    if (band.length > 1) {
      const top = band.map((p) => `${sx(p.x)},${sy(p.hi)}`).join(" ");
      const bot = band.slice().reverse().map((p) => `${sx(p.x)},${sy(p.lo)}`).join(" ");
      g += `<polygon class="band" points="${top} ${bot}"/>`;
    }
    if (pts.length > 1) g += `<polyline class="line" points="${pts.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")}"/>`;
    pts.forEach((p) => {
      if (o.errorBars && p.lo != null) {
        const x = sx(p.x);
        g += `<path class="err" d="M${x} ${sy(p.lo)}V${sy(p.hi)}M${x - 4} ${sy(p.lo)}h8M${x - 4} ${sy(p.hi)}h8"/>`;
      }
      g += `<circle class="dot" cx="${sx(p.x)}" cy="${sy(p.y)}" r="3.5"><title>${esc(p.tip || "")}</title></circle>`;
    });
    g += `<text class="t" x="14" y="${(m.t + H - m.b) / 2}" transform="rotate(-90 14 ${(m.t + H - m.b) / 2})" text-anchor="middle">${esc(o.yTitle || "")}</text>`;
    g += `<text class="t" x="${(m.l + W - m.r) / 2}" y="${H - 2}" text-anchor="middle">${esc(o.xTitle || "")}</text>`;
    return wrap(W, H, g, o.label);
  }

  /* Horizontal forest plot. rows: {label, est, lo, hi, color, tip} */
  function forest(o) {
    const rows = o.rows.filter((r) => r.est != null);
    if (!rows.length) return empty(o.emptyMsg || T("chart.nodata"));
    const W = o.W || 640, rowH = o.rowH || 34, m = { l: o.labelW || 190, r: 24, t: 10, b: 38 };
    const H = m.t + m.b + rows.length * rowH;
    let lo = Math.min(0, ...rows.map((r) => r.lo)), hi = Math.max(0, ...rows.map((r) => r.hi));
    const pad = (hi - lo) * 0.1 || 1; lo -= pad; hi += pad;
    const sx = scale(lo, hi, m.l, W - m.r);
    let g = "";
    const xt = niceTicks(lo, hi, 5), xf = tickFmt(xt);
    xt.forEach((t) => {
      g += `<g class="ax"><line x1="${sx(t)}" x2="${sx(t)}" y1="${m.t}" y2="${H - m.b}" class="grid-l"/><text x="${sx(t)}" y="${H - m.b + 16}" text-anchor="middle">${xf(t)}</text></g>`;
    });
    g += `<line class="zero" x1="${sx(0)}" x2="${sx(0)}" y1="${m.t}" y2="${H - m.b}"/>`;
    rows.forEach((r, i) => {
      const y = m.t + i * rowH + rowH / 2, col = r.color || C.accent;
      g += `<text class="lbl" x="${m.l - 10}" y="${y + 4}" text-anchor="end">${esc(r.label)}</text>`;
      g += `<path d="M${sx(r.lo)} ${y}H${sx(r.hi)}M${sx(r.lo)} ${y - 4}v8M${sx(r.hi)} ${y - 4}v8" stroke="${col}" stroke-width="1.25" fill="none"/>`;
      g += `<circle class="pt" cx="${sx(r.est)}" cy="${y}" r="4" fill="${col}"><title>${esc(r.tip || "")}</title></circle>`;
    });
    g += `<text class="t" x="${(m.l + W - m.r) / 2}" y="${H - 2}" text-anchor="middle">${esc(o.xTitle || "")}</text>`;
    return wrap(W, H, g, o.label);
  }

  /* Grouped bars (percentages). groups: {label, bars:[{v, color, name}]} */
  function groupedBars(o) {
    const W = o.W || 640, H = o.H || 280, m = { l: 44, r: 12, t: 22, b: 52 };
    const max = Math.max(o.max || 0, ...o.groups.flatMap((g) => g.bars.map((b) => b.v)));
    const sy = scale(0, max * 1.15, H - m.b, m.t);
    let g = "";
    niceTicks(0, max * 1.15, 4).forEach((t) => {
      g += `<g class="ax"><line x1="${m.l}" x2="${W - m.r}" y1="${sy(t)}" y2="${sy(t)}" class="grid-l"/><text x="${m.l - 8}" y="${sy(t) + 4}" text-anchor="end">${t}%</text></g>`;
    });
    const gw = (W - m.l - m.r) / o.groups.length;
    o.groups.forEach((grp, gi) => {
      const bw = Math.min(34, (gw - 24) / grp.bars.length);
      const x0 = m.l + gi * gw + (gw - bw * grp.bars.length - 6 * (grp.bars.length - 1)) / 2;
      grp.bars.forEach((b, bi) => {
        const x = x0 + bi * (bw + 6), y = sy(b.v);
        g += `<rect class="bar" x="${x}" y="${y}" width="${bw}" height="${H - m.b - y}" fill="${b.color}"><title>${esc(b.name)}: ${b.v.toFixed(1)}%</title></rect>`;
        g += `<text class="lbl" x="${x + bw / 2}" y="${y - 6}" text-anchor="middle">${b.v.toFixed(0)}%</text>`;
      });
      g += `<text class="t" x="${m.l + gi * gw + gw / 2}" y="${H - m.b + 18}" text-anchor="middle">${esc(grp.label)}</text>`;
    });
    return wrap(W, H, g, o.label);
  }

  /* Simple vertical bars (shot coverage per bucket). */
  function coverageBars(o) {
    const W = o.W || 640, H = o.H || 280, m = { l: 54, r: 12, t: 22, b: 50 };
    const max = Math.max(...o.rows.map((r) => r.n));
    const sy = scale(0, max * 1.12, H - m.b, m.t);
    let g = "";
    niceTicks(0, max * 1.12, 4).forEach((t) => {
      g += `<g class="ax"><line x1="${m.l}" x2="${W - m.r}" y1="${sy(t)}" y2="${sy(t)}" class="grid-l"/><text x="${m.l - 8}" y="${sy(t) + 4}" text-anchor="end">${t >= 1000 ? t / 1000 + "k" : t}</text></g>`;
    });
    const gw = (W - m.l - m.r) / o.rows.length, bw = gw * 0.42;
    o.rows.forEach((r, i) => {
      const x = m.l + i * gw + (gw - bw) / 2, y = sy(r.n), thin = r.n < 8000;
      g += `<rect class="bar" x="${x}" y="${y}" width="${bw}" height="${H - m.b - y}" fill="${thin ? C.bad : C.maple}" opacity="${thin ? 0.85 : 1}"><title>${T("chart.tip.cov", { n: r.n, p: r.players, fg: (r.fg * 100).toFixed(1) })}</title></rect>`;
      g += `<text class="lbl" x="${x + bw / 2}" y="${y - 6}" text-anchor="middle">${window.I18N.num(r.n)}</text>`;
      g += `<text class="t" x="${x + bw / 2}" y="${H - m.b + 17}" text-anchor="middle">${r.lo}–${r.hi >= 24 ? "24" : r.hi}</text>`;
      g += `<text class="t" x="${x + bw / 2}" y="${H - m.b + 31}" text-anchor="middle" style="opacity:.7">${r.players} ${T("chart.pl")}</text>`;
    });
    g += `<text class="t" x="${(m.l + W - m.r) / 2}" y="${H - 2}" text-anchor="middle">${esc(T("chart.min"))}</text>`;
    return wrap(W, H, g, o.label);
  }

  /* NBA half court. Coordinates in tenths of a foot; the Y axis is flipped with scale(1,-1). */
  function courtLines() {
    const arcA = Math.asin(92.5 / 237.5);
    const pts = [];
    for (let i = 0; i <= 60; i++) { const a = arcA + (Math.PI - 2 * arcA) * i / 60; pts.push(`${(237.5 * Math.cos(a)).toFixed(1)} ${(237.5 * Math.sin(a)).toFixed(1)}`); }
    const ra = [];
    for (let i = 0; i <= 30; i++) { const a = Math.PI * i / 30; ra.push(`${(40 * Math.cos(a)).toFixed(1)} ${(40 * Math.sin(a)).toFixed(1)}`); }
    const s = "fill='none' stroke='rgba(232,146,63,.55)' stroke-width='1.5'";
    return `<g ${s}>
      <rect x="-250" y="-47.5" width="500" height="470"/>
      <rect x="-80" y="-47.5" width="160" height="190"/>
      <rect x="-60" y="-47.5" width="120" height="190" stroke-dasharray="6 5"/>
      <circle cx="0" cy="142.5" r="60"/>
      <path d="M ${ra.join(" L ")}"/>
      <path d="M -220 -47.5 L -220 92.5 L ${pts.join(" L ")} L 220 92.5 L 220 -47.5"/>
      <line x1="-30" y1="-7.5" x2="30" y2="-7.5" stroke="#ece6da" stroke-width="3"/>
      <circle cx="0" cy="0" r="7.5" stroke="#e8923f"/></g>`;
  }
  function court(shots, label) {
    let dots = "";
    shots.forEach((s) => {
      dots += s.m
        ? `<circle cx="${s.x}" cy="${s.y}" r="4" fill="#9cc48a" fill-opacity=".7"/>`
        : `<g stroke="#e5584f" stroke-opacity=".75" stroke-width="1.75"><line x1="${s.x - 4.5}" y1="${s.y - 4.5}" x2="${s.x + 4.5}" y2="${s.y + 4.5}"/><line x1="${s.x - 4.5}" y1="${s.y + 4.5}" x2="${s.x + 4.5}" y2="${s.y - 4.5}"/></g>`;
    });
    return `<svg viewBox="-260 -432 520 490" role="img" aria-label="${esc(label || "")}"><g transform="scale(1,-1)">${courtLines()}${dots}</g></svg>`;
  }

  window.CF = { lineBand, forest, groupedBars, coverageBars, court, fmt, esc, C };
})();
