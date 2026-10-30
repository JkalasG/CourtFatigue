/* CourtFatigue - bench calculator model (pure functions; also loaded by tests/test_calculator.js).
   Expected make probability = player's level for the shot type + rival + cold start for that type and
   moment + bench-time adjustment. Every term is read from the JSON written by the Python scripts. */
(function (root) {
  "use strict";
  const Z95 = 1.959964;
  const K_SHRINK = 50;   // a player's own shots of a type count against 50 league-average shots
  const TYPES = { three: "Three-pointer", mid: "Mid-range", rim: "Near the rim (paint)" };
  const ZONES = { three: ["Left Corner 3", "Right Corner 3", "Above the Break 3"], mid: ["Mid-Range"],
    rim: ["Restricted Area", "In The Paint (Non-RA)"] };
  const WINDOWS = [[30, "0–30 s"], [60, "30–60 s"], [120, "1–2 min"]];
  const BENCH = [[3, "< 3 min"], [6, "3–6 min"], [10, "6–10 min"], [15, "10–15 min"], [Infinity, "> 15 min"]];
  const se = (lo, hi) => (hi - lo) / (2 * Z95);

  /* Shot coordinates in tenths of a foot, rim at (0, 0) (NBA shot charts). */
  function classify(x, y) {
    if ((Math.abs(x) >= 220 && y <= 92.5) || Math.hypot(x, y) >= 237.5) return "three";
    if (Math.abs(x) < 80 && y < 142.5) return "rim";
    return "mid";
  }

  /* League make rate per type, from the zone table of summary.json */
  function leagueFg(S) {
    const out = {};
    for (const [k, zs] of Object.entries(ZONES)) {
      let w = 0, f = 0;
      zs.forEach((z) => { const sh = S.zone_share[z] || 0; w += sh; f += sh * (S.zone_fg[z] || 0); });
      out[k] = w ? f / w : null;
    }
    return out;
  }

  /* Player's make rate per type, shrunk toward the league (shots file: {x, y, m}) */
  function playerBase(shots, league) {
    const n = { three: 0, mid: 0, rim: 0 }, made = { three: 0, mid: 0, rim: 0 };
    shots.x.forEach((x, i) => { const k = classify(x, shots.y[i]); n[k]++; made[k] += shots.m[i]; });
    const out = {};
    for (const k of Object.keys(TYPES)) {
      const p = (made[k] + K_SHRINK * league[k]) / (n[k] + K_SHRINK);
      out[k] = { p, se: Math.sqrt(p * (1 - p) / (n[k] + K_SHRINK)), n: n[k] };
    }
    return out;
  }

  const windowOf = (sec) => (WINDOWS.find(([lim]) => sec < lim) || [null, null])[1];

  /* Cold-start term (pp) for a shot type at `sec` seconds after entering: 0 from minute 2 on */
  function coldTerm(X, type, sec) {
    const w = windowOf(sec);
    if (!w) return { pp: 0, se: 0, window: null };
    const r = X.shot_type.find((row) => row.type === TYPES[type] && row.window === w);
    return { pp: r.effect_pp, se: se(r.lo_pp, r.hi_pp), window: w };
  }

  function benchRow(X, situation, benchMin) {
    const rows = X.bench_time.buckets;
    if (situation === "first") return rows.find((r) => r.label === "First stint of the game");
    if (situation === "half") return rows.find((r) => r.label === "Halftime (3rd quarter start)");
    const lab = BENCH.find(([lim]) => benchMin < lim)[1];
    return rows.find((r) => r.label === lab);
  }

  /* Bench adjustment (pp), first 30 s only: that bucket's 0-30 s drop minus the overall 0-30 s drop */
  function benchAdj(X, overall30, situation, benchMin, sec) {
    if (windowOf(sec) !== "0–30 s") return { pp: 0, se: 0 };
    const r = benchRow(X, situation, benchMin);
    if (!r || r.effect_30s_pp == null) return { pp: 0, se: 0 };
    return { pp: r.effect_30s_pp - overall30, se: se(r.lo_30s_pp, r.hi_30s_pp), label: r.label };
  }

  /* All terms together; probability with an approximate 95% interval (independent terms) */
  function predict({ base, type, X, overall30, situation, benchMin, sec, rival }) {
    const b = base[type], c = coldTerm(X, type, sec), a = benchAdj(X, overall30, situation, benchMin, sec);
    const r = rival ? { pp: rival.effect_pp, se: se(rival.lo_pp, rival.hi_pp) } : { pp: 0, se: 0 };
    const p = b.p + (r.pp + c.pp + a.pp) / 100;
    const s = Math.sqrt(b.se ** 2 + ((r.se ** 2 + c.se ** 2 + a.se ** 2) / 1e4));
    const clamp = (v) => Math.min(0.99, Math.max(0.01, v));
    return { p: clamp(p), lo: clamp(p - Z95 * s), hi: clamp(p + Z95 * s),
      parts: { base: b.p, rival: r.pp, cold: c.pp, bench: a.pp }, window: c.window };
  }

  const api = { TYPES, classify, leagueFg, playerBase, windowOf, coldTerm, benchAdj, predict, K_SHRINK };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CALC = api;
})(typeof window !== "undefined" ? window : globalThis);
