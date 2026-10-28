// Prueba del modelo de probabilidad y de los defensores del simulador 3D (web/simulador/index.html).
// Usa Three.js real (sin navegador) y los JSON generados en web/data/.
//
//   curl -o tests/three.min.js https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js
//   node tests/test_simulator.js
//
// (tests/three.min.js está en .gitignore; también puedes indicar otra ruta con THREE_PATH)
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const threePath = process.env.THREE_PATH || path.join(__dirname, 'three.min.js');
if (!fs.existsSync(threePath)) { console.error('Falta three.min.js: ver instrucciones al inicio de este archivo.'); process.exit(2); }
global.THREE = require(threePath);
const J = (f) => JSON.parse(fs.readFileSync(path.join(root, 'web', 'data', f), 'utf8'));

// El bloque de defensa del simulador está delimitado por marcadores en el HTML
const html = fs.readFileSync(path.join(root, 'web', 'simulador', 'index.html'), 'utf8');
const block = html.slice(html.indexOf('// <<DEFENSA'), html.indexOf('// DEFENSA>>')) + ' ' +
              html.slice(html.indexOf('// <<TRAYECTORIA'), html.indexOf('// TRAYECTORIA>>'));
if (!block) { console.error('No se encontró el bloque DEFENSA en el simulador'); process.exit(2); }

const els = {};
global.document = { getElementById: (id) => (els[id] = els[id] || { value: '2.5', textContent: '' }) };
global.scene = new THREE.Scene();
global.HOOP_X = 0; global.HOOP_Z = -5.5;
global.currentShooterPos = { x: 0, z: 2.2 };
global.activePlayerKey = 'Curry';
global.PLAYERS_DATA = { Curry: { baseFg: 47.0 } };
global.fatigueDropFor = () => 0;
(0, eval)(block + `
global.FT = FT; global.DEF = DEF;
global.computeShotProb = computeShotProb; global.buildDefenders = buildDefenders; global.placeDefenders = placeDefenders;
global.typicalDef = typicalDef; global.syncTypicalDefender = syncTypicalDefender;
global.launchModel = launchModel; global.FLIGHT_SLOWMO = FLIGHT_SLOWMO;
Object.defineProperty(global, 'defendersGroup', { get: () => defendersGroup, configurable: true });`);

let passed = 0;
const ok = (c, msg) => { if (!c) { console.log('FALLA:', msg); process.exitCode = 1; } else { passed++; } };

DEF.contest = J('contest.json'); DEF.dist = J('distance.json');
const defense = J('defense.json'); DEF.teams = defense.teams;

// 1) Un defensor a la distancia TÍPICA de ese tiro no cambia la probabilidad (la curva por distancia ya lo incluye)
global.currentShooterPos = { x: 0, z: 2.2 };
let m = computeShotProb();
DEF.mainDef = Math.round(m.typ * 2) / 2;
m = computeShotProb();
ok(Math.abs(m.ca.adj) < 1.0, `defensor a la distancia típica (${m.typ.toFixed(1)} ft) => ajuste ~0 (${m.ca.adj.toFixed(2)} pp)`);
ok(m.distFeet > 24 && m.distFeet < 26, 'distancia ~25 ft');
const typFar = typicalDef(25), typNear = typicalDef(4);
ok(typFar > typNear, `un triple se defiende más lejos (${typFar.toFixed(1)} ft) que un tiro cerca del aro (${typNear.toFixed(1)} ft)`);
// con la distancia automática activada, el control se ajusta al valor típico del tiro y queda en el rango con datos
DEF.auto = true; syncTypicalDefender();
ok(DEF.mainDef >= 1.5 && DEF.mainDef <= 8 && Math.abs(DEF.mainDef - typFar) <= 0.5, `distancia automática = ${DEF.mainDef} ft`);
ok(m.da < -8, 'un triple tiene ajuste por distancia negativo y grande');

// 2) Monótona: más lejos el defensor, nunca menos probabilidad
let prev = -1e9, mono = true;
for (let d = 1.5; d <= 8; d += 0.5) { DEF.mainDef = d; const p = computeShotProb().final; if (p < prev - 1e-9) mono = false; prev = p; }
ok(mono, 'probabilidad monótona en la distancia al defensor');
DEF.mainDef = 1.5; const close = computeShotProb().final; DEF.mainDef = 8.0; const open = computeShotProb().final;
ok(open - close > 8, 'triple abierto vs. marcado difiere en más de 8 pp');

// 3) Equipo rival
DEF.mainDef = 5.0; DEF.team = null; const base = computeShotProb().final;
DEF.team = DEF.teams[0]; const best = computeShotProb().final;
DEF.team = DEF.teams[DEF.teams.length - 1]; const worst = computeShotProb().final;
ok(best < base && base < worst, 'mejor defensa < liga < peor defensa');

// 4) Arranque frío
DEF.team = null; DEF.cold = [{ hi: 0.5, eff: -1.46 }, { hi: 1.0, eff: -0.5 }, { hi: 2.0, eff: -0.39 }];
els['slider-stint'] = { value: '0' }; const p0 = computeShotProb();
els['slider-stint'] = { value: '3' }; const p3 = computeShotProb();
ok(p0.cold === -1.46 && p3.cold === 0 && Math.abs(p3.final - p0.final - 1.46) < 1e-9, 'arranque frío: -1.46 pp al inicio, 0 desde los 2 min');

// 5) Geometría de los defensores en todas las zonas de tiro
buildDefenders(); DEF.auto = false;
ok(defendersGroup.children.length === 5, '5 defensores');
const zones = { top3: [0, 2.2], corner3_r: [6.2, -5.0], wing3: [4.8, -0.5], midrange: [-3.5, -1.0], freethrow: [0, -0.9], paint: [0.6, -3.4] };
for (const [name, [x, z]] of Object.entries(zones)) {
  global.currentShooterPos = { x, z };
  for (const ft of [1.5, 4, 8]) {
    DEF.mainDef = ft; placeDefenders();
    const main = defendersGroup.children[0].position;
    const dShooter = Math.hypot(main.x - x, main.z - z) / FT;
    const wanted = Math.min(ft, Math.max(0.46, Math.hypot(HOOP_X - x, HOOP_Z - z) - 0.3) / FT);
    ok(Math.abs(dShooter - wanted) < 0.05, `${name}/${ft} ft: distancia del defensor principal`);
    ok(Math.hypot(main.x - HOOP_X, main.z - HOOP_Z) >= 0.25, `${name}/${ft} ft: no atraviesa el aro`);
    if (Math.hypot(HOOP_X - x, HOOP_Z - z) > 3) {   // lejos del aro: el defensor se desplaza ~22° de la línea tirador-aro
      const a1 = Math.atan2(HOOP_Z - z, HOOP_X - x), a2 = Math.atan2(main.z - z, main.x - x);
      let da = Math.abs(a1 - a2); if (da > Math.PI) da = 2 * Math.PI - da;
      ok(da > 0.25 && da < 0.5, `${name}/${ft} ft: desplazado ${(da * 180 / Math.PI).toFixed(0)}° de la línea al aro`);
    }
    for (let k = 1; k < 5; k++) {
      const g = defendersGroup.children[k].position;
      ok(Math.hypot(g.x - x, g.z - z) >= 1.0 && Math.hypot(g.x - main.x, g.z - main.z) >= 0.8, `${name}/${ft} ft: defensor ${k} sin solaparse`);
    }
  }
}
const box = new THREE.Box3().setFromObject(defendersGroup.children[0]);
ok(box.max.y > 1.85 && box.max.y < 2.15, 'altura del defensor ~1.95 m');

// 6) Trayectoria del balón: parábola física hasta el aro
const HOOP_Y = 3.05;
const target = new THREE.Vector3(HOOP_X, HOOP_Y + 0.05, HOOP_Z);
const spots = { top3: [0, 2.2], corner3_r: [6.2, -5.0], wing3: [4.8, -0.5], midrange: [-3.5, -1.0], freethrow: [0, -0.9], paint: [0.6, -3.4] };
for (const [name, [x, z]] of Object.entries(spots)) {
  const start = new THREE.Vector3(x, 2.45, z);
  const m = launchModel(start, target);
  const end = m.at(m.T);
  ok(end.distanceTo(target) < 1e-6, `${name}: el balón llega exactamente al aro`);
  ok(m.vyAt(m.T) < 0, `${name}: entra bajando (vy = ${m.vyAt(m.T).toFixed(2)} m/s)`);
  const T = m.T * FLIGHT_SLOWMO;
  ok(T > 0.55 && T < 1.9, `${name}: tiempo de vuelo realista (${T.toFixed(2)} s con cámara lenta)`);
  let apex = -1, monotoneH = true, prevDist = -1;
  for (let i = 0; i <= 60; i++) {
    const q = m.at(m.T * i / 60); apex = Math.max(apex, q.y);
    const d = Math.hypot(q.x - start.x, q.z - start.z); if (d < prevDist - 1e-9) monotoneH = false; prevDist = d;
  }
  const distFt = Math.hypot(x - HOOP_X, z - HOOP_Z) * 3.28084;
  ok(apex > start.y + 0.5, `${name}: el arco sube sobre el punto de suelta (apex ${apex.toFixed(2)} m)`);
  ok(apex < 6.0, `${name}: el arco no sale de la vista (apex ${apex.toFixed(2)} m)`);
  if (distFt > 22) ok(apex > 4.0 && apex < 5.8, `${name}: tiro de 3 con altura máxima realista (${apex.toFixed(2)} m)`);
  ok(monotoneH, `${name}: avance horizontal siempre hacia el aro`);
  const ang = Math.atan2(-m.vyAt(m.T), m.v * Math.cos(m.angleDeg * Math.PI / 180)) * 180 / Math.PI;
  ok(ang > 30 && ang < 65, `${name}: ángulo de entrada al aro ${ang.toFixed(0)}°`);
}

console.log(process.exitCode ? 'HAY FALLAS' : `OK: ${passed} comprobaciones`);
