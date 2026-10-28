[English](../../DATA_QUALITY.md) | [Español](CALIDAD_DE_DATOS.md)

# Calidad de los datos

Qué comprobamos en los datos antes de analizarlos, qué encontramos y qué hicimos con cada hallazgo. Lo genera `python scripts/data_quality.py` (se puede repetir). Volver al [README](../../README.es.md).

## 1. De los datos crudos al análisis (embudo)

| Paso | Tiros | Perdidos | Motivo |
|---|---:|---:|---|
| Tiros crudos (4 temporadas) | 872,168 | 0 | Registro de tiros de la NBA, todas las temporadas |
| Con minutos en cancha reconstruidos | 872,158 | 10 | Se pierden los tiros que no se pueden unir con el play-by-play |
| Con tiro esperado (xShot) calculado | 872,158 | 0 | Se descartan filas con datos faltantes en las variables del modelo |
| Con stint fiable (análisis principal) | 869,292 | 2,866 | Se excluyen los stints inferidos |

## 2. Qué se comprobó en cada temporada

| Comprobación | 2021-22 | 2022-23 | 2023-24 | 2024-25 |
|---|---:|---:|---:|---:|
| Tiros | 216,722 | 217,218 | 218,701 | 219,527 |
| Partidos | 1,230 | 1,230 | 1,230 | 1,230 |
| Filas con algún dato faltante | 0.0% | 0.0% | 0.0% | 0.0% |
| Tiros duplicados | 0 | 0 | 0 | 0 |
| Marca de anotado distinta de 0/1 | 0 | 0 | 0 | 0 |
| Reloj fuera de rango | 0 | 0 | 0 | 0 |
| Distancia con coordenadas incoherentes (>3 ft) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| Triples desde menos de 21 ft | 0 | 0 | 0 | 0 |
| Dobles desde más de 25 ft | 0 | 0 | 0 | 0 |
| Tiros de más de 35 ft (se recortan a 35) | 655 | 625 | 604 | 740 |

## 3. ¿Coinciden los dos archivos entre sí?

Los tiros vienen de un archivo y las jugadas de otro. Comparamos, partido por partido, cuántos tiros y cuántos anotados tiene cada uno.

| Comprobación | 2021-22 | 2022-23 | 2023-24 | 2024-25 |
|---|---:|---:|---:|---:|
| Partidos que coinciden exactamente | 99.106% | 99.106% | 99.187% | 99.837% |
| Partidos con diferencia de 2 tiros o menos | 100.0% | 100.0% | 100.0% | 100.0% |
| Intentos: archivo de tiros / play-by-play | 216,722 / 216,733 | 217,218 / 217,225 | 218,701 / 218,705 | 219,527 / 219,530 |
| % de acierto: tiros / play-by-play | 46.11 / 46.11 | 47.54 / 47.54 | 47.43 / 47.43 | 46.72 / 46.72 |
| Partidos sin play-by-play | 0 | 0 | 0 | 0 |

## 4. Minutos en cancha reconstruidos

| Comprobación | 2021-22 | 2022-23 | 2023-24 | 2024-25 |
|---|---:|---:|---:|---:|
| Tiros sin minutos reconstruidos | 0 | 5 | 4 | 1 |
| Stints inferidos (excluidos del análisis principal) | 0.289% | 0.291% | 0.38% | 0.354% |
| Stint más largo (min) | 30.2 | 33.1 | 33.4 | 32.5 |
| Minutos en el cuarto por encima de 12 | 0 | 0 | 0 | 0 |
| Minutos jugados por encima de lo posible (todos / en el análisis principal) | 4 / 0 | 5 / 0 | 15 / 4 | 13 / 6 |
| Minutos negativos | 0 | 0 | 0 | 0 |

## 5. ¿Son comparables las temporadas?

| Comprobación | 2021-22 | 2022-23 | 2023-24 | 2024-25 |
|---|---:|---:|---:|---:|
| Tiros por partido (ambos equipos) | 176.2 | 176.6 | 177.8 | 178.5 |
| Porcentaje de triples | 39.93% | 38.75% | 39.49% | 42.12% |
| Acierto global | 46.11% | 47.54% | 47.43% | 46.72% |
| Distancia media (ft) | 13.8 | 13.46 | 13.53 | 14.0 |

## 6. Qué hacemos con lo encontrado

- **Distancias de más de 35 ft** (tiros desde media cancha): se recortan a 35 ft para el modelo de tiro esperado, para que unos pocos tiros extremos no distorsionen la curva.
- **Stints inferidos** (el tirador no aparece como jugador en cancha según las sustituciones): se marcan y se excluyen del análisis principal; entran solo en una prueba de robustez.
- **Tiros sin minutos reconstruidos:** se descartan, porque no se puede asignar fatiga.
- **Datos faltantes y duplicados:** no se encontraron en las columnas que usa el análisis; aun así el código descarta filas incompletas y elimina duplicados por la clave partido-evento-jugador, por si cambia la fuente.
- **Minutos jugados por encima de lo posible** (37 tiros de 872,168; 27 con stint inferido y por eso fuera del análisis principal): son partidos donde falta registrar una salida a banca. Los otros 10 están en el análisis principal; son una fracción mínima de la muestra y no se corrigen individualmente.
- **Diferencias menores con el play-by-play** (menos del 1% de los partidos, de 1 o 2 tiros): vienen de la fuente; no se corrigen porque el acierto global coincide al centésimo en las dos fuentes.
- **Reloj reiniciado en el medio tiempo:** el contador de minutos seguidos se reinicia en el tercer cuarto, y se prueba una alternativa que lo reinicia en cada cuarto.

## 7. Lo que estas comprobaciones no pueden detectar

- Errores sistemáticos de la fuente (por ejemplo, un tiro registrado con la posición equivocada pero dentro de rango).
- Que un entrenador sustituyera a alguien por cansancio visible: eso es un sesgo de selección, no un error de datos (ver *Limitaciones* en el README).
- No se verificaron las sustituciones contra el video; el stint se reconstruye con las jugadas registradas.
