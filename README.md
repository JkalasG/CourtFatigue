# 🏀 CourtFatigue: ¿cuándo deja de rendir un jugador y dónde lo nota la cancha?

> Proyecto para el **AQX Sports Analytics Data Bowl 4.0**.
> Interfaz en HTML + CSS + JS (sin librerías), análisis en Python, simulador 3D con Three.js.

CourtFatigue mide si el acierto de tiro de un jugador de la NBA cae cuando lleva muchos minutos seguidos en cancha, **descontando la dificultad de cada tiro**, y dice con qué certeza se puede afirmar algo de un jugador concreto, o de uno nuevo sin historial. Un simulador 3D permite probar el efecto de los minutos, del equipo rival y de la distancia del defensor, con cada término medido en datos.

## Resultado principal

**Datos:** temporadas regulares NBA 2021-22 a 2024-25 · 4,920 partidos · 872,158 tiros · 913 jugadores.

| Pregunta | Resultado |
| --- | --- |
| ¿Cae el acierto tras ≥ 8 min seguidos, frente a un jugador ya calentado (2-6 min)? | **+0.21 pp** (IC 95%: −0.13 a +0.56): no. Se descartan caídas promedio mayores a ~0.13 pp |
| Pendiente por minuto seguido, tras calentar | +0.027 pp/min (IC 95%: −0.014 a +0.069): plana |
| ¿Se repite temporada por temporada? | Sí: +0.41, +0.32, −0.36 y +0.18 pp (todos con IC que incluye 0) |
| Jugadores con caída demostrable (IC 95% < 0 y corrección FDR) | **0 de 592** |
| Zonas de la cancha con caída significativa (tras calentar) | **0 de 6**. Las dos interiores muestran una mejora leve (+0.11 y +0.16 pp/min) |
| Características del jugador que modifican el efecto | **0 de 7** |
| **Arranque frío** (tras entrar a cancha) | **−1.46 pp** en los primeros 30 s (IC −1.95 a −0.97), −0.50 pp entre 30 y 60 s, −0.39 pp entre 1 y 2 min; normal desde los 2 min. Negativo en las 4 temporadas (intervalo claro en 3 de 4); con otra regla de stints (reinicio en cada cuarto) sigue en −1.08 pp (IC −1.50 a −0.65) |
| Calendario y contexto | back-to-back **−0.39 pp** (IC −0.67 a −0.11); jugar en casa **+0.38 pp** (IC +0.11 a +0.65) |
| Defensa del rival | Efecto real y estable entre temporadas (r ≈ 0.52): de −1.2 pp (Thunder) a +1.7 pp (Kings) en 2024-25 |

**No hay fatiga de tiro detectable hasta ~12 minutos seguidos.** Es compatible con que las rotaciones actuales ya evitan los tramos donde el tiro se deterioraría. Lo que sí se ve es un **arranque frío**, y calendario y localía con efectos pequeños pero consistentes. A nivel individual la potencia es limitada: el error estándar típico por jugador es de ~5 pp, así que solo se detectarían caídas de unos 14 pp o más. Por eso la herramienta no etiqueta a ningún jugador como "el que se cansa", y lo dice.

> **Por qué la comparación es contra jugadores ya calentados.** Comparar ≥ 8 min contra todo lo que sea < 4 min da +0.65 pp, pero eso mezcla el arranque frío con la fatiga. Con la referencia de 2-6 min el efecto baja a +0.21 pp. La pendiente con todos los tramos (+0.097 pp/min) también está inflada por el arranque; tras calentar es +0.027.

### Por qué importa la inferencia: la regla ingenua no funciona
Una regla del tipo *"sustituir cuando el acierto cae 3 puntos en algún tramo con ≥ 20 tiros"* marca al **60.5%** de los jugadores con los datos reales y al **59.4%** cuando los minutos se barajan al azar dentro de cada jugador (donde la fatiga no puede existir). Es ruido. La regla de este proyecto (IC 95% excluye 0 y corrección de Benjamini-Hochberg) marca **0%** con los datos reales y 0.04% con los minutos al azar. Esta comparación está en la pestaña *Evidencia* y se verifica con pruebas sintéticas en `tests/`.

### Robustez
La pendiente por minuto resiste: excluir partidos decididos (diferencia ≥ 20), usar solo partidos parejos (≤ 10), controlar por minutos del partido, local o visitante, marcador y back-to-back, reiniciar el contador en cada cuarto e incluir los tiros con stint incierto (todas entre +0.09 y +0.11 pp/min con todos los tramos; tras calentar, +0.027).

## Interfaz

Pestañas: **Resumen** (con "En 30 segundos", panel para el cuerpo técnico y glosario en lenguaje llano) · **Jugador** (curva, IC, mapas descansado vs. cansado) · **Evidencia** (cobertura de datos, robustez, temporada por temporada, arranque frío, zonas, características, ranking defensivo) · **Jugador nuevo** (proyección con incertidumbre) · **Método** (+ simulador 3D).

Identidad visual tomada del hackatón AQX (azul marino, azul acero y blanco).

```bash
cd web
python -m http.server 8000      # abrir http://localhost:8000
```
Hace falta un servidor local porque el navegador bloquea `fetch` desde `file://`. La carpeta `web/` es estática. `.github/workflows/pages.yml` la publica en GitHub Pages en cada push a `main` (activar en Settings → Pages → Source: *GitHub Actions*).

Para el envío a Devpost: `docs/devpost_descripcion.md` (texto) y `docs/guion_video_2min.md` (guion opcional).

## Simulador 3D (`web/simulador/`)

La probabilidad de anotar se construye sumando términos medidos; nada está escrito a mano:

| Término | Fuente |
| --- | --- |
| Acierto base del jugador | FG% real de cada jugador en 2021-25 |
| Distancia del tiro | curva de acierto por distancia de nuestras 4 temporadas (p. ej., −11 pp en un triple de 25 ft) |
| Distancia al defensor (1.5-8 ft) | 128,065 tiros de la temporada 2014-15 con ese dato (CC0), gradient boosting monótono con banda de confianza por remuestreo de partidos. El ajuste es **relativo a la distancia típica del defensor para ese tipo de tiro** (≈5.5 ft en un triple, ≈2.3 ft cerca del aro), porque la curva por distancia del tiro ya incluye cuánto suele estar marcado; así no se cuenta dos veces |
| Equipo rival | efecto defensivo del equipo en 2024-25, suavizado hacia la liga |
| Arranque frío | medido: −1.46 pp (0-30 s), −0.50 pp (30-60 s), −0.39 pp (1-2 min) |
| Fatiga | pendiente medida tras calentar (+0.027 pp/min; escenario pesimista: límite inferior del IC) |

La distancia del defensor arranca en el valor típico de cada tiro (se puede fijar a mano). El tiro sigue una **parábola física** (movimiento de un proyectil desde la mano hasta el aro, con velocidad y ángulo de salida calculados; sin alturas de arco escritas a mano) que se muestra punteada antes de lanzar y como estela durante el vuelo, y la cámara TV es lateral para verla de perfil. Las posiciones de los otros cuatro defensores son **ilustrativas**; solo el defensor principal tiene efecto, a través de su distancia al tirador, y se dibuja algo desplazado de la línea al aro, como se defiende en la práctica. El efecto de la distancia al defensor es asociación en datos de otra época y mezcla contraataques sin defensor; el del rival es el del equipo en promedio, no el de un defensor concreto.

## Metodología

1. **Stints** (`src/stint_calculator.py`): minutos seguidos en pista al momento de cada tiro, contando solo tiempo de juego. El contador sigue entre Q1→Q2 y Q3→Q4 y **se reinicia en el medio tiempo**. El play-by-play no registra las sustituciones entre cuartos: en cada cuarto se detecta quién ya estaba en pista y conserva su contador si venía del cuarto anterior. Solo ~0.3% de los tiros tiene stint incierto y se excluye del análisis principal. También se guarda la ventaja del equipo del tirador y si juega de local.
2. **Tiro esperado** (`src/xshot_model.py`): gradient boosting con distancia, coordenadas, zona, tipo de tiro, periodo y tiempo restante; sin minutos en pista ni identidad del jugador. Validación doble: cruzada por partido (log-loss 0.6397 frente a 0.6913 sin modelo, AUC 0.657, error de calibración 0.17 pp) y **temporal** (entrena con 2021-22 a 2023-24 y evalúa en 2024-25, que no vio: log-loss 0.6407 frente a 0.6910, AUC 0.654, calibración 0.50 pp). Métricas en `data/processed/xshot_metrics.json`.
3. **Efecto de fatiga** (`src/fatigue_stats.py`): cada jugador se compara con su propio nivel **en esa temporada**. Contraste por jugador (residuo con ≥ 8 min − residuo con 2-6 min), pendiente con efectos fijos y errores robustos agrupados por jugador, efectos aleatorios (DerSimonian-Laird) para las diferencias entre jugadores, corrección de Benjamini-Hochberg y prueba placebo.
4. **Arranque frío, calendario y contexto**: rendimiento por tiempo desde la entrada, por cuarto y según primera entrada o re-entrada; control por back-to-back (calculado con las fechas), local y marcador.
5. **Defensa** (`scripts/build_defense_data.py`): efecto por equipo (con suavizado empirical Bayes) y tabla de distancia al defensor.
6. **Jugador nuevo**: acierto base según su perfil de tiro por zona + nivel; el efecto de fatiga sale de la distribución poblacional (promedio y τ). Si se ingresan tiros propios, se combinan por precisión (normal-normal).
7. **Incertidumbre**: todo se muestra con IC 95%; los tramos con pocos tiros se marcan y no se interpolan.

## Reproducir el análisis

```bash
pip install -r requirements.txt
python scripts/download_seasons.py 2021 2022 2023   # NBA 2021-22 a 2023-24 (la 2024-25 ya está en data/raw/)
python scripts/download_shot_logs.py                # 2014-15 con distancia al defensor (CC0)

python src/stint_calculator.py 2021 2022 2023 2024  # ~3 min por temporada
python src/xshot_model.py                           # modelo de tiro esperado (validación cruzada + temporal)
python scripts/build_web_data.py                    # estadística y datos de la interfaz (incluye placebo)
python scripts/build_defense_data.py                # defensa de equipos y distancia al defensor
python scripts/build_defense_data.py gap            # brecha de precisión con y sin datos del defensor

python tests/test_fatigue_stats.py                  # 6 pruebas con datos sintéticos
curl -o tests/three.min.js https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js
node tests/test_simulator.js                        # modelo de probabilidad, defensores y física del tiro (178 comprobaciones)
```
`data/raw/nbastats_2024.csv` (94 MB) no se versiona; está comprimido como `.tar.xz`. Las temporadas adicionales, el dataset externo y los CSV procesados grandes se regeneran con los scripts y están en `.gitignore`.

## Estructura

```text
├── data/            raw/ (tiros y play-by-play) · processed/ · README.md (diccionario)
├── src/             stint_calculator.py · xshot_model.py · fatigue_stats.py
├── scripts/         build_web_data.py · build_defense_data.py · download_seasons.py · download_shot_logs.py
├── tests/           pruebas del módulo estadístico (datos sintéticos)
├── web/             index.html · css/ · js/ · assets/ (logos AQX y Devpost) · data/ (JSON generado) · simulador/ (3D)
├── docs/            texto de Devpost y guion de video
└── documentacion/   descripción del proyecto
```

## Limitaciones

- **Asociación, no causalidad**: los entrenadores sustituyen a quien ven cansado, así que los stints largos están sesgados hacia jugadores que van bien. Esto puede ocultar fatiga real.
- **Sin datos del defensor en el análisis principal.** En la temporada 2014-15, conocer la distancia al defensor sube el AUC del tiro esperado de 0.617 a 0.634 (0.642 con reloj de posesión, toques y regates). Nuestro modelo deja esa parte como ruido, y no podemos comprobar si sesga la comparación entre minutos.
- Sin datos de condición física individual ni de carga.
- Casi no hay tiros con más de ~12 min seguidos: más allá, cualquier proyección es extrapolación.
- Potencia limitada por jugador (ver arriba). "No detectado" no significa "no existe".
- El efecto de la distancia al defensor viene de otra época (2014-15, temporada incompleta) y de otro sistema de medición.
- Los umbrales (2-6 min como referencia, 8 min como "largo") son una elección; la pendiente continua se reporta como alternativa.

## Trabajo futuro

Datos de seguimiento (posición de los defensores) en las temporadas recientes · carga acumulada por viajes y calendario · biometría · impacto defensivo de la fatiga.

## Datos y créditos

- NBA Stats API a través del repositorio público [`shufinskiy/nba_data`](https://github.com/shufinskiy/nba_data) (uso no comercial).
- Registro de tiros 2014-15 ("NBA shot logs"): espejo de OpenML, licencia CC0.
- Logos de AQX Analytics Hackathon y Devpost: pertenecen a sus titulares; se usan para identificar el concurso.

**Licencia del código:** MIT.
