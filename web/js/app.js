/* CourtFatigue - interface logic (plain HTML + CSS + JS, no dependencies). Texts live in i18n.js. */
(function () {
  "use strict";
  const { lineBand, forest, groupedBars, coverageBars, court, fmt, esc, C } = window.CF;
  const { t, tl, num, apply } = window.I18N;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
  const yy = (s) => `${s}-${String(+s + 1).slice(2)}`;

  const ZONES = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3", "Right Corner 3", "Above the Break 3"];
  const zoneName = (z) => t("zone." + z);

  let S = null;           // population summary
  let DEFR = null;        // team defensive effect
  let CONT = null;        // defender distance (2014-15)
  let QUAL = null;        // data-quality audit
  let X = null;           // extra analyses: impact, shot type, selection bias, free throws, bench time, team audit
  let H = null;           // preregistered replication on 2025-26
  let P = [];             // players
  let cur = null;         // selected player
  let ready = false;
  const shotCache = {};

  /* ---------------- loading ---------------- */
  async function load() {
    try {
      const [s, p] = await Promise.all([
        fetch("data/summary.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch("data/players.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      ]);
      S = s; P = p;
      try {
        [DEFR, CONT] = await Promise.all([fetch("data/defense.json").then((r) => r.json()), fetch("data/contest.json").then((r) => r.json())]);
      } catch (e) { DEFR = null; CONT = null; }
      try { QUAL = await fetch("data/quality.json").then((r) => r.json()); } catch (e) { QUAL = null; }
      try { X = await fetch("data/extra.json").then((r) => r.json()); } catch (e) { X = null; }
      try { H = await fetch("data/holdout_replication.json").then((r) => r.json()); } catch (e) { H = null; }
    } catch (e) {
      const box = $("#load-error");
      box.classList.remove("hidden");
      box.innerHTML = t("err.load");
      return;
    }
    init();
  }

  /* ---------------- tabs ---------------- */
  let backTo = null;       // where the "back" bar returns to: {tab, el}
  // Old and inner destinations -> [tab, tool, element to land on]; links and bookmarks keep working
  const ROUTES = { card: ["staff", null, "sec-card"], uses: ["staff", null, "sec-uses"], calc: ["tools", "calc"],
    player: ["tools", "player"], new: ["tools", "new"], audit: ["evidence", null, "ch-teams"] };
  function setTool(tool) {
    $$("#toolbar .tool-btn").forEach((b) => b.classList.toggle("on", b.dataset.tool === tool));
    $$("#tools .tool").forEach((p) => p.classList.toggle("on", p.id === "tool-" + tool));
  }
  // push = a click by the reader, so the browser's Back button returns to the previous tab
  function show(name, push) {
    const [tab, tool, focus] = ROUTES[name] || [name];
    const pane = $("#" + tab);
    if (!pane || !pane.classList.contains("pane")) return show("summary");
    $("#backbar").classList.add("hidden");
    $$(".pane").forEach((p) => p.classList.toggle("on", p.id === tab));
    $$("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    if (tool) setTool(tool);
    if (location.hash !== "#" + name) history[push ? "pushState" : "replaceState"](null, "", "#" + name);
    try { sessionStorage.setItem("cf.route", name); } catch (e) {}
    const target = focus && $("#" + focus);
    if (target) target.scrollIntoView({ block: "start", behavior: "instant" });
    else window.scrollTo({ top: 0, behavior: "instant" });
  }
  function bindTabs() {
    $$("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab, true)));
    document.addEventListener("click", (e) => {
      const g = e.target.closest("[data-go]");
      if (!g) return;
      show(g.dataset.go, true);
      // links out of "Uses & benefits" land on the supporting chart and offer a way back
      if (g.dataset.from) {
        backTo = { tab: g.dataset.from, el: g.closest(".use") };
        const bar = $("#backbar");
        $("span", bar).textContent = t("back.to", { tab: t("nav." + g.dataset.from) });
        bar.classList.remove("hidden");
      }
      const target = g.dataset.focus && $("#" + g.dataset.focus);
      if (target) (target.closest(".card") || target).scrollIntoView({ block: "start", behavior: "instant" });
    });
    $("#back-btn").addEventListener("click", () => {
      if (!backTo) return;
      const { tab, el } = backTo;
      show(tab, true);
      if (el) el.scrollIntoView({ block: "center", behavior: "instant" });
    });
    window.addEventListener("hashchange", () => show(location.hash.slice(1)));
    // switching tools keeps the reader where they are: the panel opens right under the cards
    $$("#toolbar .tool-btn").forEach((b) => b.addEventListener("click", () => {
      setTool(b.dataset.tool);
      history.replaceState(null, "", "#" + b.dataset.tool);
      try { sessionStorage.setItem("cf.route", b.dataset.tool); } catch (e) {}
    }));
    $$("#ev-index button").forEach((b) => b.addEventListener("click", () => $("#" + b.dataset.jump).scrollIntoView({ behavior: "smooth" })));
    $$("#lang-switch button").forEach((b) => b.addEventListener("click", () => window.I18N.set(b.dataset.lang)));
    // Scroll cue and back-to-top must not touch the hash (it drives the tabs)
    $(".scroll-cue").addEventListener("click", (e) => { e.preventDefault(); $("#tech").scrollIntoView({ behavior: "smooth" }); });
    const top = $("#to-top");
    top.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    window.addEventListener("scroll", () => top.classList.toggle("on", window.scrollY > 600), { passive: true });
  }

  const kpi = (l, v, d, cls = "") => `<div class="kpi ${cls}"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d || ""}</div></div>`;
  const icon = (n) => `<svg class="ic" aria-hidden="true"><use href="#i-${n}"/></svg>`;

  /* ---------------- population verdict ---------------- */
  const REF = () => `${S.short_lo}–${S.short} min`;   // "warmed up" reference

  function popVerdict() {
    const h = S.heterogeneity, mu = h.mu * 100, lo = h.mu_lo * 100, hi = h.mu_hi * 100;
    const b0 = S.buckets[0];
    const cold = b0 && b0.hi_pp < 0 ? " " + t("v.cold", { pp: fmt(b0.effect_pp, 1), min: b0.hi_edge }) : "";
    const ci = t("ci95", { lo: fmt(lo, 2), hi: fmt(hi, 2) });
    const v = { long: S.long, mu: fmt(mu, 2), ci, ref: REF() };
    if (hi < 0) return { cls: "alert", badge: t("v.alert.badge"), title: t("v.alert.title"), text: t("v.alert.text", v) };
    if (lo > 0) return { cls: "ok", badge: t("v.up.badge"), title: t("v.up.title"), text: t("v.up.text", v) + cold };
    return { cls: "ok", badge: t("v.none.badge"), title: t("v.none.title"),
      text: t("v.none.text", v) + (lo < 0 ? " " + t("v.none.rule", { x: Math.abs(lo).toFixed(1) }) : "") + " " + t("v.none.tail") + cold };
  }

  /* ---------------- plain language ---------------- */
  function coldRow(label) { return (S.cold_start || []).find((r) => r.label === label && r.effect_pp != null); }

  function renderSimple() {
    const h = S.heterogeneity, drop = h.mu_hi < 0, c0 = coldRow("0–30 s");
    const cc = S.slopes.con_controles || [], b2b = cc.find((r) => r.term === "b2b"), home = cc.find((r) => r.term === "is_home");
    $("#hx-answer").innerHTML = t(drop ? "hx.a.yes" : "hx.a.no");
    $("#hx-sub").textContent = t(H && H.verdict === "replicated" ? "hx.sub.rep" : "hx.sub",
      { shots: num(S.n_shots), games: num(S.n_games), long: S.long, pts: X ? Math.abs(X.impact.cold.total.pts).toFixed(0) : "—" });
    const ci = X && X.impact.cold.total, bi = X && X.impact.b2b;
    const coldCost = ci ? " " + t("hx.f2.cost", { pts: Math.abs(ci.pts).toFixed(0), lo: Math.abs(ci.hi).toFixed(0), hi: Math.abs(ci.lo).toFixed(0),
      w: Math.abs(X.impact.cold.wins.pts).toFixed(1) }) : "";
    const b2bCost = bi ? " " + t("hx.f3.cost", { pts: Math.abs(bi.pts).toFixed(0), lo: Math.abs(bi.hi).toFixed(0), hi: Math.abs(bi.lo).toFixed(0) }) : "";

    const fact = (cls, big, unit, l, d) =>
      `<div class="fact ${cls}"><div class="big">${big}<small>${unit}</small></div><div class="l">${l}</div><p>${d}</p></div>`;
    const h0 = H && H.cold_start["0–30 s"];
    $("#facts").innerHTML =
      (c0 ? fact("bad", fmt(c0.effect_pp, 2), " pp", t("hx.f2.l"), t("hx.f2.d")) : "") +
      (ci ? fact("bad", "−" + Math.abs(ci.pts).toFixed(0), " pts", t("hx.fc.l"),
        t("hx.fc.d", { lo: Math.abs(ci.hi).toFixed(0), hi: Math.abs(ci.lo).toFixed(0), w: Math.abs(X.impact.cold.wins.pts).toFixed(1) })) : "") +
      (h0 ? fact(H.verdict === "replicated" ? "good" : "warn", t("hx.fr.big." + H.verdict), "", t("hx.fr.l"),
        t("hx.fr.d", { x: fmt(h0.new, 2), lo: fmt(h0.ci95[0], 2), hi: fmt(h0.ci95[1], 2) })) : "") +
      fact(S.n_flagged ? "bad" : "good", S.n_flagged, " " + t("of") + " " + S.n_contrast_players, t("hx.f1.l"),
        t(S.n_flagged ? "hx.f1.d.some" : "hx.f1.d"));
    void coldCost; void b2bCost; void b2b; void home;

    // One stint on court: cold start buckets, then the warmed-up stretch up to ~12 min
    const segs = (S.cold_start || []).filter((r) => r.group === "Time since entering" && r.effect_pp != null && !/reference/.test(r.label))
      .map((r) => ({ label: tl(r.label), v: r.effect_pp, cold: r.hi_pp < 0, w: 1 }));
    segs.push({ label: t("hx.seg.warm", { long: S.long }), v: h.mu * 100, cold: false, warm: true, w: 4 });
    $("#stint").innerHTML =
      `<h3>${icon("clock")}${t("hx.stint.t")}</h3><p class="sub">${t("hx.stint.s")}</p><div class="timeline">` +
      segs.map((s) => `<div class="seg ${s.cold ? "cold" : "ok"}" style="flex:${s.w}">` +
        `<div class="v">${s.warm ? t("hx.normal") : fmt(s.v, 1) + " " + t("hx.pts")}</div><div class="bar"></div><div class="t">${s.label}</div></div>`).join("") +
      `</div><div class="tl-axis"><span>${t("hx.enter")}</span><span>${t("hx.leave")}</span></div>`;
    $("#takeaway").innerHTML = t(drop ? "hx.take.yes" : "hx.take");
    renderHeroArt();
  }

  // Half court with an animated shot, plus a sparkline of accuracy by consecutive minutes (real buckets up to ~12 min)
  function renderHeroArt() {
    const k = 7, cx = 190, base = 20, rimY = base + 5.25 * k;            // 7 px per foot
    const cornerY = rimY + Math.sqrt(23.75 ** 2 - 22 ** 2) * k, laneY = base + 19 * k;
    // deterministic scatter of made / missed shots
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    let dots = "";
    for (let i = 0; i < 46; i++) {
      const a = (rnd() - 0.5) * Math.PI * 0.76, r = (i % 3 === 0 ? 2 + rnd() * 6 : i % 3 === 1 ? 10 + rnd() * 8 : 23.5 + rnd() * 3) * k;
      const x = cx + Math.sin(a) * r, y = rimY + Math.cos(a) * r, made = rnd() < 0.47;
      dots += made ? `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.4" class="ha-made"/>`
        : `<path d="M${(x - 3).toFixed(1)} ${(y - 3).toFixed(1)}l6 6m0-6l-6 6" class="ha-miss"/>`;
    }
    const sx = cx + 25 * Math.sin(0.62) * k, sy = rimY + 25 * Math.cos(0.62) * k;   // shooter on the right wing
    const shot = `M${sx.toFixed(1)} ${sy.toFixed(1)} Q${(sx + 40).toFixed(1)} ${(rimY + 40).toFixed(1)} ${cx} ${rimY}`;

    // sparkline card
    const b = S.buckets.filter((r) => r.hi_edge <= 12), X0 = 40, X1 = 340, Y0 = 400, ys = 13;
    const px = (i) => X0 + (i + 0.5) * (X1 - X0) / b.length, py = (v) => Y0 - v * ys;
    const band = b.map((r, i) => `${px(i).toFixed(1)},${py(r.hi_pp).toFixed(1)}`).join(" ") + " " +
      b.slice().reverse().map((r, j) => `${px(b.length - 1 - j).toFixed(1)},${py(r.lo_pp).toFixed(1)}`).join(" ");
    const line = b.map((r, i) => `${i ? "L" : "M"}${px(i).toFixed(1)} ${py(r.effect_pp).toFixed(1)}`).join("");
    const pts = b.map((r, i) => `<circle cx="${px(i).toFixed(1)}" cy="${py(r.effect_pp).toFixed(1)}" r="4" class="${r.hi_pp < 0 ? "ha-cold" : "ha-pt"}"/>`).join("");
    const c0 = b[0];

    $("#hero-art").innerHTML = `<svg viewBox="0 0 380 470" role="img" aria-label="${esc(t("art.title"))}">
      <g class="ha-court">
        <rect x="15" y="${base}" width="350" height="280" class="ha-floor"/>
        <rect x="${cx - 56}" y="${base}" width="112" height="${laneY - base}" pathLength="1"/>
        <circle cx="${cx}" cy="${laneY}" r="42" pathLength="1"/>
        <path d="M${cx - 28} ${rimY} a28 28 0 0 0 56 0" pathLength="1"/>
        <path d="M${cx - 154} ${base} V${cornerY.toFixed(1)} A${23.75 * k} ${23.75 * k} 0 0 0 ${cx + 154} ${cornerY.toFixed(1)} V${base}" pathLength="1"/>
        <path d="M${cx - 42} 300 a42 42 0 0 1 84 0" pathLength="1"/>
      </g>
      ${dots}
      <line x1="${cx - 21}" y1="${base + 4 * k}" x2="${cx + 21}" y2="${base + 4 * k}" class="ha-board"/>
      <circle cx="${cx}" cy="${rimY}" r="6.5" class="ha-rim"/>
      <path id="ha-shot" d="${shot}" class="ha-arc"/>
      <circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="9" class="ha-shooter"/>
      ${matchMedia("(prefers-reduced-motion: reduce)").matches ? `<circle cx="${cx}" cy="${rimY}" r="6" class="ha-ball"/>`
        : `<circle r="6" class="ha-ball"><animateMotion dur="2.4s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.6;1" calcMode="linear"><mpath href="#ha-shot"/></animateMotion></circle>`}
      <g class="ha-card">
        <line x1="12" y1="322" x2="368" y2="322" class="ha-sep"/>
        <text x="28" y="343" class="ha-title">${esc(t("art.title"))}</text>
        <line x1="${X0}" y1="${Y0}" x2="${X1}" y2="${Y0}" class="ha-zero"/>
        <polygon points="${band}" class="ha-band"/>
        <path d="${line}" class="ha-line"/>
        ${pts}
        <text x="${px(0)}" y="${py(c0.lo_pp) + 16}" text-anchor="middle" class="ha-cold-t">${esc(t("art.cold"))}</text>
        <text x="${X1}" y="${Y0 - 26}" text-anchor="end" class="ha-flat">${esc(t("art.flat"))}</text>
        <text x="${X0}" y="448" class="ha-ax">${esc(t("art.enter"))}</text>
        <text x="${X1}" y="448" text-anchor="end" class="ha-ax">${esc(t("art.min", { m: b[b.length - 1].hi_edge }))}</text>
      </g>
    </svg>`;
  }

  /* ---------------- uses and benefits ---------------- */
  function renderUses() {
    const h = S.heterogeneity, c0 = coldRow("0–30 s");
    const b2b = (S.slopes.con_controles || []).find((r) => r.term === "b2b");
    const v = { mu: fmt(h.mu * 100, 2), long: S.long, c0: c0 ? fmt(c0.effect_pp, 1) : "—", b2b: b2b ? fmt(b2b.coef_pp, 2) : "—",
      f: S.n_flagged, n: S.n_contrast_players, mde: S.power.mde_pp.toFixed(0) };
    // [key, icon, tab, element to land on]; the simulator opens directly
    const yes = [["rot", "clock", "evidence", "chart-slopes"], ["entry", "arrow", "evidence", "chart-cold"], ["b2b", "clipboard", "evidence", "b2b-note"],
      ["label", "player", "player"], ["rival", "court", "evidence", "chart-defense"], ["sim", "cube", "sim"]];
    $("#uses-yes").innerHTML = yes.map(([k, ic, go, focus]) =>
      `<div class="use"><svg class="ic lead" aria-hidden="true"><use href="#i-${ic}"/></svg>` +
      `<h3>${t("u." + k + ".t")}</h3><p>${t("u." + k + ".d", v)}</p>` +
      (go === "sim" ? `<a class="btn" href="simulador/index.html">${t("u.go.method")}</a></div>`
        : `<button class="btn" data-go="${go}" data-from="uses"${focus ? ` data-focus="${focus}"` : ""}>${t("u.go." + go)}</button></div>`)).join("");
    $("#uses-no").innerHTML = ["live", "load", "other", "small", "long"]
      .map((k) => `<li>${icon("x")}<span>${t("u.no." + k, v)}</span></li>`).join("");
  }

  function renderCoach() {
    const hi = S.heterogeneity.mu_hi * 100;
    const c0 = coldRow("0–30 s");
    const cc = S.slopes.con_controles || [], b2b = cc.find((r) => r.term === "b2b"), home = cc.find((r) => r.term === "is_home");
    const ci = (r) => t("ci", { lo: fmt(r.lo_pp, 1), hi: fmt(r.hi_pp, 1) });
    const dropTxt = hi < 0 ? t("coach.drop") : t("coach.nodrop");
    const b2bTxt = b2b ? t("coach.b2b", { x: fmt(b2b.coef_pp, 2), ci: ci(b2b) }) + (b2b.hi_pp < 0 ? t("coach.b2b.small") : t("coach.b2b.unclear")) +
      (home ? t("coach.home", { x: fmt(home.coef_pp, 2) }) : "") : "";
    $("#coach").innerHTML =
      `<h3>${icon("clipboard")}${t("coach.title")}</h3><div class="coach-grid">` +
      `<div class="tag">${t("coach.data")}</div><div class="tag alt">${t("coach.try")}</div>` +
      `<p>${dropTxt}</p><p>${t("coach.try1")}</p>` +
      `<p>${c0 ? t("coach.cold", { x: Math.abs(c0.effect_pp).toFixed(1), ci: ci(c0) }) : t("coach.cold.generic")}</p><p>${t("coach.try2")}</p>` +
      `<p>${b2bTxt}</p><p>${t("coach.try3")}</p>` +
      `<p>${t("coach.power", { x: S.power.mde_pp.toFixed(0), n: S.seasons.length })}</p><p>${t("coach.try4")}</p></div>`;
  }

  function renderGlossary() {
    $("#glossary").innerHTML = `<summary>${icon("book")}${t("gl.title")}</summary><dl>` +
      ["pp", "ci", "xshot", "fe", "fdr", "placebo", "power"].map((k) => `<dt>${t("gl." + k + ".t")}</dt><dd>${t("gl." + k + ".d")}</dd>`).join("") + `</dl>`;
  }

  /* ---------------- summary ---------------- */
  function renderHero() {
    $("#season").textContent = t("season.label", { a: yy(S.seasons[0]), b: yy(S.seasons[S.seasons.length - 1]) });
    $("#hero-lede").textContent = t("hero.lede", { games: num(S.n_games), shots: num(S.n_shots), long: S.long, ref: REF() });
    const v = popVerdict(), h = S.heterogeneity;
    const c0 = coldRow("0–30 s");
    $("#hero-kpis").innerHTML =
      kpi(t("kpi.acc", { long: S.long }), fmt(h.mu * 100, 2) + " pp", t("kpi.acc.d", { lo: fmt(h.mu_lo * 100, 1), hi: fmt(h.mu_hi * 100, 1) }), v.cls === "alert" ? "bad" : "accent") +
      kpi(t("kpi.flag"), `${S.n_flagged} <small style="font-size:.5em;color:var(--muted)">${t("of")} ${S.n_contrast_players}</small>`, t("kpi.flag.d"), S.n_flagged ? "bad" : "") +
      kpi(t("kpi.cold"), c0 ? fmt(c0.effect_pp, 1) + " pp" : "—", c0 ? t("kpi.cold.d", { lo: fmt(c0.lo_pp, 1), hi: fmt(c0.hi_pp, 1) }) : "", "bad") +
      kpi(t("kpi.shots"), num(S.n_shots_analysis), t("kpi.shots.d", { games: num(S.n_games), players: num(S.n_players) }));
    renderSimple(); renderUses(); renderCoach(); renderGlossary(); renderCard();
    $("#verdict").className = "card verdict " + v.cls;
    $("#verdict").innerHTML = `<h3>${esc(v.title)} <span class="badge ${v.cls}">${esc(v.badge)}</span></h3><p>${v.text}</p>`;

    const b = S.buckets;
    const firstThin = b.findIndex((r) => r.n < 8000);
    $("#chart-pop-buckets").innerHTML = lineBand({
      pts: b.map((r, i) => ({ x: i, y: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp, tip: t("tip.bucket", { lo: r.lo_edge, hi: r.hi_edge, n: num(r.n), pp: fmt(r.effect_pp, 2) }) })),
      ticks: b.map((r, i) => ({ x: i, label: `${r.lo_edge}–${r.hi_edge >= 24 ? "24" : r.hi_edge}`, sub: num(r.n) })),
      xmin: -0.4, xmax: b.length - 0.6, hatchFrom: firstThin > 0 ? firstThin - 0.5 : null, hatchLabel: t("few.shots"),
      yTitle: t("ax.acc.vs.avg"), xTitle: t("ax.min.below"), errorBars: true, label: t("chart.pop"),
    });
    const pl = S.placebo, real = t("lg.real"), rnd = t("lg.random");
    $("#chart-placebo").innerHTML = groupedBars({
      groups: [
        { label: t("pl.naive"), bars: [{ v: pl.naive_real * 100, color: C.accent, name: real }, { v: pl.naive_placebo * 100, color: C.dim, name: rnd }] },
        { label: t("pl.infer"), bars: [{ v: pl.inference_real * 100, color: C.accent, name: real }, { v: pl.inference_placebo * 100, color: C.dim, name: rnd }] },
      ],
      max: 10, label: t("chart.placebo"),
    }) + `<div class="legend"><span><i style="background:${C.accent}"></i>${real}</span><span><i style="background:${C.dim}"></i>${t("lg.placebo")}</span><span>${t("pl.players", { n: pl.n_players })}</span></div>`;
  }

  /* ---------------- evidence ---------------- */
  function renderEvidence() {
    $("#chart-coverage").innerHTML = coverageBars({ rows: S.coverage, label: t("chart.cov") });
    const sl = S.slopes, b2b = (sl.con_controles || []).find((r) => r.term === "b2b");
    $("#b2b-note").textContent = b2b ? t("ev.b2b", { x: fmt(b2b.coef_pp, 2), lo: fmt(b2b.lo_pp, 2), hi: fmt(b2b.hi_pp, 2) }) + (b2b.hi_pp < 0 ? "." : t("coach.b2b.unclear")) : "";
    $("#chart-slopes").innerHTML = forest({
      rows: (S.robustness || []).map((r) => ({ label: tl(r.label), est: r.coef_pp, lo: r.lo_pp, hi: r.hi_pp, color: C.accent,
        tip: t("tip.slope", { n: num(r.n), c: fmt(r.coef_pp, 3), lo: fmt(r.lo_pp, 3), hi: fmt(r.hi_pp, 3) }) })),
      xTitle: t("ax.pp.per.min"), labelW: 330, label: t("chart.robust"),
    });
    $("#chart-seasons").innerHTML = forest({
      rows: (S.replication || []).map((r) => ({ label: t("season.n", { s: yy(r.season) }), est: r.mu_pp, lo: r.mu_lo_pp, hi: r.mu_hi_pp,
        color: r.mu_hi_pp < 0 ? C.bad : C.blue, tip: t("tip.season", { n: num(r.n), k: r.k }) })),
      xTitle: t("ax.long.minus.ref", { long: S.long, ref: REF() }), labelW: 150, label: t("chart.byseason"),
    });
    $("#chart-cold-seasons").innerHTML = forest({
      rows: (S.cold_by_season || []).filter((r) => r.effect_pp != null).map((r) => ({ label: t("season.n", { s: yy(r.season) }),
        est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp, color: r.hi_pp < 0 ? C.bad : C.blue, tip: t("tip.shots", { n: num(r.n) }) })),
      xTitle: t("ax.pp.red"), labelW: 150, label: t("chart.coldseason"),
    });
    const grp = { "Time since entering": t("cold.after"), "First minute: first appearance?": t("cold.first"), "First minute, by quarter": t("cold.first") };
    const cs = (S.cold_start || []).filter((r) => r.effect_pp != null);
    $("#chart-cold").innerHTML = forest({
      rows: cs.map((r) => ({ label: `${grp[r.group] || r.group} · ${tl(r.label)}`, est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp,
        color: r.hi_pp < 0 ? C.bad : C.blue, tip: t("tip.shots", { n: num(r.n) }) })),
      xTitle: t("ax.pp.red2"), labelW: 250, W: 1120, rowH: 30, label: t("chart.cold"),
    });
    const cq = (S.cold_start_quarter || [])[0];
    $("#cold-note").textContent = t("cold.note") + (cq && cq.effect_pp != null ? " " + t("cold.note2", { x: fmt(cq.effect_pp, 1), lo: fmt(cq.lo_pp, 1), hi: fmt(cq.hi_pp, 1) }) : "");
    $("#chart-zones").innerHTML = forest({
      rows: S.zone_slopes.map((z) => ({ label: zoneName(z.zone), est: z.coef_pp, lo: z.lo_pp, hi: z.hi_pp,
        color: z.q < 0.05 ? (z.coef_pp < 0 ? C.bad : C.good) : C.blue, tip: t("tip.zone", { n: num(z.n), q: z.q.toFixed(3) }) })),
      xTitle: t("ax.zone"), labelW: 170, label: t("chart.zone"),
    });
    $("#chart-metareg").innerHTML = forest({
      rows: S.metareg.map((m) => ({ label: tl(m.feature), est: m.coef_pp, lo: m.lo_pp, hi: m.hi_pp,
        color: m.q < 0.05 ? (m.coef_pp < 0 ? C.bad : C.good) : C.blue, tip: `q=${m.q.toFixed(3)}` })),
      xTitle: t("ax.metareg"), labelW: 230, label: t("chart.metareg"),
    });
    const h = S.heterogeneity;
    $("#het-text").innerHTML =
      `<p>${t("het.p1", { k: h.k, tau: (h.tau * 100).toFixed(2), i2: (h.I2 * 100).toFixed(0), p: h.p_het < 0.001 ? "&lt; 0.001" : "= " + h.p_het.toFixed(3) })}</p>` +
      `<p>${h.p_het > 0.05 ? t("het.none", { n: S.seasons.length }) : t("het.some")}</p>` +
      `<p>${t("het.flag", { f: S.n_flagged, n: S.n_contrast_players, e: Math.round(S.n_contrast_players * 0.05) })}</p>`;
  }

  /* ---------------- one-page coach card ---------------- */
  function renderCard() {
    const c0 = coldRow("0–30 s"), h = S.heterogeneity;
    const b2b = (S.slopes.con_controles || []).find((r) => r.term === "b2b");
    const rim = X && X.shot_type.find((r) => r.type === "Near the rim (paint)" && r.window === "0–30 s");
    const three = X && X.shot_type.find((r) => r.type === "Three-pointer" && r.window === "0–30 s");
    const mid = X && X.shot_type.find((r) => r.type === "Mid-range" && r.window === "0–30 s");
    const ftc = X && X.free_throws.cold[0];
    const fact = (cls, big, unit, l, d) =>
      `<div class="fact ${cls}"><div class="big">${big}<small>${unit}</small></div><div class="l">${l}</div><p>${d}</p></div>`;
    if (X) {
      const ci = X.impact.cold, bi = X.impact.b2b;
      $("#cc-impact").innerHTML =
        fact("bad", "−" + Math.abs(ci.total.pts).toFixed(0), " " + t("cc.pts.season"), t("cc.i1.l"),
          t("cc.i1.d", { lo: Math.abs(ci.total.hi).toFixed(0), hi: Math.abs(ci.total.lo).toFixed(0), w: Math.abs(ci.wins.pts).toFixed(1),
            g: Math.abs(ci.per_game.pts).toFixed(1) })) +
        fact("warn", "−" + Math.abs(bi.pts).toFixed(0), " " + t("cc.pts.season"), t("cc.i2.l"),
          t("cc.i2.d", { lo: Math.abs(bi.hi).toFixed(0), hi: Math.abs(bi.lo).toFixed(0), g: Math.abs(bi.per_b2b_game).toFixed(1) })) +
        fact("good", S.n_flagged, " " + t("of") + " " + S.n_contrast_players, t("cc.i3.l"), t("cc.i3.d", { mu: fmt(h.mu * 100, 2), long: S.long }));
    }
    const ci95 = (r) => t("ci", { lo: fmt(r.lo_pp, 1), hi: fmt(r.hi_pp, 1) });
    const h0 = H && H.cold_start["0–30 s"], bt = X && X.bench_time, sl = bt && bt.slope_pp_per_bench_min;
    const rows = [
      [t("cc.r1.f", { x: c0 ? fmt(c0.effect_pp, 1) : "—", ci: c0 ? ci95(c0) : "", ft: ftc ? fmt(ftc.effect_pp, 1) : "—" }),
        t(rim && three && mid ? "cc.r1.a" : "cc.r1.a.generic", { r: rim ? fmt(rim.effect_pp, 1) : "", tr: three ? fmt(three.effect_pp, 1) : "", m: mid ? fmt(mid.effect_pp, 1) : "" }),
        t(h0 ? "cc.r1.e.rep" : "cc.r1.e", { n: S.seasons.length, x: h0 ? fmt(h0.new, 2) : "", v: H ? t("verdict." + H.verdict) : "" })],
    ];
    if (sl) {
      const grows = sl.hi_pp < 0, flat = sl.lo_pp < 0 && sl.hi_pp > 0;
      rows.push([t(grows ? "cc.rb.f.grows" : flat ? "cc.rb.f.flat" : "cc.rb.f.shrinks",
        { x: fmt(sl.coef_pp, 2), ci: t("ci", { lo: fmt(sl.lo_pp, 2), hi: fmt(sl.hi_pp, 2) }) }),
        t(grows ? "cc.rb.a.grows" : "cc.rb.a.flat"), t("cc.rb.e", { n: num(sl.n) })]);
    }
    rows.push([t("cc.r2.f", { mu: fmt(h.mu * 100, 2), ci: t("ci", { lo: fmt(h.mu_lo * 100, 1), hi: fmt(h.mu_hi * 100, 1) }), long: S.long }), t("cc.r2.a"),
      t("cc.r2.e", { n: S.n_contrast_players })]);
    rows.push([t("cc.r3.f", { x: b2b ? fmt(b2b.coef_pp, 2) : "—", ci: b2b ? ci95(b2b) : "" }), t("cc.r3.a"), t("cc.r3.e")]);
    $("#cc-table").innerHTML = `<table><thead><tr><th>${t("cc.th.f")}</th><th>${t("cc.th.a")}</th><th>${t("cc.th.e")}</th></tr></thead><tbody>` +
      rows.map(([f, a, e]) => `<tr><td>${f}</td><td>${a}</td><td>${e}</td></tr>`).join("") + `</tbody></table>`;
    $("#cc-note").textContent = t("cc.note", { ppw: X ? X.impact.points_per_win : 30 });
  }

  /* ---------------- extra analyses (impact, shot type, free throws, selection) ---------------- */
  function renderExtra() {
    if (!X) { ["#chart-impact", "#chart-shot-type", "#chart-ft", "#chart-selection"].forEach((s) => $(s).closest(".card").classList.add("hidden")); return; }
    const ic = X.impact.cold, bi = X.impact.b2b;
    $("#chart-impact").innerHTML = forest({
      rows: ic.buckets.map((b) => ({ label: t("x.imp.cold", { b: tl(b.label) }), est: b.pts, lo: b.lo, hi: b.hi, color: C.bad,
        tip: t("x.imp.tip", { n: Math.round(b.shots_per_team_season) }) }))
        .concat([{ label: t("x.imp.total"), est: ic.total.pts, lo: ic.total.lo, hi: ic.total.hi, color: C.court },
          { label: t("x.imp.b2b"), est: bi.pts, lo: bi.lo, hi: bi.hi, color: C.maple }]),
      xTitle: t("ax.pts.season"), labelW: 220, label: t("e.x1.t"),
    });
    $("#impact-note").textContent = t("x.imp.note", { ppw: X.impact.points_per_win, f: Math.abs(ic.formula_pts).toFixed(0),
      w: Math.abs(ic.wins.pts).toFixed(1), wlo: Math.abs(ic.wins.hi).toFixed(1), whi: Math.abs(ic.wins.lo).toFixed(1) });

    $("#chart-shot-type").innerHTML = forest({
      rows: X.shot_type.filter((r) => r.window === "0–30 s" || r.window === "0–2 min").map((r) => ({ label: `${tl(r.type)} · ${tl(r.window)}`, est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp,
        color: r.q < 0.05 ? C.bad : C.blue, tip: t("tip.shots", { n: num(r.n) }) + ` · q=${r.q.toFixed(4)}` })),
      xTitle: t("ax.pp.red2"), labelW: 230, label: t("e.x2.t"),
    });
    $("#shot-type-note").textContent = t("x.type.note");

    const ft = X.free_throws;
    $("#chart-ft").innerHTML = forest({
      rows: ft.cold.filter((r) => r.effect_pp != null && !/reference/.test(r.label)).map((r) => ({ label: t("x.ft.cold", { b: tl(r.label) }),
        est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp, color: r.hi_pp < 0 ? C.bad : C.blue, tip: t("tip.shots", { n: num(r.n) }) }))
        .concat([{ label: t("x.ft.long", { long: S.long, ref: REF() }), est: ft.contrast.effect_pp, lo: ft.contrast.lo_pp, hi: ft.contrast.hi_pp,
          color: ft.contrast.hi_pp < 0 ? C.bad : C.blue, tip: t("tip.shots", { n: num(ft.contrast.n) }) }]),
      xTitle: t("ax.pp.red2"), labelW: 230, label: t("e.x3.t"),
    });
    $("#ft-note").textContent = t("x.ft.note", { n: num(ft.n), p: (ft.ft_pct * 100).toFixed(1) });

    const sel = X.selection, win = (g, far) => (sel.by_window || []).find((r) => r.group === g && /more than/.test(r.window) === far);
    const srows = [["all", sel.all], ["exo", sel.exogenous], ["coach", sel.coach], ["coach.far", win("coach", true)], ["coach.near", win("coach", false)]];
    $("#chart-selection").innerHTML = forest({
      rows: srows.filter(([, r]) => r).map(([k, r]) => ({ label: t("x.sel." + k, { m: sel.end_window_min }), est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp,
        color: r.hi_pp < 0 ? C.bad : r.lo_pp > 0 ? C.good : C.blue, tip: t("tip.shots", { n: num(r.n) }) })),
      xTitle: t("ax.long.minus.ref", { long: S.long, ref: REF() }), labelW: 260, label: t("e.x4.t"),
    });
    $("#selection-note").textContent = t("x.sel.note", { m: sel.end_window_min });

    const bt = X.bench_time;
    if (bt) {
      $("#chart-bench").innerHTML = forest({
        rows: bt.buckets.filter((r) => r.effect_30s_pp != null).map((r) => ({ label: tl(r.label), est: r.effect_30s_pp, lo: r.lo_30s_pp, hi: r.hi_30s_pp,
          color: r.q < 0.05 && r.hi_30s_pp < 0 ? C.bad : C.blue, tip: t("tip.shots", { n: num(r.n_30s) }) + ` · q=${r.q.toFixed(3)}` })),
        xTitle: t("ax.pp.red2"), labelW: 230, W: 1120, rowH: 30, label: t("e.b.t"),
      });
      const sl = bt.slope_pp_per_bench_min;
      $("#bench-note").textContent = t("x.bench.note", { x: fmt(sl.coef_pp, 3), lo: fmt(sl.lo_pp, 3), hi: fmt(sl.hi_pp, 3), n: num(sl.n) });
    } else $("#chart-bench").closest(".card").classList.add("hidden");
  }

  /* ---------------- preregistered replication (2025-26) ---------------- */
  function renderHoldout() {
    if (!H) { $("#holdout-card").classList.add("hidden"); return; }
    const rows = [];
    Object.entries(H.cold_start).forEach(([w, r]) => {
      rows.push({ label: t("h.row.frozen", { w: tl(w) }), est: r.frozen, lo: r.frozen_ci95[0], hi: r.frozen_ci95[1], color: C.dim, tip: "2021-25" });
      rows.push({ label: t("h.row.new", { w: tl(w) }), est: r.new, lo: r.ci95[0], hi: r.ci95[1], color: r.ci95[1] < 0 ? C.bad : C.blue,
        tip: t("tip.shots", { n: num(r.n) }) });
    });
    const f = H.fatigue_8plus_vs_2_6;
    rows.push({ label: t("h.row.ffrozen", { long: S.long }), est: f.frozen, lo: f.frozen_ci95[0], hi: f.frozen_ci95[1], color: C.dim, tip: "2021-25" });
    rows.push({ label: t("h.row.fnew", { long: S.long }), est: f.new, lo: f.ci95[0], hi: f.ci95[1], color: C.blue, tip: t("tip.players", { n: f.players }) });
    $("#chart-holdout").innerHTML = forest({ rows, xTitle: t("ax.pp.red2"), labelW: 300, W: 1120, rowH: 28, label: t("e.h.t") });
    $("#holdout-note").innerHTML = t("h.note", { v: t("verdict." + H.verdict), hash: H.preregistration_commit.slice(0, 7),
      date: H.preregistration_date.slice(0, 10), games: num(H.games), shots: num(H.shots) });
  }

  /* ---------------- bench calculator ---------------- */
  const calcState = { sit: "re", type: "three" };
  function initCalc() {
    if (!X || !X.bench_time) { $("#tool-calc").innerHTML = `<p class="note">${t("calc.none")}</p>`; return; }
    $("#calc-player").innerHTML = P.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.team)}</option>`).join("");
    ["calc-player", "calc-rival"].forEach((id) => $("#" + id).addEventListener("change", renderCalc));
    ["bench", "sec"].forEach((k) => $("#calc-" + k).addEventListener("input", () => { $("#calc-" + k + "-v").textContent = $("#calc-" + k).value; renderCalc(); }));
    document.addEventListener("click", (e) => {
      const b = e.target.closest("#calc-sit button, #calc-type button");
      if (!b) return;
      calcState[b.parentElement.id === "calc-sit" ? "sit" : "type"] = b.dataset.v;
      renderCalc();
    });
    renderCalc();
  }
  async function renderCalc() {
    if (!X || !X.bench_time) return;
    const segBtns = (opts, cur) => opts.map((v) => `<button type="button" data-v="${v}" class="${v === cur ? "on" : ""}">${t("calc.opt." + v)}</button>`).join("");
    $("#calc-sit").innerHTML = segBtns(["re", "first", "half"], calcState.sit);
    $("#calc-type").innerHTML = segBtns(["three", "mid", "rim"], calcState.type);
    $("#calc-bench-f").classList.toggle("hidden", calcState.sit !== "re");
    const rv = $("#calc-rival").value;
    $("#calc-rival").innerHTML = `<option value="">${t("calc.rival.none")}</option>` +
      (DEFR ? DEFR.teams.map((x) => `<option value="${esc(x.team)}">${esc(x.team)}</option>`).join("") : "");
    $("#calc-rival").value = rv;
    const pid = +$("#calc-player").value, pl = P.find((p) => p.id === pid);
    if (!shotCache[pid]) shotCache[pid] = await fetch(`data/shots/${pid}.json`).then((r) => r.json());
    if (+$("#calc-player").value !== pid) return;
    const base = CALC.playerBase(shotCache[pid], CALC.leagueFg(S));
    const rival = rv && DEFR ? DEFR.teams.find((x) => x.team === rv) : null;
    const sec = +$("#calc-sec").value, benchMin = +$("#calc-bench").value, c0 = coldRow("0–30 s");
    const args = { base, X, overall30: c0.effect_pp, situation: calcState.sit, benchMin, sec, rival };
    const r = CALC.predict({ ...args, type: calcState.type });
    const pc = (v) => (v * 100).toFixed(1) + "%", pp = (v) => fmt(v, 1) + " pp";
    const row = (l, v) => `<tr><td>${l}</td><td>${v}</td></tr>`;
    const alt = Object.keys(CALC.TYPES).map((k) => ({ k, cold: CALC.coldTerm(X, k, sec).pp }));
    const best = alt.reduce((a, b) => (b.cold > a.cold ? b : a));
    const mine = alt.find((a) => a.k === calcState.type);
    let rec;
    if (!r.window) rec = t("calc.rec.warm");
    else if (best.k !== calcState.type && best.cold - mine.cold >= 0.5)
      rec = t("calc.rec.switch", { s: sec, type: t("calc.opt." + calcState.type), x: fmt(mine.cold, 1), alt: t("calc.opt." + best.k), y: fmt(best.cold, 1) });
    else rec = t("calc.rec.keep", { s: sec, x: fmt(mine.cold, 1) });
    $("#calc-out").innerHTML =
      `<div class="big">${pc(r.p)}<small>${t("calc.prob")}</small></div>` +
      `<p class="sub">${t("calc.ci", { lo: pc(r.lo), hi: pc(r.hi) })} · ${esc(pl ? pl.name : "")}, ${t("calc.opt." + calcState.type)}</p>` +
      `<table class="calc-break">` +
      row(t("calc.part.base", { n: base[calcState.type].n }), pc(r.parts.base)) +
      row(t("calc.part.rival"), rival ? pp(r.parts.rival) : "—") +
      row(t("calc.part.cold", { w: r.window ? tl(r.window) : t("calc.none.window") }), pp(r.parts.cold)) +
      row(t("calc.part.bench"), r.window === "0–30 s" ? pp(r.parts.bench) : "—") + `</table>` +
      `<p class="calc-rec">${rec}</p>`;
  }

  /* ---------------- team audit ---------------- */
  const auditSort = { key: "pts", dir: -1 };
  function initAudit() {
    if (!X || !X.team_audit) { $("#audit").innerHTML = `<p class="note">${t("calc.none")}</p>`; return; }
    const seasons = Array.from(new Set(X.team_audit.rows.map((r) => r.season))).sort();
    $("#audit-season").innerHTML = seasons.map((s) => `<option value="${s}">${yy(s)}</option>`).join("");
    $("#audit-season").value = seasons[seasons.length - 1];
    $("#audit-season").addEventListener("change", renderAudit);
    $("#audit-table").addEventListener("click", (e) => {
      const th = e.target.closest("th[data-k]");
      if (!th) return;
      auditSort.dir = auditSort.key === th.dataset.k ? -auditSort.dir : -1;
      auditSort.key = th.dataset.k;
      renderAudit();
    });
    renderAudit();
  }
  function renderAudit() {
    if (!X || !X.team_audit) return;
    const A = X.team_audit, sea = $("#audit-season").value;
    const rows = A.rows.filter((r) => r.season === sea).sort((a, b) => auditSort.dir * (a[auditSort.key] < b[auditSort.key] ? -1 : a[auditSort.key] > b[auditSort.key] ? 1 : 0));
    // a position only means something if teams really differ (tau > 0); otherwise it would rank noise
    const real = (A.tau_by_season[sea] || 0) > 0;
    const cols = [["team", t("au.col.team")], ["pts", t("au.col.pts")], ["shrunk", t("au.col.shrunk")], ["jump_share", t("au.col.jump")]]
      .concat(real ? [["rank", t("au.col.rank")]] : []);
    $("#audit-table").innerHTML = `<table><thead><tr>` +
      cols.map(([k, l]) => `<th data-k="${k}"${auditSort.key === k ? ` aria-sort="${auditSort.dir > 0 ? "ascending" : "descending"}"` : ""}>${l}</th>`).join("") +
      `</tr></thead><tbody>` + rows.map((r) => `<tr><td>${esc(r.team)}</td>` +
        `<td class="num">${fmt(r.pts, 1)} <span class="muted">(${fmt(r.lo, 0)} ${t("to")} ${fmt(r.hi, 0)})</span></td>` +
        `<td class="num">${fmt(r.shrunk, 1)}</td><td class="num">${(r.jump_share * 100).toFixed(0)}%</td>${real ? `<td class="num">${r.rank}</td>` : ""}</tr>`).join("") +
      `</tbody></table>`;
    const byShrunk = A.rows.filter((r) => r.season === sea).sort((a, b) => b.shrunk - a.shrunk);
    $("#chart-audit").innerHTML = forest({
      rows: byShrunk.map((r) => ({ label: r.team, est: r.pts, lo: r.lo, hi: r.hi, color: r.hi < 0 ? C.bad : r.lo > 0 ? C.good : C.blue,
        tip: t("au.tip", { s: fmt(r.shrunk, 1), n: num(r.n_cold) }) })),
      W: 1120, rowH: 22, labelW: 230, xTitle: t("ax.pts.season"), label: t("au.chart.t"),
    });
    $("#audit-note").textContent = t((A.tau_by_season[sea] || 0) > 0 ? "au.note.real" : "au.note.noise", { lg: (A.league_jump_share * 100).toFixed(0), r: A.corr_jump_share_pts.toFixed(2),
      tau: (A.tau_by_season[sea] || 0).toFixed(1) });
  }

  /* ---------------- team defense ---------------- */
  function renderDefense() {
    const box = $("#chart-defense");
    if (!DEFR) { box.innerHTML = `<svg viewBox="0 0 640 120"><text class="empty" x="320" y="60" text-anchor="middle">${esc(t("def.none"))}</text></svg>`; return; }
    box.innerHTML = forest({
      rows: DEFR.teams.map((x) => ({ label: x.team, est: x.effect_pp, lo: x.lo_pp, hi: x.hi_pp,
        color: x.hi_pp < 0 ? C.good : x.lo_pp > 0 ? C.bad : C.blue,
        tip: t("tip.def", { n: num(x.n), pp: fmt(x.effect_pp, 2), lo: fmt(x.lo_pp, 2), hi: fmt(x.hi_pp, 2) }) })),
      W: 1120, rowH: 22, labelW: 230, xTitle: t("ax.def"), label: t("chart.def"),
    });
    $("#def-ev-note").textContent = t("def.note", { s: yy(DEFR.season), r: DEFR.stability_r.map((v) => v.toFixed(2)).join(", ") });
  }

  /* ---------------- player ---------------- */
  function fillPlayers(keepId) {
    const team = $("#team-sel").value;
    const list = P.filter((p) => team === "all" || p.team === team);
    $("#player-sel").innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.name)} · ${t("n.shots", { n: num(p.n) })}</option>`).join("");
    if (!list.length) return;
    const id = keepId && list.some((p) => p.id === keepId) ? keepId : list[0].id;
    selectPlayer(id);
  }
  function fillTeams() {
    const teams = Array.from(new Set(P.map((p) => p.team))).sort(), prev = $("#team-sel").value || "all";
    $("#team-sel").innerHTML = `<option value="all">${t("all.teams")}</option>` + teams.map((x) => `<option>${esc(x)}</option>`).join("");
    $("#team-sel").value = teams.includes(prev) ? prev : "all";
  }
  function initPlayerControls() {
    fillTeams();
    $("#team-sel").addEventListener("change", () => fillPlayers());
    $("#player-sel").addEventListener("change", (e) => selectPlayer(+e.target.value));
    ["short", "long"].forEach((k) => $("#" + k + "-rng").addEventListener("input", () => {
      $("#" + k + "-v").textContent = $("#" + k + "-rng").value; renderCourts();
    }));
    fillPlayers();
  }
  function playerVerdict(p) {
    const c = p.contrast;
    if (!c) return { cls: "warn", badge: t("pv.few.badge"), title: t("pv.few.title"), text: t("pv.few.text", { ref: REF(), long: S.long }) };
    const range = t("range.pp", { lo: fmt(c.lo_pp, 1), hi: fmt(c.hi_pp, 1) });
    if (c.flag) return { cls: "alert", badge: t("pv.flag.badge"), title: t("pv.flag.title", { long: S.long }),
      text: t("pv.flag.text", { x: fmt(c.effect_pp, 1), range, long: S.long }) };
    return { cls: "ok", badge: t("pv.none.badge"), title: t("pv.none.title"),
      text: t("pv.none.text", { x: fmt(c.effect_pp, 1), range, n: num(c.n_l), mde: (2.8 * c.se_pp).toFixed(0) }) };
  }
  async function selectPlayer(id) {
    cur = P.find((p) => p.id === id);
    if (!cur) return;
    $("#player-sel").value = String(id);
    const c = cur.contrast, v = playerVerdict(cur);
    $("#player-head").innerHTML =
      `<img class="photo" src="https://cdn.nba.com/headshots/nba/latest/1040x760/${cur.id}.png" alt="" onerror="this.style.display='none'">` +
      `<div><h2>${esc(cur.name)}</h2><div class="meta">${esc(cur.team)} · ${t("n.analyzed", { n: num(cur.n) })}</div></div>` +
      `<img class="logo" src="https://cdn.nba.com/logos/nba/${cur.team_id}/primary/L/logo.svg" alt="" onerror="this.style.display='none'">`;
    $("#player-kpis").innerHTML =
      kpi(t("pk.fg"), pct(cur.fg), t("pk.fg.d", { x: pct(cur.xfg) })) +
      kpi(t("pk.eff", { long: S.long, ref: REF() }), c ? fmt(c.effect_pp, 1) + " pp" : "—", c ? t("ci95", { lo: fmt(c.lo_pp, 1), hi: fmt(c.hi_pp, 1) }) : t("pk.few"), c && c.flag ? "bad" : "accent") +
      kpi(t("pk.long"), c ? num(c.n_l) : "—", c ? t("pk.long.d", { n: num(c.n_s) }) : "") +
      kpi(t("pk.shrunk"), c ? fmt(c.shrunk_pp, 1) + " pp" : "—", t("pk.shrunk.d"));
    $("#player-verdict").className = "card verdict " + v.cls;
    $("#player-verdict").innerHTML = `<h3>${esc(v.title)} <span class="badge ${v.cls}">${esc(v.badge)}</span></h3><p>${v.text}</p>`;

    const b = cur.buckets;
    $("#chart-player-buckets").innerHTML = lineBand({
      pts: b.map((r, i) => ({ x: i, y: r.n >= 30 ? r.dev_pp : null, lo: r.lo_pp, hi: r.hi_pp,
        tip: t("tip.pb", { lo: r.lo, hi: r.hi, n: r.n, fg: r.fg != null ? pct(r.fg) : "—", xfg: r.xfg != null ? pct(r.xfg) : "—" }) })),
      ticks: b.map((r, i) => ({ x: i, label: `${r.lo}–${r.hi >= 24 ? "24" : r.hi}`, sub: "n=" + r.n })),
      xmin: -0.4, xmax: b.length - 0.6, yTitle: t("ax.vs.avg"), xTitle: t("ax.min.omit"), errorBars: true,
      emptyMsg: t("empty.curve"), label: t("chart.player"),
    });
    if (c) {
      const se2 = (c.se_pp / 100) ** 2, tau2 = S.heterogeneity.tau2, B = se2 / (tau2 + se2);
      const sd = Math.sqrt((tau2 * se2) / (tau2 + se2) + B * B * S.heterogeneity.se_mu ** 2) * 100;
      $("#chart-player-contrast").innerHTML = forest({
        rows: [
          { label: t("ct.direct"), est: c.effect_pp, lo: c.lo_pp, hi: c.hi_pp, color: C.accent, tip: t("ct.direct.tip") },
          { label: t("ct.shrunk"), est: c.shrunk_pp, lo: c.shrunk_pp - 1.96 * sd, hi: c.shrunk_pp + 1.96 * sd, color: C.blue, tip: t("ct.shrunk.tip") },
          { label: t("ct.league"), est: S.heterogeneity.mu * 100, lo: S.heterogeneity.mu_lo * 100, hi: S.heterogeneity.mu_hi * 100, color: C.dim, tip: t("ct.league.tip") },
        ],
        xTitle: t("ax.long.minus.ref", { long: S.long, ref: REF() }), labelW: 150, label: t("chart.contrast"),
      });
    } else {
      $("#chart-player-contrast").innerHTML = `<svg viewBox="0 0 640 140"><text class="empty" x="320" y="70" text-anchor="middle">${esc(t("empty.contrast"))}</text></svg>`;
    }
    if (!shotCache[id]) {
      try { shotCache[id] = await fetch(`data/shots/${id}.json`).then((r) => r.json()); } catch (e) { shotCache[id] = null; }
    }
    renderCourts();
  }
  function renderCourts() {
    if (!cur) return;
    const d = shotCache[cur.id], box = $("#courts");
    if (!d) { box.innerHTML = `<p class="note">${t("courts.err")}</p>`; return; }
    const sh = +$("#short-rng").value, lg = +$("#long-rng").value, fresh = [], tired = [];
    for (let i = 0; i < d.x.length; i++) {
      if (d.i[i]) continue;
      const st = d.s[i] / 10, s = { x: d.x[i], y: d.y[i], m: d.m[i] };
      if (st < sh) fresh.push(s); else if (st >= lg) tired.push(s);
    }
    const stat = (a) => (a.length ? t("courts.stat", { fg: pct(a.reduce((x, s) => x + s.m, 0) / a.length), n: a.length }) : t("courts.none"));
    box.innerHTML =
      `<div class="court-box"><h4>${t("courts.rested", { x: sh })}</h4><div class="stat">${stat(fresh)}</div>${court(fresh, t("chart.court"))}</div>` +
      `<div class="court-box"><h4>${t("courts.tired", { x: lg })}</h4><div class="stat">${stat(tired)}</div>${court(tired, t("chart.court"))}</div>`;
  }

  /* ---------------- new player ---------------- */
  function initNew() {
    $("#mix-sliders").innerHTML = ZONES.map((z, i) => {
      const def = Math.round((S.zone_share[z] || 0) * 100);
      return `<div class="mix-row"><label for="mx-${i}"><span></span></label>` +
        `<input type="range" id="mx-${i}" min="0" max="60" step="1" value="${def}" data-zone="${esc(z)}"><output>${def}%</output></div>`;
    }).join("");
    $$(".sv").forEach((e) => (e.textContent = `${S.short_lo}–${S.short}`));
    $$(".lv").forEach((e) => (e.textContent = S.long));
    $$("#tool-new input").forEach((i) => i.addEventListener("input", renderNew));
    renderNew();
  }
  function renderNew() {
    const rows = $$("#mix-sliders input");
    rows.forEach((r) => { r.previousElementSibling.firstElementChild.textContent = zoneName(r.dataset.zone); });
    const raw = rows.map((r) => +r.value), tot = raw.reduce((a, b) => a + b, 0) || 1;
    rows.forEach((r, i) => { r.nextElementSibling.textContent = Math.round((raw[i] / tot) * 100) + "%"; });
    const skill = +$("#skill-rng").value;
    $("#skill-v").textContent = (skill >= 0 ? "+" : "") + skill.toFixed(1);
    const base = ZONES.reduce((a, z, i) => a + (raw[i] / tot) * (S.zone_fg[z] || 0), 0) + skill / 100;

    const h = S.heterogeneity;
    let mu = h.mu, v = h.tau2 + h.se_mu ** 2, usedOwn = false;
    const ns = +$("#own-ns").value, ms = Math.min(+$("#own-ms").value, ns), nl = +$("#own-nl").value, ml = Math.min(+$("#own-ml").value, nl);
    if (ns > 0 && nl > 0) {
      const ps = ms / ns, pl = ml / nl, ov = Math.max(ps * (1 - ps), 0.01) / ns + Math.max(pl * (1 - pl), 0.01) / nl, prec = 1 / v + 1 / ov;
      mu = (h.mu / v + (pl - ps) / ov) / prec; v = 1 / prec; usedOwn = true;
    }
    const half = 1.96 * Math.sqrt(v), lo = mu - half, hi = mu + half;
    const long = base + mu;
    $("#proj-kpis").innerHTML =
      kpi(t("nk.rested"), pct(base), t("nk.rested.d", { x: (skill >= 0 ? "+" : "") + skill.toFixed(1) })) +
      kpi(t("nk.proj", { long: S.long }), pct(long), t("ci95", { lo: pct(base + lo), hi: pct(base + hi) }), "accent") +
      kpi(t("nk.eff"), fmt(mu * 100, 2) + " pp", t("nk.eff.d", { lo: fmt(lo * 100, 1), hi: fmt(hi * 100, 1) }), lo > 0 || hi < 0 ? "bad" : "");
    const B = base * 100, E = mu * 100, L = lo * 100, H = hi * 100;
    const pts = [{ x: 0, y: B, lo: B, hi: B }, { x: S.short, y: B, lo: B, hi: B }, { x: S.long, y: B + E, lo: B + L, hi: B + H }, { x: 12, y: B + E, lo: B + L, hi: B + H }]
      .map((p) => ({ ...p, tip: `${p.y.toFixed(1)}% (${p.lo.toFixed(1)}–${p.hi.toFixed(1)})` }));
    $("#chart-projection").innerHTML = lineBand({
      pts, xmin: 0, xmax: 24, ticks: [0, 4, 8, 12, 16, 20, 24].map((x) => ({ x, label: x + "'" })),
      hatchFrom: 12, hatchLabel: t("no.data.extrap"), includeZero: false, yTitle: t("ax.proj"), xTitle: t("ax.min.court"), label: t("chart.proj"),
    });
    $("#proj-note").innerHTML = (usedOwn ? t("proj.own") : t("proj.noown", { tau: (h.tau * 100).toFixed(2) })) + " " + t("proj.limit") + " " + t("proj.profile") + " " +
      (S.metareg.some((r) => r.q < 0.05) ? t("proj.meta.some") : t("proj.meta.none"));
  }

  /* ---------------- method ---------------- */
  function qualityHtml() {
    if (!QUAL) return "";
    const Q = QUAL.seasons, f = QUAL.funnel;
    const row = (name, fn) => `<tr><td>${name}</td>${Q.map((q) => `<td>${fn(q)}</td>`).join("")}</tr>`;
    return `<h3>${t("q.title")}</h3><p>${t("q.intro", { n: Q.length })}</p>
      <table><thead><tr><th>${t("q.step")}</th><th>${t("q.shots")}</th><th>${t("q.lost")}</th></tr></thead><tbody>
      ${f.map((x) => `<tr><td>${t("q.step." + x.step)}</td><td>${num(x.n)}</td><td>${num(x.lost)}</td></tr>`).join("")}</tbody></table>
      <table><thead><tr><th>${t("q.check")}</th>${Q.map((q) => `<th>${esc(q.label)}</th>`).join("")}</tr></thead><tbody>
      ${row(t("q.missing"), (q) => t("q.missing.v", { d: num(q.duplicates), m: q.missing_any_pct }))}
      ${row(t("q.coord"), (q) => num(q.coord_vs_dist_gt3ft))}
      ${row(t("q.match"), (q) => q.games_match_exact_pct.toFixed(1) + "%")}
      ${row(t("q.inferred"), (q) => q.inferred_pct + "%")}
      ${row(t("q.over"), (q) => num(q.game_minutes_gt_possible))}
      </tbody></table>
      <p>${t("q.outro")}</p>`;
  }

  function renderMethod() {
    const x = S.xshot || {}, m = x[x.chosen] || {}, bl = x.baseline_log_loss, ho = x.temporal_holdout;
    const first = S.seasons[0], last = S.seasons[S.seasons.length - 1];
    $("#method-text").innerHTML = `
      <h3>${t("m.q.h")}</h3>
      <p>${t("m.q.p")}</p>
      <h3>${t("m.data.h")}</h3>
      <p>${t("m.data.main", { season: t("season.label", { a: yy(first), b: yy(last) }), games: num(S.n_games), shots: num(S.n_shots) })}</p>
      ${CONT ? `<p>${t("m.data.def")}</p>` : ""}
      ${qualityHtml()}
      <h3>${t("m.s1.h")}</h3>
      <ul>
        <li>${t("m.s1.a")}</li>
        <li>${t("m.s1.b")}</li>
        <li>${t("m.s1.c", { x: pct(S.n_inferred / S.n_shots, 2) })}</li>
        <li>${t("m.s1.d")}</li>
      </ul>
      <h3>${t("m.s2.h")}</h3>
      <p>${t("m.s2.p")} ${t("m.s2.val", { v: esc(x.validation || "") })}
      ${m.log_loss ? t("m.s2.model", { name: esc(x.chosen), ll: m.log_loss.toFixed(4), bl: bl.toFixed(4), auc: m.auc.toFixed(3), ece: (m.ece * 100).toFixed(2) }) : ""}
      ${ho ? "<br>" + t("m.s2.temporal", { s: yy(ho.test_season), n: num(ho.n_test), ll: ho[x.chosen].log_loss.toFixed(4), bl: ho.baseline_log_loss.toFixed(4), auc: ho[x.chosen].auc.toFixed(3), ece: (ho[x.chosen].ece * 100).toFixed(2) }) : ""}</p>
      <h3>${t("m.s3.h")}</h3>
      <ul>
        <li>${t("m.s3.a")}</li>
        <li>${t("m.s3.b", { long: S.long, lo: S.short_lo, short: S.short })}</li>
        <li>${t("m.s3.c")}</li>
        <li>${t("m.s3.d")}</li>
        <li>${t("m.s3.e")}</li>
        <li>${t("m.s3.f")}</li>
      </ul>
      <h3>${t("m.s4.h")}</h3>
      <p>${t("m.s4.p")}</p>
      <h3>${t("m.s5.h")}</h3>
      <ul>
        <li>${t("m.s5.a")}</li>
        <li>${t("m.s5.b", { nb: CONT ? CONT.n_boot : 24 })}</li>
        <li>${t("m.s5.c")}</li>
      </ul>
      <h3>${t("m.lim.h")}</h3>
      <ul>
        <li>${t("m.lim.a")}</li>
        <li>${t("m.lim.b")} ${CONT && CONT.gap ? t("m.lim.b2", { a0: CONT.gap.rows[0].auc.toFixed(3), a1: CONT.gap.rows[1].auc.toFixed(3), a2: CONT.gap.rows[2].auc.toFixed(3) }) : ""}</li>
        <li>${t("m.lim.c")}</li>
        <li>${t("m.lim.d", { n: S.seasons.length, a: yy(first), b: yy(last) })}</li>
        <li>${t("m.lim.e", { se: S.power.median_se_pp.toFixed(1), mde: S.power.mde_pp.toFixed(0) })}</li>
        <li>${t("m.lim.f", { lo: S.short_lo, short: S.short, long: S.long })}</li>
        <li>${t("m.lim.g", { n: S.seasons.length })}</li>
      </ul>`;
  }

  /* ---------------- (re)render ---------------- */
  function renderAll() {
    renderHero(); renderEvidence(); renderExtra(); renderHoldout(); renderDefense(); renderMethod(); renderNew(); renderCalc(); renderAudit();
  }
  function onLang() {
    if (!ready) return;
    renderAll();
    fillTeams();
    fillPlayers(cur && cur.id);
  }
  function init() {
    renderHero(); renderEvidence(); renderExtra(); renderHoldout(); renderDefense(); initPlayerControls(); initCalc(); initAudit();
    $("#print-card").addEventListener("click", () => window.print()); initNew(); renderMethod();
    ready = true;
    window.I18N.onChange(onLang);
    show(location.hash.slice(1) || "summary");
  }
  bindTabs();
  apply();
  load();
})();
