/* CourtFatigue · lógica de la interfaz (HTML + CSS + JS sin dependencias) */
(function () {
  "use strict";
  const { lineBand, forest, groupedBars, coverageBars, court, fmt, esc, C } = window.CF;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const num = (v) => Number(v).toLocaleString("es");
  const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";

  const ZONE_ES = {
    "Restricted Area": "Bajo el aro", "In The Paint (Non-RA)": "Pintura (fuera del aro)", "Mid-Range": "Media distancia",
    "Left Corner 3": "Triple esquina izq.", "Right Corner 3": "Triple esquina der.", "Above the Break 3": "Triple frontal",
  };
  const ZONES = Object.keys(ZONE_ES);

  let S = null;           // resumen poblacional
  let DEFR = null;        // efecto defensivo por equipo
  let CONT = null;        // distancia al defensor (2014-15)
  let P = [];             // jugadores
  let cur = null;         // jugador seleccionado
  const shotCache = {};

  /* ---------------- carga ---------------- */
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
    } catch (e) {
      const box = $("#load-error");
      box.classList.remove("hidden");
      box.innerHTML = "<b>No se pudieron cargar los datos.</b> Esta página necesita un servidor local " +
        "(los navegadores bloquean <code>fetch</code> desde <code>file://</code>). " +
        "Desde la carpeta <code>web/</code> ejecuta <code>python -m http.server 8000</code> y abre <code>http://localhost:8000</code>. " +
        "Si falta la carpeta <code>data/</code>, genera los datos con <code>python scripts/build_web_data.py</code>.";
      return;
    }
    init();
  }

  /* ---------------- pestañas ---------------- */
  function show(tab) {
    if (!$("#" + tab)) tab = "resumen";
    $$(".pane").forEach((p) => p.classList.toggle("on", p.id === tab));
    $$("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    if (location.hash !== "#" + tab) history.replaceState(null, "", "#" + tab);
    window.scrollTo({ top: 0 });
  }
  function bindTabs() {
    $$("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tab)));
    $$("[data-go]").forEach((b) => b.addEventListener("click", () => show(b.dataset.go)));
    window.addEventListener("hashchange", () => show(location.hash.slice(1)));
  }

  const kpi = (l, v, d, cls = "") => `<div class="kpi ${cls}"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d || ""}</div></div>`;

  /* ---------------- veredicto poblacional ---------------- */
  const REF = () => `${S.short_lo}–${S.short} min`;   // referencia "ya calentado"

  function popVerdict() {
    const h = S.heterogeneity, mu = h.mu * 100, lo = h.mu_lo * 100, hi = h.mu_hi * 100;
    const b0 = S.buckets[0];
    const cold = b0 && b0.hi_pp < 0
      ? ` Lo que sí se ve va en sentido contrario a la fatiga: un arranque frío de ${fmt(b0.effect_pp, 1)} pp en los primeros ${b0.hi_edge} minutos tras entrar.` : "";
    const ci = `(IC 95%: ${fmt(lo, 2)} a ${fmt(hi, 2)})`;
    if (hi < 0) return { cls: "alert", badge: "Efecto detectado", title: "Hay una caída promedio de acierto tras muchos minutos seguidos",
      text: `Con ≥${S.long} min seguidos, el acierto ajustado por dificultad es ${fmt(mu, 2)} pp ${ci} frente a jugadores ya calentados (${REF()}).` };
    if (lo > 0) return { cls: "ok", badge: "Sin fatiga detectable", title: "No hay caída por fatiga: tras calentar, el acierto se mantiene o sube levemente",
      text: `Con ≥${S.long} min seguidos el acierto es ${fmt(mu, 2)} pp ${ci} frente a ${REF()}. Es una diferencia mínima y de signo contrario a la fatiga; ` +
        `probablemente refleja selección (los entrenadores dejan en cancha a quien está bien) más que un beneficio de jugar más.` + cold };
    return { cls: "ok", badge: "Sin efecto detectable", title: "No se detecta un efecto promedio de fatiga en el tiro",
      text: `Diferencia de ${fmt(mu, 2)} pp entre ≥${S.long} min y ${REF()} ${ci}. ` +
        (lo < 0 ? `Con esta precisión se descartan caídas promedio mayores a ${Math.abs(lo).toFixed(1)} pp. ` : "") +
        `Es compatible con que las rotaciones actuales ya evitan los tramos donde el tiro se deterioraría.` + cold };
  }

  /* ---------------- lenguaje llano ---------------- */
  function coldRow(label) { return (S.cold_start || []).find((r) => r.label === label && r.effect_pp != null); }

  function renderPlain() {
    const h = S.heterogeneity, mu = h.mu * 100, lo = h.mu_lo * 100, hi = h.mu_hi * 100, c0 = coldRow("0–30 s"), c1 = coldRow("1–2 min");
    const nS = S.seasons.length;
    const found = hi < 0
      ? `Tras muchos minutos seguidos <b>el acierto cae ${Math.abs(mu).toFixed(1)} puntos porcentuales</b> respecto a jugadores ya calentados. `
      : lo > 0
        ? `Hasta unos 12 minutos seguidos <b>el acierto no cae</b>: una vez calentados, se mantiene o sube apenas ${mu.toFixed(1)} puntos (probablemente porque se deja jugando a quien va bien). `
        : `Hasta unos 12 minutos seguidos <b>no hay una caída medible</b> del acierto (se descartan caídas mayores a ${Math.abs(lo).toFixed(1)} puntos porcentuales). `;
    $("#plain").innerHTML =
      `<h3>En 30 segundos</h3><div class="plain-grid">` +
      `<div><span class="step">1</span><h4>La pregunta</h4><p>Cuando un jugador lleva muchos minutos seguidos en cancha, ¿le cuesta más anotar? Si fuera así, el entrenador debería sustituirlo antes.</p></div>` +
      `<div><span class="step">2</span><h4>Lo que encontramos</h4><p>${found}` +
      (c0 ? `Lo que sí se ve es un <b>arranque frío</b>: en los primeros 30 segundos tras entrar, anotan unos ${Math.abs(c0.effect_pp).toFixed(1)} puntos menos que lo normal en ellos${c1 ? ", y se normaliza hacia el minuto 2" : ""}.` : "") + `</p></div>` +
      `<div><span class="step">3</span><h4>Qué significa</h4><p>Las rotaciones actuales ya evitan el problema de fondo. El margen de mejora está en <b>cómo entran</b> los jugadores más que en cuándo salen. ` +
      `Y ni con ${nS} temporadas se puede <b>señalar a un jugador individual</b> como "el que se cansa": la herramienta lo dice en vez de inventar una cifra.</p></div></div>`;
  }

  function renderCoach() {
    const h = S.heterogeneity, hi = h.mu_hi * 100;
    const c0 = coldRow("0–30 s");
    const cc = S.slopes.con_controles || [], b2b = cc.find((r) => r.term === "b2b"), home = cc.find((r) => r.term === "is_home");
    const ci = (r) => `IC ${fmt(r.lo_pp, 1)} a ${fmt(r.hi_pp, 1)}`;
    const dropTxt = hi < 0
      ? "Hay una caída de acierto tras muchos minutos seguidos: conviene vigilar los bloques largos."
      : "No hay base para acortar los bloques por \"cansancio de tiro\" hasta ~12 minutos seguidos.";
    $("#coach").innerHTML =
      `<h3>Para el cuerpo técnico</h3><div class="coach-grid">` +
      `<div class="tag">Lo que dicen los datos</div><div class="tag alt">Qué probar</div>` +
      `<p>${dropTxt}</p><p>Mantener a los titulares sin miedo a que el tiro se deteriore; buscar otras razones (defensa, faltas) para rotar.</p>` +
      `<p>${c0 ? `Los primeros 30 s tras entrar rinden ${Math.abs(c0.effect_pp).toFixed(1)} pp menos (${ci(c0)}) y el efecto se nota hasta cerca del minuto 2.` : "Hay un arranque frío tras entrar."}</p><p>Diseñar la primera jugada tras una entrada para un tiro de ritmo y no uno difícil, y comprobarlo en vídeo (es una hipótesis, no un hecho).</p>` +
      `<p>${b2b ? `En partidos tras jugar el día anterior, el acierto es ${fmt(b2b.coef_pp, 2)} pp (${ci(b2b)})${b2b.hi_pp < 0 ? ", un efecto pequeño pero consistente." : ": no concluyente."}${home ? ` Jugar en casa suma ${fmt(home.coef_pp, 2)} pp.` : ""}` : ""}</p><p>Dosificar a los tiradores clave en el segundo partido de un back-to-back; confirmarlo con datos de carga física real.</p>` +
      `<p>Solo se detectarían caídas individuales de ≈${S.power.mde_pp.toFixed(0)} pp o más, incluso con ${S.seasons.length} temporadas.</p><p>No etiquetar a un jugador como "se cansa" sin evidencia propia; en este análisis ningún jugador la tiene.</p></div>`;
  }

  function renderGlossary() {
    $("#glossary").innerHTML = `<summary>Glosario sin tecnicismos</summary><dl>` +
      [["pp (punto porcentual)", "Diferencia en el porcentaje de acierto. Pasar de 45% a 44% es −1 pp."],
        ["Margen de error / IC 95%", "El rango donde, con 95% de confianza, está el valor real. Si incluye el 0, no se puede afirmar que haya efecto."],
        ["Tiro esperado (xShot)", "La probabilidad de que un tiro entre según desde dónde y cómo se lanza. Sirve para no culpar al cansancio de un tiro difícil."],
        ["Efectos fijos", "Cada jugador se compara con su propio promedio, no con otros: así una estrella no distorsiona el resultado."],
        ["Corrección FDR", "Cuando se prueban muchos jugadores, algunos parecen 'culpables' por azar. Esta corrección evita acusar a inocentes."],
        ["Prueba placebo", "Barajar al azar los minutos de cada jugador. Si una regla sigue marcando jugadores, esa regla detecta ruido, no fatiga."],
        ["Potencia", "Qué tan pequeño puede ser un efecto y aun así ser detectado con los datos disponibles."]]
        .map(([t, d]) => `<dt>${t}</dt><dd>${d}</dd>`).join("") + `</dl>`;
  }

  /* ---------------- resumen ---------------- */
  function renderHero() {
    $("#season").textContent = S.season;
    $("#hero-lede").textContent =
      `Con ${num(S.n_games)} partidos y ${num(S.n_shots)} tiros, medimos cuánto cambia el acierto de cada jugador —descontada la dificultad de cada tiro— ` +
      `cuando lleva ${S.long} o más minutos seguidos en cancha, frente a cuando ya está calentado (${REF()}). Y mostramos con qué certeza se puede afirmar algo de cada jugador.`;
    const v = popVerdict(), h = S.heterogeneity;
    const c0 = coldRow("0–30 s");
    $("#hero-kpis").innerHTML =
      kpi(`Acierto tras ${S.long}+ min vs. ya calentado`, fmt(h.mu * 100, 2) + " pp", `puntos porcentuales; margen de error: ${fmt(h.mu_lo * 100, 1)} a ${fmt(h.mu_hi * 100, 1)}`, v.cls === "alert" ? "bad" : "accent") +
      kpi("Jugadores con caída comprobada", `${S.n_flagged} <small style="font-size:.5em;color:var(--muted)">de ${S.n_contrast_players}</small>`, "con prueba estadística exigente", S.n_flagged ? "bad" : "") +
      kpi("Arranque frío (primeros 30 s)", c0 ? fmt(c0.effect_pp, 1) + " pp" : "—", c0 ? `margen de error: ${fmt(c0.lo_pp, 1)} a ${fmt(c0.hi_pp, 1)}` : "", "bad") +
      kpi("Tiros analizados", num(S.n_shots_analysis), `${S.n_games.toLocaleString("es")} partidos · ${num(S.n_players)} jugadores`);
    renderPlain(); renderCoach(); renderGlossary();
    $("#verdict").className = "card verdict " + v.cls;
    $("#verdict").innerHTML = `<h3>${esc(v.title)} <span class="badge ${v.cls}">${esc(v.badge)}</span></h3><p>${v.text}</p>`;

    const b = S.buckets;
    const thin = (r) => r.n < 8000;
    const firstThin = b.findIndex(thin);
    $("#chart-pop-buckets").innerHTML = lineBand({
      pts: b.map((r, i) => ({ x: i, y: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp, tip: `${r.lo_edge}–${r.hi_edge} min · ${num(r.n)} tiros · ${fmt(r.effect_pp, 2)} pp` })),
      ticks: b.map((r, i) => ({ x: i, label: `${r.lo_edge}–${r.hi_edge >= 24 ? "24" : r.hi_edge}`, sub: num(r.n) })),
      xmin: -0.4, xmax: b.length - 0.6, hatchFrom: firstThin > 0 ? firstThin - 0.5 : null, hatchLabel: "pocos tiros",
      yTitle: "acierto vs. su promedio (pp)", xTitle: "minutos seguidos en cancha (debajo: nº de tiros)", errorBars: true, label: "Efecto por tramo de minutos seguidos",
    });
    const pl = S.placebo;
    $("#chart-placebo").innerHTML = groupedBars({
      groups: [
        { label: "Regla ingenua (caída ≥ 3 pp)", bars: [{ v: pl.naive_real * 100, color: C.accent, name: "Datos reales" }, { v: pl.naive_placebo * 100, color: "#5b6b90", name: "Minutos al azar" }] },
        { label: "Con inferencia (IC 95% + FDR)", bars: [{ v: pl.inference_real * 100, color: C.accent, name: "Datos reales" }, { v: pl.inference_placebo * 100, color: "#5b6b90", name: "Minutos al azar" }] },
      ],
      max: 10, label: "Tasa de jugadores marcados, real vs. placebo",
    }) + `<div class="legend"><span><i style="background:${C.accent}"></i>Datos reales</span><span><i style="background:#5b6b90"></i>Minutos al azar (placebo)</span><span>${pl.n_players} jugadores con ≥200 tiros</span></div>`;
  }

  /* ---------------- evidencia ---------------- */
  function renderEvidence() {
    $("#chart-coverage").innerHTML = coverageBars({ rows: S.coverage, label: "Tiros por tramo" });
    const sl = S.slopes, b2b = (sl.con_controles || []).find((r) => r.term === "b2b");
    $("#b2b-note").textContent = b2b ? `El propio back-to-back (partido tras jugar el día anterior) se asocia con ${fmt(b2b.coef_pp, 2)} pp (IC ${fmt(b2b.lo_pp, 2)} a ${fmt(b2b.hi_pp, 2)})${b2b.hi_pp < 0 ? "." : ": no concluyente."}` : "";
    $("#chart-slopes").innerHTML = forest({
      rows: (S.robustness || []).map((r) => ({ label: r.label, est: r.coef_pp, lo: r.lo_pp, hi: r.hi_pp, color: C.accent,
        tip: `${num(r.n)} tiros · ${fmt(r.coef_pp, 3)} pp/min (${fmt(r.lo_pp, 3)} a ${fmt(r.hi_pp, 3)})` })),
      xTitle: "pp de acierto por cada minuto seguido", labelW: 330, label: "Robustez de la pendiente",
    });
    $("#chart-seasons").innerHTML = forest({
      rows: (S.replication || []).map((r) => ({ label: `Temporada ${r.season}-${String(+r.season + 1).slice(2)}`, est: r.mu_pp, lo: r.mu_lo_pp, hi: r.mu_hi_pp,
        color: r.mu_hi_pp < 0 ? C.bad : C.blue, tip: `${num(r.n)} tiros · ${r.k} jugadores` })),
      xTitle: `pp: ≥${S.long} min menos ${REF()}`, labelW: 150, label: "Efecto por temporada",
    });
    $("#chart-cold-seasons").innerHTML = forest({
      rows: (S.cold_by_season || []).filter((r) => r.effect_pp != null).map((r) => ({ label: `Temporada ${r.season}-${String(+r.season + 1).slice(2)}`,
        est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp, color: r.hi_pp < 0 ? C.bad : C.blue, tip: `${num(r.n)} tiros` })),
      xTitle: "pp vs. su promedio (rojo = el intervalo excluye el 0)", labelW: 150, label: "Arranque frío por temporada",
    });
    const short = { "Tiempo desde que entra": "Tras entrar", "Primer minuto: ¿primera entrada?": "1.er minuto", "Primer minuto, por cuarto": "1.er minuto" };
    const cs = (S.cold_start || []).filter((r) => r.effect_pp != null);
    $("#chart-cold").innerHTML = forest({
      rows: cs.map((r) => ({ label: `${short[r.group] || r.group} · ${r.label}`, est: r.effect_pp, lo: r.lo_pp, hi: r.hi_pp,
        color: r.hi_pp < 0 ? C.bad : C.blue, tip: `${num(r.n)} tiros` })),
      xTitle: "pp de acierto vs. su promedio (rojo = el intervalo excluye el 0)", labelW: 250, W: 1120, rowH: 30, label: "Arranque frío",
    });
    const cq = (S.cold_start_quarter || [])[0];
    $("#cold-note").textContent = "Es asociación: puede reflejar calentamiento, emparejamientos de banca o el tipo de tiro tras entrar, no necesariamente un 'frío' físico. " +
      (cq && cq.effect_pp != null ? `Con otra regla de stints (reinicio en cada cuarto) el primer medio minuto da ${fmt(cq.effect_pp, 1)} pp (IC ${fmt(cq.lo_pp, 1)} a ${fmt(cq.hi_pp, 1)}), consistente.` : "");
    $("#chart-zones").innerHTML = forest({
      rows: S.zone_slopes.map((z) => ({ label: ZONE_ES[z.zone] || z.zone, est: z.coef_pp, lo: z.lo_pp, hi: z.hi_pp,
        color: z.q < 0.05 ? (z.coef_pp < 0 ? C.bad : C.good) : C.blue, tip: `${num(z.n)} tiros · q=${z.q.toFixed(3)}` })),
      xTitle: "pp por minuto seguido (rojo = caída significativa, verde = mejora significativa)", labelW: 170, label: "Efecto por zona",
    });
    $("#chart-metareg").innerHTML = forest({
      rows: S.metareg.map((m) => ({ label: m.feature, est: m.coef_pp, lo: m.lo_pp, hi: m.hi_pp,
        color: m.q < 0.05 ? (m.coef_pp < 0 ? C.bad : C.good) : C.blue, tip: `q=${m.q.toFixed(3)}` })),
      xTitle: "cambio del efecto (pp) por +1 desv. estándar (color = significativo tras FDR)", labelW: 230, label: "Meta-regresión",
    });
    const h = S.heterogeneity;
    const noHet = h.p_het > 0.05;
    $("#het-text").innerHTML =
      `<p>Entre los ${h.k} jugadores con tiros suficientes en ambos tramos, la dispersión real del efecto (τ) es <b>${(h.tau * 100).toFixed(2)} pp</b>` +
      ` (I² = ${(h.I2 * 100).toFixed(0)}%; prueba de heterogeneidad p ${h.p_het < 0.001 ? "&lt; 0.001" : "= " + h.p_het.toFixed(3)}).</p>` +
      (noHet ? `<p>La prueba no encuentra diferencias demostrables: <b>lo que se ve entre jugadores es compatible con ruido de muestreo</b>. Con ${S.seasons.length} temporadas de datos no se puede afirmar que unos se cansen más que otros. Por eso cada jugador se suaviza hacia el promedio de la liga y solo se recomienda cuando el intervalo excluye el cero.</p>`
        : `<p>Hay diferencias reales entre jugadores, pero son pequeñas frente a la incertidumbre de cada estimación individual; por eso cada jugador se suaviza hacia el promedio y solo se recomienda cuando el intervalo excluye el cero.</p>`) +
      `<p>Jugadores marcados: <b>${S.n_flagged} de ${S.n_contrast_players}</b>. Con 5% de error tipo I se esperarían ≈${Math.round(S.n_contrast_players * 0.05)} marcas solo por azar sin corrección; por eso se aplica Benjamini-Hochberg.</p>`;
  }

  /* ---------------- defensa de los equipos ---------------- */
  function renderDefense() {
    const box = $("#chart-defense");
    if (!DEFR) { box.innerHTML = '<svg viewBox="0 0 640 120"><text class="empty" x="320" y="60" text-anchor="middle">Sin datos de defensa cargados</text></svg>'; return; }
    const t = DEFR.teams;     // ya ordenados de mejor a peor defensa
    box.innerHTML = forest({
      rows: t.map((x) => ({ label: x.team, est: x.effect_pp, lo: x.lo_pp, hi: x.hi_pp,
        color: x.hi_pp < 0 ? C.good : x.lo_pp > 0 ? C.bad : C.blue,
        tip: `${num(x.n)} tiros defendidos · ${fmt(x.effect_pp, 2)} pp (${fmt(x.lo_pp, 2)} a ${fmt(x.hi_pp, 2)})` })),
      W: 1120, rowH: 22, labelW: 230, xTitle: "pp que sus rivales aciertan de más (+) o de menos (−) de lo esperado (verde = defensa sólida)", label: "Efecto defensivo por equipo",
    });
    const r = DEFR.stability_r.map((v) => v.toFixed(2)).join(", ");
    $("#def-ev-note").textContent = `Temporada ${DEFR.season}-${String(+DEFR.season + 1).slice(2)}. Cada valor descuenta la dificultad del tiro y el nivel del propio tirador, y se suaviza hacia el promedio de la liga. ` +
      `Se repite de un año a otro (correlación entre temporadas consecutivas: ${r}), así que es una señal real pero parcial. Es el efecto promedio del equipo, no el de un defensor sobre un tiro concreto.`;
  }

  /* ---------------- jugador ---------------- */
  function fillPlayers() {
    const team = $("#team-sel").value;
    const list = P.filter((p) => team === "all" || p.team === team);
    $("#player-sel").innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.name)} · ${num(p.n)} tiros</option>`).join("");
    if (list.length) selectPlayer(list[0].id);
  }
  function initPlayerControls() {
    const teams = Array.from(new Set(P.map((p) => p.team))).sort();
    $("#team-sel").innerHTML = `<option value="all">Todos los equipos</option>` + teams.map((t) => `<option>${esc(t)}</option>`).join("");
    $("#team-sel").addEventListener("change", fillPlayers);
    $("#player-sel").addEventListener("change", (e) => selectPlayer(+e.target.value));
    ["short", "long"].forEach((k) => $("#" + k + "-rng").addEventListener("input", () => {
      $("#" + k + "-v").textContent = $("#" + k + "-rng").value; renderCourts();
    }));
    fillPlayers();
  }
  function playerVerdict(p) {
    const c = p.contrast;
    if (!c) return { cls: "warn", badge: "Muestra insuficiente", title: "No hay datos suficientes para este jugador",
      text: `Se necesitan al menos 15 tiros con ${REF()} y 15 con ≥${S.long} min seguidos. Aquí no se alcanzan, así que no se puede decir nada sobre su fatiga.` };
    const range = `${fmt(c.lo_pp, 1)} a ${fmt(c.hi_pp, 1)} pp`;
    if (c.flag) return { cls: "alert", badge: "Evidencia de caída", title: `Rinde peor tras ≥${S.long} min seguidos`,
      text: `Diferencia de ${fmt(c.effect_pp, 1)} pp (IC 95%: ${range}), que resiste la corrección por comparaciones múltiples. ` +
        `Recomendación: planificar sus bloques por debajo de ~${S.long} min seguidos y comprobarlo con su cuerpo técnico y preparadores.` };
    return { cls: "ok", badge: "Sin evidencia", title: "Los datos no muestran que se deteriore con minutos seguidos",
      text: `Diferencia de ${fmt(c.effect_pp, 1)} pp con un intervalo de ${range}, que incluye el cero (o no resiste la corrección por comparaciones múltiples). ` +
        `No hay base estadística para cambiar su rotación por fatiga de tiro. Con sus ${num(c.n_l)} tiros en tramos largos solo se detectarían caídas de ≈${(2.8 * c.se_pp).toFixed(0)} pp o más; algo menor no se distingue del azar.` };
  }
  async function selectPlayer(id) {
    cur = P.find((p) => p.id === id);
    if (!cur) return;
    $("#player-sel").value = String(id);
    const c = cur.contrast, v = playerVerdict(cur);
    $("#player-head").innerHTML =
      `<img class="photo" src="https://cdn.nba.com/headshots/nba/latest/1040x760/${cur.id}.png" alt="" onerror="this.style.display='none'">` +
      `<div><h2>${esc(cur.name)}</h2><div class="meta">${esc(cur.team)} · ${num(cur.n)} tiros analizados</div></div>` +
      `<img class="logo" src="https://cdn.nba.com/logos/nba/${cur.team_id}/primary/L/logo.svg" alt="" onerror="this.style.display='none'">`;
    $("#player-kpis").innerHTML =
      kpi("Acierto real", pct(cur.fg), `esperado por dificultad: ${pct(cur.xfg)}`) +
      kpi(`Efecto ≥${S.long} vs ${REF()}`, c ? fmt(c.effect_pp, 1) + " pp" : "—", c ? `IC 95%: ${fmt(c.lo_pp, 1)} a ${fmt(c.hi_pp, 1)}` : "muestra insuficiente", c && c.flag ? "bad" : "accent") +
      kpi("Tiros en tramo largo", c ? num(c.n_l) : "—", c ? `y ${num(c.n_s)} en tramo corto` : "") +
      kpi("Estimación suavizada", c ? fmt(c.shrunk_pp, 1) + " pp" : "—", "hacia el promedio de la liga");
    $("#player-verdict").className = "card verdict " + v.cls;
    $("#player-verdict").innerHTML = `<h3>${esc(v.title)} <span class="badge ${v.cls}">${esc(v.badge)}</span></h3><p>${v.text}</p>`;

    const b = cur.buckets;
    $("#chart-player-buckets").innerHTML = lineBand({
      pts: b.map((r, i) => ({ x: i, y: r.n >= 30 ? r.dev_pp : null, lo: r.lo_pp, hi: r.hi_pp, tip: `${r.lo}–${r.hi} min · ${r.n} tiros · acierto ${r.fg != null ? pct(r.fg) : "—"} vs esperado ${r.xfg != null ? pct(r.xfg) : "—"}` })),
      ticks: b.map((r, i) => ({ x: i, label: `${r.lo}–${r.hi >= 24 ? "24" : r.hi}`, sub: "n=" + r.n })),
      xmin: -0.4, xmax: b.length - 0.6, yTitle: "vs. su promedio (pp)", xTitle: "minutos seguidos (se omiten tramos con < 30 tiros)", errorBars: true,
      emptyMsg: "Muy pocos tiros para dibujar una curva", label: "Curva del jugador",
    });
    if (c) {
      const se2 = (c.se_pp / 100) ** 2, tau2 = S.heterogeneity.tau2, B = se2 / (tau2 + se2);
      const sd = Math.sqrt((tau2 * se2) / (tau2 + se2) + B * B * S.heterogeneity.se_mu ** 2) * 100;
      $("#chart-player-contrast").innerHTML = forest({
        rows: [
          { label: "Estimación directa", est: c.effect_pp, lo: c.lo_pp, hi: c.hi_pp, color: C.accent, tip: "Solo sus datos" },
          { label: "Suavizada (liga)", est: c.shrunk_pp, lo: c.shrunk_pp - 1.96 * sd, hi: c.shrunk_pp + 1.96 * sd, color: C.blue, tip: "Combina sus datos con el promedio de la liga" },
          { label: "Promedio de la liga", est: S.heterogeneity.mu * 100, lo: S.heterogeneity.mu_lo * 100, hi: S.heterogeneity.mu_hi * 100, color: "#7d8aa8", tip: "Todos los jugadores" },
        ],
        xTitle: `pp de acierto: ≥${S.long} min menos ${REF()}`, labelW: 150, label: "Contraste del jugador",
      });
    } else {
      $("#chart-player-contrast").innerHTML = '<svg viewBox="0 0 640 140"><text class="empty" x="320" y="70" text-anchor="middle">Muestra insuficiente en alguno de los dos tramos</text></svg>';
    }
    if (!shotCache[id]) {
      try { shotCache[id] = await fetch(`data/shots/${id}.json`).then((r) => r.json()); } catch (e) { shotCache[id] = null; }
    }
    renderCourts();
  }
  function renderCourts() {
    if (!cur) return;
    const d = shotCache[cur.id], box = $("#courts");
    if (!d) { box.innerHTML = '<p class="note">No se pudieron cargar los tiros de este jugador.</p>'; return; }
    const sh = +$("#short-rng").value, lg = +$("#long-rng").value, fresh = [], tired = [];
    for (let i = 0; i < d.x.length; i++) {
      if (d.i[i]) continue;
      const st = d.s[i] / 10, s = { x: d.x[i], y: d.y[i], m: d.m[i] };
      if (st < sh) fresh.push(s); else if (st >= lg) tired.push(s);
    }
    const stat = (a) => (a.length ? `${pct(a.reduce((t, s) => t + s.m, 0) / a.length)} de acierto · ${a.length} tiros` : "sin tiros");
    box.innerHTML =
      `<div class="court-box"><h4>DESCANSADO · menos de ${sh} min</h4><div class="stat">${stat(fresh)}</div>${court(fresh)}</div>` +
      `<div class="court-box"><h4>CANSADO · ${lg} min o más</h4><div class="stat">${stat(tired)}</div>${court(tired)}</div>`;
  }

  /* ---------------- jugador nuevo ---------------- */
  function initNew() {
    const box = $("#mix-sliders");
    box.innerHTML = ZONES.map((z) => {
      const def = Math.round((S.zone_share[z] || 0) * 100);
      return `<div class="mix-row"><label for="mx-${ZONES.indexOf(z)}"><span>${ZONE_ES[z]}</span></label>` +
        `<input type="range" id="mx-${ZONES.indexOf(z)}" min="0" max="60" step="1" value="${def}" data-zone="${esc(z)}"><output>${def}%</output></div>`;
    }).join("");
    $$(".sv").forEach((e) => (e.textContent = `${S.short_lo}–${S.short}`));
    $$(".lv").forEach((e) => (e.textContent = S.long));
    $$("#nuevo input").forEach((i) => i.addEventListener("input", renderNew));
    renderNew();
  }
  function renderNew() {
    const rows = $$("#mix-sliders input");
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
      kpi("Acierto descansado", pct(base), `perfil de tiro + nivel (${skill >= 0 ? "+" : ""}${skill.toFixed(1)} pp)`) +
      kpi(`Proyección ≥${S.long} min`, pct(long), `IC 95%: ${pct(base + lo)} a ${pct(base + hi)}`, "accent") +
      kpi("Efecto esperado", fmt(mu * 100, 2) + " pp", `rango ${fmt(lo * 100, 1)} a ${fmt(hi * 100, 1)}`, lo > 0 || hi < 0 ? "bad" : "");
    const B = base * 100, E = mu * 100, L = lo * 100, H = hi * 100;
    const pts = [{ x: 0, y: B, lo: B, hi: B }, { x: S.short, y: B, lo: B, hi: B }, { x: S.long, y: B + E, lo: B + L, hi: B + H }, { x: 12, y: B + E, lo: B + L, hi: B + H }]
      .map((p) => ({ ...p, tip: `${p.y.toFixed(1)}% (${p.lo.toFixed(1)}–${p.hi.toFixed(1)})` }));
    $("#chart-projection").innerHTML = lineBand({
      pts, xmin: 0, xmax: 24, ticks: [0, 4, 8, 12, 16, 20, 24].map((x) => ({ x, label: x + "'" })),
      hatchFrom: 12, hatchLabel: "sin datos: extrapolación", includeZero: false, yTitle: "acierto proyectado (%)", xTitle: "minutos seguidos en cancha", label: "Proyección de acierto",
    });
    $("#proj-note").innerHTML =
      (usedOwn ? "Estimación combinada: el promedio de la liga se ajusta con los tiros que ingresaste, pesando más lo observado cuanto más tiros haya. "
        : "Sin tiros propios, la proyección es el promedio de la liga con el rango de variación entre jugadores (τ = " + (h.tau * 100).toFixed(2) + " pp). ") +
      "Los datos reales llegan hasta ~12 minutos seguidos; más allá, cualquier curva es extrapolación. " +
      "El perfil de tiro fija el punto de partida. " +
      (S.metareg.some((r) => r.q < 0.05) ? "Alguna característica modificó el efecto de forma significativa (ver Evidencia), pero esta proyección no la usa."
        : "Ninguna característica medida modificó el efecto de forma significativa (ver Evidencia).");
  }

  /* ---------------- método ---------------- */
  function renderMethod() {
    const x = S.xshot || {}, m = x[x.chosen] || {}, bl = x.baseline_log_loss;
    $("#method-text").innerHTML = `
      <h3>Pregunta</h3>
      <p>¿Cae el acierto de un jugador cuando lleva muchos minutos seguidos en cancha, y en qué zonas? ¿Con qué certeza se puede decir algo de un jugador concreto, o de uno nuevo sin historial?</p>
      <h3>Datos</h3>
      <p><b>Análisis principal.</b> ${esc(S.season)}: ${num(S.n_games)} partidos y ${num(S.n_shots)} tiros con coordenadas (<code>ShotChartDetail</code>), más el play-by-play con sustituciones y marcador (<code>PlayByPlayV2</code>), de la NBA Stats API.</p>
      ${CONT ? `<p><b>Defensa.</b> Nuestras temporadas no traen la posición de los defensores. Para el simulador se usa un segundo conjunto: el registro de tiros 2014-15 (unos 128 mil tiros con distancia al defensor, licencia CC0), que mide cuánto cambia el acierto según qué tan cerca esté el defensor. No se cruza con las otras temporadas.</p>` : ""}
      <h3>1 · Minutos seguidos (stints)</h3>
      <ul>
        <li>Se cuenta solo el tiempo de juego. El contador sigue entre el 1.º y 2.º cuarto y entre el 3.º y 4.º, y se reinicia en el medio tiempo.</li>
        <li>El play-by-play no registra las sustituciones entre cuartos: en cada cuarto se detecta quién ya estaba en pista y, si venía del cuarto anterior, conserva su contador.</li>
        <li>Los tiros cuyo tirador no figuraba en pista (${pct(S.n_inferred / S.n_shots, 2)}) se excluyen del análisis principal.</li>
        <li>Prueba de sensibilidad: reiniciar el contador en cada cuarto (ver Evidencia).</li>
      </ul>
      <h3>2 · Tiro esperado (xShot)</h3>
      <p>Probabilidad de anotar según distancia, posición, zona, tipo de tiro y periodo; no usa minutos en pista ni identidad del jugador. Validación: ${esc(x.validation || "")}.
      ${m.log_loss ? `Modelo elegido: <b>${esc(x.chosen)}</b> · log-loss ${m.log_loss.toFixed(4)} (referencia sin modelo: ${bl.toFixed(4)}) · AUC ${m.auc.toFixed(3)} · error de calibración ${(m.ece * 100).toFixed(2)} pp.` : ""}
      ${x.temporal_holdout ? `<br><b>Prueba temporal:</b> entrenado con las temporadas anteriores y evaluado en ${esc(x.temporal_holdout.test_season)}-${String(+x.temporal_holdout.test_season + 1).slice(2)} (${num(x.temporal_holdout.n_test)} tiros que nunca vio): log-loss ${x.temporal_holdout[x.chosen].log_loss.toFixed(4)} (referencia: ${x.temporal_holdout.baseline_log_loss.toFixed(4)}), AUC ${x.temporal_holdout[x.chosen].auc.toFixed(3)}, calibración ${(x.temporal_holdout[x.chosen].ece * 100).toFixed(2)} pp.` : ""}</p>
      <h3>3 · Efecto de fatiga</h3>
      <ul>
        <li><b>Residuo</b> = acierto real − xShot.</li>
        <li><b>Contraste por jugador</b> = residuo medio con ≥${S.long} min seguidos − residuo medio con ${S.short_lo}–${S.short} min (ya calentado: así se excluye el arranque frío, que no es fatiga). Restar dentro del mismo jugador elimina su nivel base, así que cada uno se compara consigo mismo.</li>
        <li><b>Pendiente poblacional</b>: regresión del residuo sobre los minutos seguidos con efectos fijos por jugador y errores robustos agrupados por jugador.</li>
        <li><b>Diferencias entre jugadores</b>: modelo de efectos aleatorios (DerSimonian-Laird) → promedio, τ e I².</li>
        <li><b>Recomendación</b>: solo si el IC 95% excluye 0 y la tasa de falsos descubrimientos (Benjamini-Hochberg) es &lt; 5%.</li>
        <li><b>Prueba placebo</b>: se repite el procedimiento con los minutos barajados dentro de cada jugador; mide cuántas recomendaciones aparecen cuando la fatiga no puede existir.</li>
      </ul>
      <h3>4 · Jugador nuevo</h3>
      <p>Punto de partida: acierto esperado según su perfil de tiro por zona más su nivel. El efecto de fatiga se toma de la distribución poblacional (promedio y τ). Si se ingresan tiros propios, se combinan por precisión (estimación bayesiana normal-normal).</p>
      <h3>5 · Defensa y simulador 3D</h3>
      <ul>
        <li><b>Efecto del equipo rival</b>: acierto del rival menos lo esperado por la dificultad del tiro y por el propio tirador, promediado por equipo y suavizado hacia la liga (empirical Bayes). Se usa la temporada más reciente.</li>
        <li><b>Efecto de la distancia al defensor</b>: gradient boosting monótono (más distancia nunca baja el acierto) sobre los datos 2014-15, con banda de confianza por remuestreo de partidos (${CONT ? CONT.n_boot : 24} réplicas). El ajuste es relativo a la distancia típica del defensor para ese tipo de tiro (≈5.5 ft en un triple, ≈2.3 ft cerca del aro), porque la curva por distancia del tiro ya incluye cuánto suele estar marcado. Solo se ofrece entre 1.5 y 8 pies, donde hay datos suficientes.</li>
        <li><b>Probabilidad del simulador</b> = acierto base del jugador + ajuste por distancia del tiro + efecto del defensor + efecto del rival + arranque frío − fatiga. Cada término sale de datos; las posiciones de los otros cuatro defensores son ilustrativas.</li>
      </ul>
      <h3>Limitaciones</h3>
      <ul>
        <li>Es asociación, no causalidad: los entrenadores sustituyen a quien perciben cansado, de modo que los stints largos están sesgados hacia jugadores que van bien.</li>
        <li>Sin datos del defensor ni de condición física individual en el análisis principal. ${CONT && CONT.gap ? `En la 2014-15, conocer la distancia al defensor sube el AUC del tiro esperado de ${CONT.gap.rows[0].auc.toFixed(3)} a ${CONT.gap.rows[1].auc.toFixed(3)} (${CONT.gap.rows[2].auc.toFixed(3)} con reloj, toques y regates): nuestro modelo deja esa parte como ruido, y no podemos comprobar si sesga la comparación entre minutos.` : ""}</li>
        <li>El efecto de la distancia al defensor viene de otra época (2014-15) y mide asociación: los defensores suelen estar más cerca de los mejores tiradores y hay contraataques sin defensor. El efecto del rival es del equipo en promedio, no de un defensor concreto.</li>
        <li>${S.seasons.length} temporadas (${S.seasons[0]}-${String(+S.seasons[0] + 1).slice(2)} a ${S.seasons[S.seasons.length - 1]}-${String(+S.seasons[S.seasons.length - 1] + 1).slice(2)}). Los stints de más de 12 minutos son raros: más allá de ahí, cualquier proyección es extrapolación.</li>
        <li>Potencia limitada por jugador: el error estándar típico del contraste es ${S.power.median_se_pp.toFixed(1)} pp, así que solo se detectarían caídas individuales de ≈${S.power.mde_pp.toFixed(0)} pp o más. Efectos menores existen o no, pero estos datos no permiten verlos.</li>
        <li>Los umbrales (${S.short_lo}–${S.short} y ${S.long} minutos) son una elección; la pendiente continua se reporta como alternativa.</li>
        <li>Un resultado sin efecto detectable no demuestra que la fatiga no exista: indica que, con estos datos, no se distingue de cero. Con ${S.seasons.length} temporadas el promedio queda acotado con bastante precisión, pero no el de cada jugador.</li>
      </ul>`;
  }

  function init() {
    renderHero(); renderEvidence(); renderDefense(); initPlayerControls(); initNew(); renderMethod();
    show(location.hash.slice(1) || "resumen");
  }
  bindTabs();
  load();
})();
