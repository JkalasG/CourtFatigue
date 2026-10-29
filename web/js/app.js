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
    } catch (e) {
      const box = $("#load-error");
      box.classList.remove("hidden");
      box.innerHTML = t("err.load");
      return;
    }
    init();
  }

  /* ---------------- tabs ---------------- */
  function show(tab) {
    if (!$("#" + tab)) tab = "summary";
    $$(".pane").forEach((p) => p.classList.toggle("on", p.id === tab));
    $$("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    if (location.hash !== "#" + tab) history.replaceState(null, "", "#" + tab);
    window.scrollTo({ top: 0 });
  }
  function bindTabs() {
    $$("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
    document.addEventListener("click", (e) => { const g = e.target.closest("[data-go]"); if (g) show(g.dataset.go); });
    window.addEventListener("hashchange", () => show(location.hash.slice(1)));
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
    $("#hx-sub").textContent = t("hx.sub", { shots: num(S.n_shots), games: num(S.n_games), long: S.long });

    const fact = (cls, big, unit, l, d) =>
      `<div class="fact ${cls}"><div class="big">${big}<small>${unit}</small></div><div class="l">${l}</div><p>${d}</p></div>`;
    $("#facts").innerHTML =
      fact(S.n_flagged ? "bad" : "good", S.n_flagged, " " + t("of") + " " + S.n_contrast_players, t("hx.f1.l"),
        t(S.n_flagged ? "hx.f1.d.some" : "hx.f1.d")) +
      (c0 ? fact("bad", fmt(c0.effect_pp, 1), " " + t("hx.pts"), t("hx.f2.l"), t("hx.f2.d")) : "") +
      (b2b ? fact("warn", fmt(b2b.coef_pp, 1), " " + t("hx.pts"), t("hx.f3.l"),
        t("hx.f3.d") + (home ? " " + t("hx.f3.home", { x: fmt(home.coef_pp, 1) }) : "")) : "");

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
        <rect x="15" y="${base}" width="350" height="280" rx="4"/>
        <rect x="${cx - 56}" y="${base}" width="112" height="${laneY - base}"/>
        <circle cx="${cx}" cy="${laneY}" r="42"/>
        <path d="M${cx - 28} ${rimY} a28 28 0 0 0 56 0"/>
        <path d="M${cx - 154} ${base} V${cornerY.toFixed(1)} A${23.75 * k} ${23.75 * k} 0 0 0 ${cx + 154} ${cornerY.toFixed(1)} V${base}"/>
        <path d="M15 300 H365" />
        <path d="M${cx - 42} 300 a42 42 0 0 1 84 0"/>
      </g>
      ${dots}
      <line x1="${cx - 21}" y1="${base + 4 * k}" x2="${cx + 21}" y2="${base + 4 * k}" class="ha-board"/>
      <circle cx="${cx}" cy="${rimY}" r="6.5" class="ha-rim"/>
      <path id="ha-shot" d="${shot}" class="ha-arc"/>
      <circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="9" class="ha-shooter"/>
      ${matchMedia("(prefers-reduced-motion: reduce)").matches ? `<circle cx="${cx}" cy="${rimY}" r="6" class="ha-ball"/>`
        : `<circle r="6" class="ha-ball"><animateMotion dur="2.4s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.6;1" calcMode="linear"><mpath href="#ha-shot"/></animateMotion></circle>`}
      <g class="ha-card">
        <rect x="12" y="318" width="356" height="140" rx="12"/>
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
    const yes = [["rot", "clock", "evidence"], ["entry", "arrow", "evidence"], ["b2b", "clipboard", "evidence"],
      ["label", "player", "player"], ["rival", "court", "evidence"], ["sim", "cube", "method"]];
    $("#uses-yes").innerHTML = yes.map(([k, ic, go], i) =>
      `<div class="use"><div class="use-top"><span class="step">${i + 1}</span>${icon(ic)}</div>` +
      `<h3>${t("u." + k + ".t")}</h3><p>${t("u." + k + ".d", v)}</p>` +
      `<button class="btn" data-go="${go}">${t("u.go." + go)}${icon("arrow")}</button></div>`).join("");
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
    renderSimple(); renderUses(); renderCoach(); renderGlossary();
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
        { label: t("pl.naive"), bars: [{ v: pl.naive_real * 100, color: C.accent, name: real }, { v: pl.naive_placebo * 100, color: "#5b6b90", name: rnd }] },
        { label: t("pl.infer"), bars: [{ v: pl.inference_real * 100, color: C.accent, name: real }, { v: pl.inference_placebo * 100, color: "#5b6b90", name: rnd }] },
      ],
      max: 10, label: t("chart.placebo"),
    }) + `<div class="legend"><span><i style="background:${C.accent}"></i>${real}</span><span><i style="background:#5b6b90"></i>${t("lg.placebo")}</span><span>${t("pl.players", { n: pl.n_players })}</span></div>`;
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
          { label: t("ct.league"), est: S.heterogeneity.mu * 100, lo: S.heterogeneity.mu_lo * 100, hi: S.heterogeneity.mu_hi * 100, color: "#7d8aa8", tip: t("ct.league.tip") },
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
    $$("#new input").forEach((i) => i.addEventListener("input", renderNew));
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
    renderHero(); renderEvidence(); renderDefense(); renderMethod(); renderNew();
  }
  function onLang() {
    if (!ready) return;
    renderAll();
    fillTeams();
    fillPlayers(cur && cur.id);
  }
  function init() {
    renderHero(); renderEvidence(); renderDefense(); initPlayerControls(); initNew(); renderMethod();
    ready = true;
    window.I18N.onChange(onLang);
    show(location.hash.slice(1) || "summary");
  }
  bindTabs();
  apply();
  load();
})();
