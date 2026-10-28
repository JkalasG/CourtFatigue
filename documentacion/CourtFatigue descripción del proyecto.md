# CourtFatigue: ¿cuándo deja de rendir un jugador y dónde lo nota la cancha?

Actualizado el 28 oct 2026 · @juan

## Resumen

CourtFatigue es una herramienta de análisis que mide si el rendimiento de tiro de un jugador de la NBA cae según los minutos seguidos que lleva en cancha, en qué zonas, y con qué certeza se puede afirmar algo de un jugador concreto o de uno nuevo. Incluye un simulador 3D donde cada término de la probabilidad de anotar sale de datos medidos. Su objetivo es dar al entrenador una referencia honesta para decidir sustituciones: qué dicen los datos, qué no, y qué conviene probar.

*El nombre es una propuesta; puedes cambiarlo.*

## El problema

Las rotaciones en el baloncesto profesional se deciden en gran parte por intuición: el entrenador "ve" cansado a un jugador y lo cambia. No existe una guía clara, basada en datos, de cuántos minutos seguidos puede rendir cada jugador antes de bajar de nivel, ni de qué tipo de tiros se deterioran primero.

Sustituir demasiado pronto desperdicia a los mejores jugadores. Sustituir tarde cuesta puntos en momentos clave.

## La solución

CourtFatigue reconstruye cuántos minutos seguidos lleva cada jugador en cancha en el momento de cada tiro, y mide cómo cambia su acierto respecto a lo esperado por la dificultad del tiro. Se presenta en vistas pensadas para una persona sin formación técnica:

1. **Resumen en lenguaje llano** ("En 30 segundos"), panel para el cuerpo técnico y glosario.
2. **Explorador de jugadores:** curva por minutos seguidos con intervalo de confianza y mapas de tiro descansado frente a cansado.
3. **Evidencia:** cobertura de datos, robustez del resultado, repetición temporada por temporada, arranque frío, zonas de la cancha, características del jugador y ranking defensivo de los 30 equipos.
4. **Jugador nuevo:** proyección para alguien sin historial, con su incertidumbre, que se actualiza con sus tiros reales.
5. **Simulador 3D:** minutos seguidos, equipo rival y distancia del defensor.

La herramienta **solo recomienda sustituir a un jugador si hay evidencia estadísticamente sólida de caída en él**; si no, lo dice y muestra cuánto margen hay.

## Datos

- **NBA, temporadas regulares 2021-22 a 2024-25** (NBA Stats API a través del repositorio público `shufinskiy/nba_data`): 4 × 1,230 partidos, 872,158 tiros con coordenadas (`ShotChartDetail`) y el play-by-play con sustituciones y marcador (`PlayByPlayV2`). 913 jugadores; 592 con tiros suficientes en los tramos comparados.
- **Registro de tiros 2014-15** (Kaggle "NBA shot logs", espejo de OpenML, licencia CC0): 128,069 tiros con distancia al defensor más cercano. Se usa para el simulador y para medir la limitación por no tener datos del defensor en las temporadas recientes. No se cruza con las anteriores.

## Metodología

1. **Reconstrucción de stints:** solo cuenta tiempo de juego; el contador sigue entre Q1→Q2 y Q3→Q4 y se reinicia en el medio tiempo (prueba de sensibilidad: reinicio en cada cuarto). El play-by-play no registra las sustituciones entre cuartos, así que en cada cuarto se detecta quién ya estaba en pista. ~0.3% de los tiros tiene stint incierto y se excluye.
2. **Tiro esperado:** gradient boosting con distancia, coordenadas, zona, tipo de tiro, periodo y tiempo restante, sin minutos en pista ni identidad del jugador. Se valida con validación cruzada por partido (AUC 0.657, calibración 0.17 pp) y con una **prueba temporal**: entrenado con 2021-22 a 2023-24 y evaluado en 2024-25, que no vio (log-loss 0.6407 frente a 0.6910 sin modelo, AUC 0.654, calibración 0.50 pp).
3. **Efecto de fatiga:** cada jugador se compara con su propio nivel **en esa temporada**. Se contrasta ≥ 8 min seguidos contra 2-6 min (ya calentado, para no mezclar el arranque frío con fatiga), y se estima la pendiente por minuto con efectos fijos y errores agrupados por jugador. Un modelo de efectos aleatorios separa diferencias reales entre jugadores del ruido.
4. **Control de falsos positivos:** corrección de Benjamini-Hochberg y prueba placebo (minutos barajados dentro de cada jugador).
5. **Arranque frío, calendario y contexto:** rendimiento por tiempo desde la entrada, por cuarto y según primera entrada o re-entrada; controles por back-to-back, local y marcador.
6. **Defensa:** efecto de cada equipo rival (suavizado hacia la liga) y efecto de la distancia al defensor (monótono, con banda por remuestreo de partidos).
7. **Incertidumbre:** todos los resultados se muestran con intervalos de confianza, y los tramos con pocos datos se marcan como poco fiables.

## Hallazgos

- **Efecto promedio de la fatiga: no detectable.** Con ≥ 8 min seguidos, el acierto ajustado por dificultad cambia **+0.21 pp** (IC 95%: −0.13 a +0.56) frente a jugadores ya calentados; se descartan caídas promedio mayores a ~0.13 pp. La pendiente tras calentar es +0.027 pp/min (IC −0.014 a +0.069). El resultado se repite en cada temporada y resiste los controles (partidos decididos, local, marcador, back-to-back, reinicio por cuarto).
- **Zonas:** ninguna zona muestra una caída significativa tras calentar. Las dos interiores muestran una mejora leve (+0.11 y +0.16 pp/min).
- **Diferencias entre jugadores:** ninguna demostrable. 0 de 592 jugadores muestran una caída con IC 95% bajo cero y falsos descubrimientos < 5%. La potencia individual es limitada: solo se detectarían caídas de ~14 pp o más.
- **Arranque frío:** en los primeros 30 s tras entrar el jugador anota **−1.46 pp** menos de lo normal en él (IC −1.95 a −0.97), −0.50 pp entre 30 y 60 s y −0.39 pp entre 1 y 2 min; desde los 2 min es normal. Es negativo en las 4 temporadas (con intervalo claro en 3; en 2022 el intervalo incluye 0) y se repite con otra regla de stints (−1.08 pp).
- **Calendario y contexto:** back-to-back −0.39 pp (IC −0.67 a −0.11); jugar en casa +0.38 pp.
- **Defensa:** el efecto defensivo de cada equipo es real y estable entre temporadas (r ≈ 0.52), de −1.2 pp (Thunder) a +1.7 pp (Kings) en 2024-25. En 2014-15, conocer la distancia al defensor sube el AUC del tiro esperado de 0.617 a 0.634.
- **La regla ingenua no sirve:** "sustituir si cae 3 pp en algún tramo con ≥ 20 tiros" marca al 60.5% de los jugadores con datos reales y al 59.4% con los minutos barajados al azar; es ruido.

Como anticipaba el planteamiento, no apareció un efecto de fatiga grande, y es un hallazgo válido: las rotaciones actuales ya serían bastante eficientes. Lo accionable está en otro lado: cómo entran los jugadores.

## Impacto práctico

| Perfil | Cómo lo usa |
| --- | --- |
| Entrenadores | No acortar bloques por "cansancio de tiro" hasta ~12 min seguidos; diseñar la primera jugada tras una entrada para un tiro de ritmo (hipótesis a probar); dosificar a los tiradores clave en el segundo partido de un back-to-back. |
| Preparadores físicos | Saber que, con estos datos, ningún jugador muestra una caída demostrable por minutos seguidos; la carga debe medirse con datos físicos reales. |
| Analistas y gerencia | Ranking defensivo por equipo con su margen de error; la regla "−3 pp" descartada con evidencia; el límite de lo que se puede afirmar de un jugador con una temporada. |
| Aficionados y medios | Visualizar con claridad qué es señal y qué es ruido en el rendimiento. |

## Limitaciones

El análisis mide asociación y no demuestra causalidad. Se declaran de forma explícita:

- Los entrenadores ya sustituyen cuando perciben fatiga, así que los stints largos están sesgados hacia jugadores que van bien y son raros más allá de ~12 min. Esto puede ocultar fatiga real.
- Sin datos del defensor en las temporadas recientes: el modelo de tiro esperado deja esa parte como ruido, y no se puede comprobar si sesga la comparación entre minutos.
- Sin datos de condición física individual.
- Potencia limitada por jugador. "No detectado" no significa "no existe".
- El efecto de la distancia al defensor viene de otra época (2014-15) y es asociación; el efecto del rival es del equipo en promedio, no de un defensor concreto.
- Los umbrales (2-6 min como referencia, 8 min como "largo") son una elección; la pendiente continua se reporta como alternativa.

## Tecnologías

Python (`pandas`, `numpy`, `scikit-learn`) para el análisis; interfaz en HTML, CSS y JavaScript sin librerías (gráficos SVG propios), publicable en GitHub Pages; Three.js para el simulador 3D; GitHub para el código abierto. Pruebas con datos sintéticos para la estadística y para el modelo del simulador.

## Trabajo futuro

- Datos de seguimiento (posición de los defensores) en las temporadas recientes.
- Incluir la fatiga acumulada por viajes y carga real.
- Ampliar el análisis a la WNBA o la EuroLeague.
- Medir también el impacto defensivo de la fatiga y no solo el tiro.

## Versión corta para Devpost

CourtFatigue mide, con 872 mil tiros de 4 temporadas de la NBA, si el tiro cae al llevar muchos minutos seguidos en cancha. No encuentra una caída medible hasta ~12 minutos, desmonta una regla popular ("sustituir si cae 3 puntos", que marca igual con datos aleatorios) y detecta algo distinto: un arranque frío de ~1.5 puntos porcentuales en los primeros 30 segundos tras entrar. Incluye un simulador 3D donde cada término de la probabilidad de anotar sale de datos, con el rival y la distancia del defensor, y es explícito sobre lo que no se puede afirmar de un jugador individual.
